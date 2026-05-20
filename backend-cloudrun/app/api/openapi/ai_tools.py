"""AI prediction and report tool endpoints for OpenAPI agent integrations."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Annotated, Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.openapi.auth import ApiClientContext, require_tool_permission, resolve_target_org
from app.api.openapi.schemas import PredictionResponse, AiReportResponse
from app.core.pollutant_library import get_pollutant_info, get_pollutant_name, normalize_pollutant_code
from app.db.postgres import get_db
from app.models.daily_report import DailyReport, ReportStatus
from app.models.device import Device, ThresholdConfig, INDUSTRY_STANDARD_MAP
from app.services.monitoring_service import MonitoringService

router = APIRouter()
logger = structlog.get_logger()


async def _find_device_by_org(
    db: AsyncSession, org_id, device_name: str | None, device_mn: str | None,
) -> Device | None:
    """Find a device belonging to the given org."""
    query = (
        select(Device)
        .options(selectinload(Device.organization))
        .where(Device.org_id == org_id)
    )
    if device_mn:
        query = query.where(Device.mn == device_mn)
    elif device_name:
        query = query.where(Device.name.contains(device_name))

    query = query.order_by(Device.created_at.asc()).limit(1)
    result = await db.execute(query)
    return result.scalars().first()


def _get_threshold_for_pollutant(device: Device, pollutant_code: str) -> float | None:
    """Extract threshold value for a pollutant from device config."""
    if not device.thresholds:
        return None
    try:
        tc = ThresholdConfig.model_validate_json(device.thresholds)
        pt = tc.get_threshold(normalize_pollutant_code(pollutant_code))
        return pt.alarm_value if pt else None
    except Exception:
        return None


def _coerce_sort_key(value: Any) -> float:
    """Best-effort conversion to a sortable timestamp."""
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            dt = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except ValueError:
            return 0.0
    return 0.0


async def _get_recent_pollutant_candidates(
    db: AsyncSession,
    device: Device,
    limit: int = 5,
) -> list[str]:
    """Get recent pollutant codes with available data for fallback prediction."""
    service = MonitoringService(db)
    rows = await service.get_latest_values(
        device_ids=[device.mn],
        org_id=str(device.org_id),
    )

    sorted_rows = sorted(rows, key=lambda row: _coerce_sort_key(row.get("ts")), reverse=True)
    candidates: list[str] = []
    for row in sorted_rows:
        code = normalize_pollutant_code(str(row.get("pollutant_code") or "").strip())
        if not code or code in candidates:
            continue
        candidates.append(code)
        if len(candidates) >= limit:
            break

    return candidates


async def _run_prediction(
    db: AsyncSession,
    device: Device,
    pollutant_code: str,
    prediction_hours: int,
) -> tuple[dict[str, Any] | None, str | None]:
    """Run prediction and return (result, error_message)."""
    from app.ai.prediction import predict_trend

    try:
        result = await predict_trend(
            device_id=device.mn,
            pollutant_code=pollutant_code,
            hours=24,
            prediction_hours=prediction_hours,
            db_session=db,
        )
        return result, None
    except Exception as exc:
        return None, str(exc)


@router.get(
    "/ai/predict",
    response_model=PredictionResponse,
    summary="AI趋势预测",
    description="获取指定设备某污染物的AI趋势预测（未来1-4小时），包含置信区间和超标风险评估。供智能体预判排放趋势。",
)
async def get_ai_prediction(
    ctx: Annotated[ApiClientContext, Depends(require_tool_permission("get_ai_prediction"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    enterprise_name: str | None = Query(None, description="企业名称（all_orgs Key 必填，支持模糊匹配）"),
    org_id: UUID | None = Query(None, description="组织ID（可选，优先于 enterprise_name）"),
    device_name: str | None = Query(None, description="设备名称（模糊匹配）"),
    device_mn: str | None = Query(None, description="设备MN号（精确匹配）"),
    pollutant_code: str = Query("w01018", description="污染物编码，默认COD"),
    prediction_hours: int = Query(4, ge=1, le=24, description="预测时长（小时）"),
) -> PredictionResponse:
    """Get AI trend prediction for a device pollutant."""
    target_org_id, target_org_name = await resolve_target_org(
        ctx=ctx,
        db=db,
        enterprise_name=enterprise_name,
        org_id=org_id,
    )

    device = await _find_device_by_org(db, target_org_id, device_name, device_mn)
    if not device:
        return PredictionResponse(
            success=False, data=None,
            summary=f"未找到匹配的设备（企业：{target_org_name}）",
        )

    requested_code = normalize_pollutant_code(pollutant_code)
    requested_name = get_pollutant_name(requested_code)

    fallback_candidates = await _get_recent_pollutant_candidates(db, device)
    candidate_codes: list[str] = []
    for code in [requested_code, *fallback_candidates]:
        if code and code not in candidate_codes:
            candidate_codes.append(code)

    attempted_codes: list[str] = []
    selected_code: str | None = None
    selected_result: dict[str, Any] | None = None
    last_error: str | None = None

    for candidate_code in candidate_codes:
        attempted_codes.append(candidate_code)
        result, error = await _run_prediction(
            db=db,
            device=device,
            pollutant_code=candidate_code,
            prediction_hours=prediction_hours,
        )
        if error:
            last_error = error
            logger.warning(
                "Prediction attempt failed",
                device_mn=device.mn,
                pollutant_code=candidate_code,
                error=error,
            )
            continue

        raw_predictions = (result or {}).get("predictions", [])
        if raw_predictions:
            selected_code = candidate_code
            selected_result = result
            break

    if selected_code is None or selected_result is None:
        available_fallback = [code for code in candidate_codes if code != requested_code]
        fallback_text = ""
        if available_fallback:
            fallback_names = [get_pollutant_name(code) for code in available_fallback]
            fallback_text = f"。可尝试污染物：{'、'.join(fallback_names)}"

        error_hint = f"。最近错误：{last_error[:120]}" if last_error else ""
        return PredictionResponse(
            success=False,
            data=None,
            summary=(
                f"{device.name}请求的{requested_name}暂无可用预测结果，可能是历史数据不足或模型暂不可用"
                f"{fallback_text}{error_hint}"
            ),
        )

    norm_code = selected_code
    result = selected_result
    used_fallback_pollutant = norm_code != requested_code

    pol_info = get_pollutant_info(norm_code)
    pol_name = pol_info["name"] if pol_info else norm_code
    unit = pol_info["unit"] if pol_info else ""
    threshold = _get_threshold_for_pollutant(device, norm_code)

    raw_predictions = result.get("predictions", [])

    # Format prediction points
    prediction_points = []
    max_predicted = float("-inf")
    min_predicted = float("inf")
    exceed_risk_time = None

    for p in raw_predictions:
        val = float(p.get("value", 0) or 0)
        lower = float(p.get("value_lower", val) or val)
        upper = float(p.get("value_upper", val) or val)
        ts = p.get("timestamp", "")

        max_predicted = max(max_predicted, val)
        min_predicted = min(min_predicted, val)

        if threshold and upper >= threshold and exceed_risk_time is None:
            exceed_risk_time = ts

        prediction_points.append({
            "time": ts,
            "predicted_value": round(val, 4),
            "lower_bound": round(lower, 4),
            "upper_bound": round(upper, 4),
        })

    # Risk assessment
    exceed_risk = False
    risk_description = "低风险，预测值在安全范围内"
    if threshold and threshold > 0:
        if max_predicted >= threshold:
            exceed_risk = True
            risk_description = f"高风险：预测最大值{max_predicted:.2f}{unit}将超过限值{threshold}{unit}"
        elif max_predicted >= threshold * 0.8:
            risk_description = f"中等风险：预测最大值{max_predicted:.2f}{unit}接近限值{threshold}{unit}的{max_predicted/threshold*100:.0f}%"

    # Current value from historical data
    historical = result.get("historical_data", [])
    current_value_raw = historical[-1].get("value") if historical else None
    try:
        current_value = float(current_value_raw) if current_value_raw is not None else None
    except (TypeError, ValueError):
        current_value = None

    # Summary
    summary_parts = [f"{device.name}的{pol_name}AI预测（未来{prediction_hours}小时）"]
    if used_fallback_pollutant:
        summary_parts.append(f"原请求{requested_name}数据不足，已自动回退")
    if current_value is not None:
        summary_parts.append(f"当前值{current_value:.2f}{unit}")
    summary_parts.append(f"预测范围{min_predicted:.2f}-{max_predicted:.2f}{unit}")
    if exceed_risk:
        summary_parts.append(f"存在超标风险")
    summary_text = "，".join(summary_parts) + "。"

    industry_info = INDUSTRY_STANDARD_MAP.get(device.industry_type or "", {})

    return PredictionResponse(
        success=True,
        data={
            "device_name": device.name,
            "device_mn": device.mn,
            "enterprise": target_org_name,
            "pollutant": pol_name,
            "pollutant_code": norm_code,
            "requested_pollutant_code": requested_code,
            "requested_pollutant": requested_name,
            "used_fallback_pollutant": used_fallback_pollutant,
            "unit": unit,
            "threshold": threshold,
            "national_standard": device.national_standard or industry_info.get("standard_name", ""),
            "current_value": round(current_value, 4) if current_value is not None else None,
            "prediction_hours": prediction_hours,
            "model_type": result.get("model_type", "unknown"),
            "predictions": prediction_points,
            "risk_assessment": {
                "max_predicted": round(max_predicted, 4),
                "min_predicted": round(min_predicted, 4),
                "exceed_risk": exceed_risk,
                "risk_description": risk_description,
                "exceed_risk_time": exceed_risk_time,
            },
            "attempted_pollutant_codes": attempted_codes,
        },
        summary=summary_text,
    )


async def _get_completed_report_on(
    db: AsyncSession,
    device_id,
    target_date: date,
) -> DailyReport | None:
    """Get completed report on an exact date."""
    result = await db.execute(
        select(DailyReport)
        .where(
            and_(
                DailyReport.device_id == device_id,
                DailyReport.report_date == target_date,
                DailyReport.status == ReportStatus.COMPLETED.value,
            )
        )
        .order_by(DailyReport.generated_at.desc())
        .limit(1)
    )
    return result.scalars().first()


async def _get_latest_completed_report(
    db: AsyncSession,
    device_id,
    before_or_on: date | None = None,
) -> DailyReport | None:
    """Get latest completed report, optionally constrained by date."""
    query = select(DailyReport).where(
        and_(
            DailyReport.device_id == device_id,
            DailyReport.status == ReportStatus.COMPLETED.value,
        )
    )
    if before_or_on:
        query = query.where(DailyReport.report_date <= before_or_on)

    query = query.order_by(DailyReport.report_date.desc(), DailyReport.generated_at.desc()).limit(1)
    result = await db.execute(query)
    return result.scalars().first()


@router.get(
    "/ai/report",
    response_model=AiReportResponse,
    summary="获取AI运维诊断报告",
    description="获取指定设备的AI运维诊断报告（优先返回缓存的每日报告）。包含问题分析和运维建议。",
)
async def get_ai_report(
    ctx: Annotated[ApiClientContext, Depends(require_tool_permission("get_ai_report"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    enterprise_name: str | None = Query(None, description="企业名称（all_orgs Key 必填，支持模糊匹配）"),
    org_id: UUID | None = Query(None, description="组织ID（可选，优先于 enterprise_name）"),
    device_name: str | None = Query(None, description="设备名称（模糊匹配）"),
    device_mn: str | None = Query(None, description="设备MN号（精确匹配）"),
    report_date: date | None = Query(None, description="报告日期，默认今天"),
) -> AiReportResponse:
    """Get AI diagnostic report for a device (cached daily report preferred)."""
    target_org_id, target_org_name = await resolve_target_org(
        ctx=ctx,
        db=db,
        enterprise_name=enterprise_name,
        org_id=org_id,
    )

    device = await _find_device_by_org(db, target_org_id, device_name, device_mn)
    if not device:
        return AiReportResponse(
            success=False, data=None,
            summary=f"未找到匹配的设备（企业：{target_org_name}）",
        )

    requested_date = report_date or date.today()
    report = await _get_completed_report_on(db, device.id, requested_date)
    used_fallback_report = False
    fallback_reason = ""

    if report is None:
        report = await _get_latest_completed_report(db, device.id, before_or_on=requested_date)
        if report is not None:
            used_fallback_report = True
            fallback_reason = "目标日期无可用报告，已回退到最近可用日报"

    if report is None and report_date is not None:
        report = await _get_latest_completed_report(db, device.id, before_or_on=None)
        if report is not None:
            used_fallback_report = True
            fallback_reason = "目标日期之前无可用报告，已回退到全量最近可用日报"

    if not report:
        return AiReportResponse(
            success=False,
            data=None,
            summary=(
                f"{device.name}截至{requested_date}暂无可用AI诊断报告。"
                "请确认每日报告任务已执行，或先调用生成报告接口后重试。"
            ),
        )

    # Parse stats snapshot
    stats = None
    if report.stats_snapshot:
        try:
            stats = json.loads(report.stats_snapshot)
        except (json.JSONDecodeError, TypeError):
            pass

    industry_info = INDUSTRY_STANDARD_MAP.get(device.industry_type or "", {})

    return AiReportResponse(
        success=True,
        data={
            "device_name": device.name,
            "device_mn": device.mn,
            "enterprise": target_org_name,
            "industry_type": industry_info.get("name", device.industry_type or ""),
            "national_standard": device.national_standard or industry_info.get("standard_name", ""),
            "report_date": str(report.report_date),
            "requested_report_date": str(requested_date),
            "actual_report_date": str(report.report_date),
            "used_fallback_report": used_fallback_report,
            "fallback_reason": fallback_reason,
            "report_content": report.report_content or "",
            "report_status": report.status,
            "generated_at": report.generated_at.strftime("%Y-%m-%d %H:%M:%S") if report.generated_at else "",
            "pollutant_count": report.pollutant_count,
            "data_points": report.data_points,
            "domain": report.domain or "",
            "stats_snapshot": stats,
        },
        summary=(
            f"{device.name}（{target_org_name}）{report.report_date}的AI运维诊断报告已生成，"
            f"包含{report.pollutant_count or '多'}项污染物分析"
            + ("（已自动回退到最近可用报告）" if used_fallback_report else "")
            + "。"
        ),
    )
