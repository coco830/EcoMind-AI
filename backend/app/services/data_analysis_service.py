"""
数据特征提取服务

为 AI 分析提供设备监测数据的统计特征，将原始时序数据转换为结构化的统计信息。
"""

import json
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.tdengine_client import get_tdengine_client
from app.models.device import Device, ThresholdConfig

logger = structlog.get_logger(__name__)


class DataAnalysisService:
    """数据分析服务，提供监测数据的特征提取和统计分析。"""

    def __init__(self, db_session: AsyncSession | None = None):
        """
        初始化数据分析服务。

        Args:
            db_session: PostgreSQL 数据库会话，用于查询设备阈值配置
        """
        self.tdengine = get_tdengine_client()
        self.db_session = db_session

    async def get_device_thresholds(self, device_id: str) -> ThresholdConfig | None:
        """
        获取设备的阈值配置。

        Args:
            device_id: 设备 ID 或 MN 号

        Returns:
            阈值配置对象，如果没有配置则返回 None
        """
        if not self.db_session:
            return None

        try:
            # 尝试通过 ID 或 MN 号查询设备
            stmt = select(Device).where(
                (Device.id == device_id) | (Device.mn == device_id)
            )
            result = await self.db_session.execute(stmt)
            device = result.scalar_one_or_none()

            if device and device.thresholds:
                return ThresholdConfig.model_validate_json(device.thresholds)
            return None
        except Exception as e:
            logger.warning("Failed to get device thresholds", device_id=device_id, error=str(e))
            return None

    async def analyze_device_daily_stats(
        self,
        device_id: str,
        target_date: date,
        pollutant_code: str | None = None,
    ) -> dict[str, Any]:
        """
        分析设备指定日期的数据统计特征。

        Args:
            device_id: 设备 ID 或 MN 号
            target_date: 目标日期
            pollutant_code: 污染物代码（可选，不指定则分析所有污染物）

        Returns:
            包含以下字段的统计字典：
            - device_id: 设备ID
            - date: 分析日期
            - pollutants: 各污染物的统计数据列表
            - summary: 综合描述文本
        """
        # 计算时间范围（当天 00:00:00 到 23:59:59）
        start_time = datetime.combine(target_date, datetime.min.time())
        end_time = datetime.combine(target_date, datetime.max.time())

        logger.info(
            "Analyzing device daily stats",
            device_id=device_id,
            date=target_date.isoformat(),
            pollutant_code=pollutant_code,
        )

        # 查询原始数据
        raw_data = await self.tdengine.query_monitoring_data(
            device_id=device_id,
            pollutant_code=pollutant_code,
            start_time=start_time,
            end_time=end_time,
            limit=10000,  # 分钟级数据一天最多 1440 条
        )

        if not raw_data:
            logger.warning("No data found for device", device_id=device_id, date=target_date.isoformat())
            return {
                "device_id": device_id,
                "date": target_date.isoformat(),
                "pollutants": [],
                "summary": "该日期无监测数据",
                "data_count": 0,
            }

        # 转换为 DataFrame
        df = pd.DataFrame(raw_data)
        df["ts"] = pd.to_datetime(df["ts"])

        # 获取阈值配置
        thresholds = await self.get_device_thresholds(device_id)

        # 按污染物分组分析
        pollutant_stats = []
        for code, group in df.groupby("pollutant_code"):
            stats = self._calculate_pollutant_stats(
                group,
                str(code),
                thresholds,
            )
            pollutant_stats.append(stats)

        # 生成综合描述
        summary = self._generate_summary(pollutant_stats, target_date)

        result = {
            "device_id": device_id,
            "date": target_date.isoformat(),
            "pollutants": pollutant_stats,
            "summary": summary,
            "data_count": len(df),
        }

        logger.info(
            "Analysis completed",
            device_id=device_id,
            pollutant_count=len(pollutant_stats),
            data_count=len(df),
        )

        return result

    def _calculate_pollutant_stats(
        self,
        df: pd.DataFrame,
        pollutant_code: str,
        thresholds: ThresholdConfig | None,
    ) -> dict[str, Any]:
        """
        计算单个污染物的统计特征。

        Args:
            df: 该污染物的数据 DataFrame
            pollutant_code: 污染物代码
            thresholds: 阈值配置

        Returns:
            统计特征字典
        """
        values = df["value"]

        # 基本统计
        avg_val = float(values.mean())
        max_val = float(values.max())
        min_val = float(values.min())
        std_val = float(values.std()) if len(values) > 1 else 0.0

        # 峰值时间
        max_idx = values.idxmax()
        peak_time = df.loc[max_idx, "ts"].strftime("%H:%M") if pd.notna(max_idx) else None

        # 波动率（变异系数 CV = std / mean）
        volatility = (std_val / avg_val * 100) if avg_val > 0 else 0.0

        # 超标次数
        over_limit_count = 0
        threshold_value = None
        if thresholds:
            pollutant_threshold = thresholds.get_threshold(pollutant_code)
            if pollutant_threshold:
                threshold_value = pollutant_threshold.alarm_value
                over_limit_count = int((values > threshold_value).sum())

        # 时段分析（早班 6:00-14:00，晚班 14:00-22:00，夜班 22:00-6:00）
        df_copy = df.copy()
        df_copy["hour"] = df_copy["ts"].dt.hour

        morning_mask = (df_copy["hour"] >= 6) & (df_copy["hour"] < 14)
        afternoon_mask = (df_copy["hour"] >= 14) & (df_copy["hour"] < 22)
        night_mask = (df_copy["hour"] >= 22) | (df_copy["hour"] < 6)

        morning_avg = float(df_copy.loc[morning_mask, "value"].mean()) if morning_mask.any() else None
        afternoon_avg = float(df_copy.loc[afternoon_mask, "value"].mean()) if afternoon_mask.any() else None
        night_avg = float(df_copy.loc[night_mask, "value"].mean()) if night_mask.any() else None

        # 趋势描述
        trend_description = self._generate_trend_description(
            avg_val=avg_val,
            max_val=max_val,
            min_val=min_val,
            volatility=volatility,
            over_limit_count=over_limit_count,
            morning_avg=morning_avg,
            afternoon_avg=afternoon_avg,
            night_avg=night_avg,
            threshold_value=threshold_value,
        )

        return {
            "pollutant_code": pollutant_code,
            "avg_val": round(avg_val, 4),
            "max_val": round(max_val, 4),
            "min_val": round(min_val, 4),
            "peak_time": peak_time,
            "volatility": round(volatility, 2),  # 百分比
            "std_val": round(std_val, 4),
            "over_limit_count": over_limit_count,
            "threshold_value": threshold_value,
            "data_points": len(df),
            "time_period_stats": {
                "morning_avg": round(morning_avg, 4) if morning_avg else None,
                "afternoon_avg": round(afternoon_avg, 4) if afternoon_avg else None,
                "night_avg": round(night_avg, 4) if night_avg else None,
            },
            "trend_description": trend_description,
        }

    def _generate_trend_description(
        self,
        avg_val: float,
        max_val: float,
        min_val: float,
        volatility: float,
        over_limit_count: int,
        morning_avg: float | None,
        afternoon_avg: float | None,
        night_avg: float | None,
        threshold_value: float | None,
    ) -> str:
        """
        基于规则生成趋势描述文本。

        Args:
            各统计指标

        Returns:
            描述文本
        """
        descriptions = []

        # 超标情况
        if over_limit_count > 0:
            if over_limit_count >= 10:
                descriptions.append(f"超标严重，共 {over_limit_count} 次超标")
            else:
                descriptions.append(f"存在 {over_limit_count} 次超标")

        # 波动性判断
        if volatility > 50:
            descriptions.append("数据波动剧烈")
        elif volatility > 20:
            descriptions.append("数据波动较大")
        elif volatility < 5:
            descriptions.append("数据较为平稳")

        # 峰谷差异
        if max_val > 0:
            peak_ratio = (max_val - min_val) / max_val * 100
            if peak_ratio > 80:
                descriptions.append("峰谷差异显著")
            elif peak_ratio > 50:
                descriptions.append("峰谷差异明显")

        # 时段差异分析
        if morning_avg and afternoon_avg and night_avg:
            avgs = [
                ("早班", morning_avg),
                ("午班", afternoon_avg),
                ("夜班", night_avg),
            ]
            max_period = max(avgs, key=lambda x: x[1])
            min_period = min(avgs, key=lambda x: x[1])

            if max_period[1] > min_period[1] * 1.5:
                descriptions.append(f"{max_period[0]}浓度显著高于{min_period[0]}，昼夜差异显著")
            elif max_period[1] > min_period[1] * 1.2:
                descriptions.append(f"{max_period[0]}浓度略高于{min_period[0]}")

        # 与阈值的关系
        if threshold_value:
            ratio = avg_val / threshold_value * 100
            if ratio > 90:
                descriptions.append(f"均值接近阈值（达 {ratio:.0f}%）")
            elif ratio > 70:
                descriptions.append(f"均值处于阈值 {ratio:.0f}% 水平")

        return "；".join(descriptions) if descriptions else "数据正常"

    def _generate_summary(
        self,
        pollutant_stats: list[dict[str, Any]],
        target_date: date,
    ) -> str:
        """
        生成综合分析摘要。

        Args:
            pollutant_stats: 各污染物统计数据
            target_date: 分析日期

        Returns:
            综合摘要文本
        """
        if not pollutant_stats:
            return "无数据"

        total_over_limit = sum(p.get("over_limit_count", 0) for p in pollutant_stats)
        high_volatility_count = sum(1 for p in pollutant_stats if p.get("volatility", 0) > 20)

        summary_parts = [f"{target_date.isoformat()} 数据分析："]

        # 超标统计
        if total_over_limit > 0:
            over_limit_pollutants = [
                p["pollutant_code"]
                for p in pollutant_stats
                if p.get("over_limit_count", 0) > 0
            ]
            summary_parts.append(
                f"共 {total_over_limit} 次超标，涉及污染物：{', '.join(over_limit_pollutants)}"
            )
        else:
            summary_parts.append("无超标记录")

        # 波动性统计
        if high_volatility_count > 0:
            summary_parts.append(f"{high_volatility_count} 项污染物波动较大")

        # 主要问题污染物
        problematic = [
            p for p in pollutant_stats
            if p.get("over_limit_count", 0) > 0 or p.get("volatility", 0) > 30
        ]
        if problematic:
            codes = [p["pollutant_code"] for p in problematic]
            summary_parts.append(f"需重点关注：{', '.join(codes)}")

        return "；".join(summary_parts)


