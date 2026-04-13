"""Scheduled tasks service using APScheduler.

定时任务服务，主要任务：
1. 每天凌晨 02:00 为所有在线设备生成昨日 AI 日报
"""

import asyncio
import json
from datetime import date, datetime, timedelta
from typing import Any

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.postgres import AsyncSessionLocal
from app.models.device import Device, DeviceStatus
from app.models.daily_report import DailyReport, ReportStatus
from app.services.data_analysis_service import DataAnalysisService
from app.services.monitoring_service import MonitoringService
from app.services.video_risk_service import VideoRiskService
from app.core.prompts import (
    build_comprehensive_diagnosis_prompt,
    get_domain_from_pollutant_code,
)

logger = structlog.get_logger(__name__)
settings = get_settings()

# Global scheduler instance
_scheduler: AsyncIOScheduler | None = None


def _attach_video_prompt_context(prompt: str, video_risk_assessment: dict[str, Any]) -> str:
    if not video_risk_assessment:
        return prompt

    prompt_block = VideoRiskService.format_for_prompt(video_risk_assessment)
    return (
        f"{prompt}\n\n"
        "# Video Linkage Context (视频联动上下文)\n"
        f"{prompt_block}\n\n"
        "# Extra Output Requirement (额外输出要求)\n"
        "请在报告中明确给出“疑似风险级别 + 证据片段 + 关联数采 + 建议动作”，"
        "用于企业侧提前预警和复核，不得把视频摘要表述为法定监测结论。"
    )


def get_scheduler() -> AsyncIOScheduler:
    """Get the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(
            timezone="Asia/Shanghai",
            job_defaults={
                "coalesce": True,  # 合并多个错过的执行
                "max_instances": 1,  # 同一任务同时只能有一个实例
                "misfire_grace_time": 3600,  # 错过执行的宽限时间（秒）
            }
        )
    return _scheduler


async def generate_daily_report_for_device(
    device: Device,
    target_date: date,
    db: AsyncSession,
) -> dict[str, Any]:
    """为单个设备生成日报。

    Args:
        device: 设备对象
        target_date: 目标日期
        db: 数据库会话

    Returns:
        生成结果字典
    """
    device_id = str(device.id)

    try:
        logger.info(
            "Generating daily report for device",
            device_id=device_id,
            device_name=device.name,
            date=target_date.isoformat(),
        )

        # 检查是否已有该日期的报告
        existing_result = await db.execute(
            select(DailyReport).where(
                DailyReport.device_id == device.id,
                DailyReport.report_date == target_date,
            )
        )
        existing_report = existing_result.scalar_one_or_none()

        if existing_report and existing_report.status == ReportStatus.COMPLETED.value:
            logger.info(
                "Daily report already exists",
                device_id=device_id,
                report_id=str(existing_report.id),
            )
            return {
                "device_id": device_id,
                "status": "skipped",
                "reason": "report_exists",
            }

        # 创建或更新报告记录（标记为生成中）
        if existing_report:
            existing_report.status = ReportStatus.GENERATING.value
            existing_report.error_message = None
            report = existing_report
        else:
            report = DailyReport(
                device_id=device.id,
                report_date=target_date,
                status=ReportStatus.GENERATING.value,
            )
            db.add(report)
        await db.commit()
        await db.refresh(report)

        # 获取数据统计
        service = DataAnalysisService(db)
        stats = await service.analyze_device_daily_stats(
            device_id=device.mn,  # 使用 MN 号查询 TDengine
            target_date=target_date,
            pollutant_code=None,  # 综合分析所有污染物
        )

        if not stats.get("pollutants"):
            # 无数据，标记为失败
            report.status = ReportStatus.FAILED.value
            report.error_message = "无监测数据"
            await db.commit()
            return {
                "device_id": device_id,
                "status": "failed",
                "reason": "no_data",
            }

        # 获取行业信息
        industry_info = await service.get_device_industry_info(device.mn)
        industry_type = industry_info.get("industry_type")
        national_standard = industry_info.get("national_standard")
        video_risk_assessment = await VideoRiskService(db).build_device_video_risk_assessment(
            device_id=device.mn,
            target_date=target_date,
            stats=stats,
        )

        # 确定领域
        first_code = stats["pollutants"][0]["pollutant_code"]
        domain = get_domain_from_pollutant_code(first_code)

        # 构建 Prompt
        prompt = build_comprehensive_diagnosis_prompt(
            device_id=device.mn,
            device_name=device.name,
            report_date=target_date.isoformat(),
            pollutants_stats=stats["pollutants"],
            total_data_points=stats.get("data_count", 0),
            domain=domain,
            industry_type=industry_type,
            national_standard=national_standard,
        )
        prompt = _attach_video_prompt_context(prompt, video_risk_assessment)

        # 调用 AI 生成报告
        report_content = await _call_spark_api(prompt)

        # 更新报告记录
        report.status = ReportStatus.COMPLETED.value
        report.report_content = report_content
        report.stats_snapshot = json.dumps(
            {
                **stats,
                "video_risk_assessment": video_risk_assessment,
            },
            ensure_ascii=False,
        )
        report.pollutant_count = len(stats["pollutants"])
        report.data_points = stats.get("data_count", 0)
        report.domain = domain
        report.generated_at = datetime.now()
        report.error_message = None

        await db.commit()

        logger.info(
            "Daily report generated successfully",
            device_id=device_id,
            report_id=str(report.id),
            pollutant_count=report.pollutant_count,
        )

        return {
            "device_id": device_id,
            "status": "success",
            "report_id": str(report.id),
            "pollutant_count": report.pollutant_count,
        }

    except Exception as e:
        logger.error(
            "Failed to generate daily report",
            device_id=device_id,
            error=str(e),
        )

        # 更新报告状态为失败
        try:
            result = await db.execute(
                select(DailyReport).where(
                    DailyReport.device_id == device.id,
                    DailyReport.report_date == target_date,
                )
            )
            report = result.scalar_one_or_none()
            if report:
                report.status = ReportStatus.FAILED.value
                report.error_message = str(e)[:500]  # 限制错误消息长度
                await db.commit()
        except Exception as update_error:
            logger.error("Failed to update report status", error=str(update_error))

        return {
            "device_id": device_id,
            "status": "failed",
            "error": str(e),
        }


async def _call_spark_api(prompt: str) -> str:
    """调用星火大模型 API。

    Args:
        prompt: 提示词

    Returns:
        AI 生成的内容
    """
    from app.services.llm.spark_client import SparkClient, SparkClientError

    if not settings.spark_app_id or not settings.spark_api_key or not settings.spark_api_secret:
        raise ValueError("Spark API 未配置")

    client = SparkClient(
        app_id=settings.spark_app_id,
        api_secret=settings.spark_api_secret,
        api_key=settings.spark_api_key,
        api_password=settings.spark_api_password,
        spark_url=settings.spark_api_url,
        domain=settings.spark_domain,
    )

    messages = [{"role": "user", "content": prompt}]
    return await client.chat(messages)


async def generate_daily_reports_job():
    """定时任务：为所有在线设备生成昨日日报。

    此任务每天凌晨 02:00 执行，遍历所有在线设备，
    为每个设备生成昨日的 AI 诊断报告。
    """
    logger.info("Starting daily reports generation job")

    # 目标日期为昨天
    target_date = date.today() - timedelta(days=1)

    results = {
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "total": 0,
        "details": [],
    }

    try:
        async with AsyncSessionLocal() as db:
            # 查询所有在线设备
            query = select(Device).where(
                Device.status == DeviceStatus.ONLINE.value
            )
            result = await db.execute(query)
            devices = result.scalars().all()

            results["total"] = len(devices)
            logger.info(
                "Found online devices for daily report",
                device_count=len(devices),
                target_date=target_date.isoformat(),
            )

            # 为每个设备生成报告
            for device in devices:
                # 每个设备使用独立会话，避免事务冲突
                async with AsyncSessionLocal() as device_db:
                    report_result = await generate_daily_report_for_device(
                        device=device,
                        target_date=target_date,
                        db=device_db,
                    )

                    results["details"].append(report_result)

                    if report_result["status"] == "success":
                        results["success"] += 1
                    elif report_result["status"] == "skipped":
                        results["skipped"] += 1
                    else:
                        results["failed"] += 1

                # 添加短暂延迟，避免 API 限流
                await asyncio.sleep(2)

        logger.info(
            "Daily reports generation job completed",
            target_date=target_date.isoformat(),
            total=results["total"],
            success=results["success"],
            failed=results["failed"],
            skipped=results["skipped"],
        )

    except Exception as e:
        logger.error(
            "Daily reports generation job failed",
            error=str(e),
        )
        raise

    return results


async def monitor_device_health_job() -> dict[str, int]:
    """定时任务：设备健康检查（离线检测 + 离线告警补齐）。"""
    from app.services.device_health import sync_device_health

    try:
        async with AsyncSessionLocal() as db:
            result = await sync_device_health(db)
            await db.commit()
        if result.get("offline_status_updated") or result.get("offline_alarms_upserted"):
            logger.info("Device health synced", **result)
        return result
    except Exception as e:
        logger.error("Device health monitor failed", error=str(e))
        return {"offline_status_updated": 0, "offline_alarms_upserted": 0}


async def aggregate_monitoring_data_job():
    """定时任务：聚合昨日监测数据为每日统计。

    此任务每天凌晨 01:00 执行，将昨日的原始监测数据
    聚合为每日统计记录，用于热力图和趋势分析。
    """
    logger.info("Starting monitoring data aggregation job")

    # 目标日期为昨天
    target_date = date.today() - timedelta(days=1)

    try:
        async with AsyncSessionLocal() as db:
            service = MonitoringService(db)
            count = await service.aggregate_daily_stats(target_date)

            logger.info(
                "Monitoring data aggregation completed",
                target_date=target_date.isoformat(),
                aggregated_count=count,
            )

            return {
                "status": "success",
                "target_date": target_date.isoformat(),
                "aggregated_count": count,
            }

    except Exception as e:
        logger.error(
            "Monitoring data aggregation failed",
            error=str(e),
        )
        return {
            "status": "failed",
            "error": str(e),
        }


def setup_scheduler(app=None):
    """配置并启动定时任务调度器。

    Args:
        app: FastAPI 应用实例（可选，用于存储调度器引用）
    """
    scheduler = get_scheduler()

    # 添加监测数据聚合任务
    # 每天凌晨 01:00 执行（在日报生成之前）
    scheduler.add_job(
        aggregate_monitoring_data_job,
        CronTrigger(
            hour=1,
            minute=0,
            timezone="Asia/Shanghai",
        ),
        id="monitoring_aggregation_job",
        name="Aggregate Daily Monitoring Data",
        replace_existing=True,
    )

    logger.info(
        "Scheduled monitoring aggregation job",
        schedule="Every day at 01:00 (Asia/Shanghai)",
    )

    # 添加每日报告生成任务
    # 每天凌晨 02:00 执行
    scheduler.add_job(
        generate_daily_reports_job,
        CronTrigger(
            hour=2,
            minute=0,
            timezone="Asia/Shanghai",
        ),
        id="daily_reports_job",
        name="Generate Daily AI Reports",
        replace_existing=True,
    )

    logger.info(
        "Scheduled daily reports job",
        schedule="Every day at 02:00 (Asia/Shanghai)",
    )

    # 设备健康检查：每 N 秒执行一次（默认 5 分钟），并在启动后立即运行一次
    scheduler.add_job(
        monitor_device_health_job,
        IntervalTrigger(
            seconds=int(settings.device_health_check_interval_seconds),
            timezone="Asia/Shanghai",
        ),
        id="device_health_monitor_job",
        name="Monitor Device Health (Offline + Alarms)",
        replace_existing=True,
        next_run_time=datetime.now(),  # run once immediately after scheduler starts
    )
    logger.info(
        "Scheduled device health monitor job",
        interval_seconds=int(settings.device_health_check_interval_seconds),
    )

    # 存储到 app.state（如果提供）
    if app is not None:
        app.state.scheduler = scheduler

    return scheduler


def start_scheduler():
    """启动调度器。"""
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started")


def stop_scheduler():
    """停止调度器。"""
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


async def trigger_daily_reports_manually(
    device_ids: list[str] | None = None,
    target_date: date | None = None,
) -> dict[str, Any]:
    """手动触发日报生成任务。

    用于测试或手动补生成日报。

    Args:
        device_ids: 指定设备ID列表，None 表示所有在线设备
        target_date: 目标日期，默认为昨天

    Returns:
        生成结果统计
    """
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    logger.info(
        "Manually triggering daily reports generation",
        device_ids=device_ids,
        target_date=target_date.isoformat(),
    )

    results = {
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "total": 0,
        "details": [],
    }

    async with AsyncSessionLocal() as db:
        # 构建查询
        if device_ids:
            query = select(Device).where(Device.mn.in_(device_ids))
        else:
            query = select(Device).where(
                Device.status == DeviceStatus.ONLINE.value
            )

        result = await db.execute(query)
        devices = result.scalars().all()
        results["total"] = len(devices)

        for device in devices:
            async with AsyncSessionLocal() as device_db:
                report_result = await generate_daily_report_for_device(
                    device=device,
                    target_date=target_date,
                    db=device_db,
                )

                results["details"].append(report_result)

                if report_result["status"] == "success":
                    results["success"] += 1
                elif report_result["status"] == "skipped":
                    results["skipped"] += 1
                else:
                    results["failed"] += 1

            await asyncio.sleep(1)

    return results