# 便捷函数：直接使用，无需实例化
async def analyze_device_daily_stats(
    device_id: str,
    target_date: date,
    pollutant_code: str | None = None,
    db_session: AsyncSession | None = None,
) -> dict[str, Any]:
    """
    分析设备指定日期的数据统计特征（便捷函数）。

    Args:
        device_id: 设备 ID 或 MN 号
        target_date: 目标日期
        pollutant_code: 污染物代码（可选）
        db_session: 数据库会话（可选，用于获取阈值配置）

    Returns:
        统计特征字典

    Example:
        ```python
        from datetime import date
        from app.services.data_analysis_service import analyze_device_daily_stats

        stats = await analyze_device_daily_stats(
            device_id="DEVICE001",
            target_date=date(2024, 1, 15)
        )
        print(stats)
        # {
        #     "device_id": "DEVICE001",
        #     "date": "2024-01-15",
        #     "pollutants": [
        #         {
        #             "pollutant_code": "w01018",
        #             "avg_val": 45.32,
        #             "max_val": 78.5,
        #             "min_val": 12.1,
        #             "peak_time": "14:35",
        #             "volatility": 28.5,
        #             "over_limit_count": 3,
        #             "trend_description": "存在 3 次超标；数据波动较大"
        #         }
        #     ],
        #     "summary": "2024-01-15 数据分析：共 3 次超标..."
        # }
        ```
    """
    service = DataAnalysisService(db_session)
    return await service.analyze_device_daily_stats(device_id, target_date, pollutant_code)
