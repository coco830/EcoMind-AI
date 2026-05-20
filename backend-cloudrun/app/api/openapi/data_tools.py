"""Latest monitoring data tool endpoint for OpenAPI agent integrations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.openapi.auth import ApiClientContext, require_tool_permission, resolve_target_org
from app.api.openapi.schemas import (
    LatestDataResponse,
    PollutantReading,
    FLAG_DESCRIPTIONS,
)
from app.core.pollutant_library import get_pollutant_info, get_pollutant_name, normalize_pollutant_code
from app.db.postgres import get_db
from app.models.device import Device, ThresholdConfig, INDUSTRY_STANDARD_MAP
from app.services.monitoring_service import MonitoringService

router = APIRouter()
logger = structlog.get_logger()


def _assess_compliance(value: float, threshold: float | None) -> tuple[str, str, str]:
    """Assess compliance status. Returns (status, risk_level, percentage)."""
    if threshold is None or threshold <= 0:
        return "未设定标准", "normal", ""
    pct = value / threshold * 100
    pct_str = f"{pct:.1f}%"
    if pct >= 100:
        return "超标", "critical", pct_str
    if pct >= 80:
        return "接近超标", "warning", pct_str
    return "达标", "normal", pct_str


@router.get(
    "/data/latest",
    response_model=LatestDataResponse,
    summary="查询最新监测数据",
    description="获取指定设备的最新各项污染物监测数据，包含达标状态和风险评估。供智能体了解企业当前排放情况。",
)
async def get_latest_data(
    ctx: Annotated[ApiClientContext, Depends(require_tool_permission("get_latest_data"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    enterprise_name: str | None = Query(None, description="企业名称（all_orgs Key 必填，支持模糊匹配）"),
    org_id: UUID | None = Query(None, description="组织ID（可选，优先于 enterprise_name）"),
    device_name: str | None = Query(None, description="设备名称（模糊匹配）"),
    device_mn: str | None = Query(None, description="设备MN号（精确匹配）"),
) -> LatestDataResponse:
    """Get latest monitoring data for a device."""
    target_org_id, target_org_name = await resolve_target_org(
        ctx=ctx,
        db=db,
        enterprise_name=enterprise_name,
        org_id=org_id,
    )

    # Find the target device
    query = (
        select(Device)
        .options(selectinload(Device.organization))
        .where(Device.org_id == target_org_id)
    )
    if device_mn:
        query = query.where(Device.mn == device_mn)
    elif device_name:
        query = query.where(Device.name.contains(device_name))
    # Default: return first matched device of the org
    query = query.order_by(Device.created_at.asc()).limit(1)

    result = await db.execute(query)
    device = result.scalars().first()

    if not device:
        return LatestDataResponse(
            success=False,
            data=None,
            summary=f"未找到匹配的设备（企业：{target_org_name}）",
        )

    # Parse thresholds
    thresholds_map: dict[str, float] = {}
    if device.thresholds:
        try:
            tc = ThresholdConfig.model_validate_json(device.thresholds)
            for pt in tc.pollutants:
                if pt.enabled:
                    thresholds_map[normalize_pollutant_code(pt.pollutant_code)] = pt.alarm_value
        except Exception:
            pass

    # Query latest data via MonitoringService
    svc = MonitoringService(db)
    latest_rows = await svc.get_latest_values(
        device_ids=[device.mn],
        org_id=str(target_org_id),
    )

    # Build LLM-friendly readings
    readings: list[dict] = []
    exceed_count = 0
    warning_count = 0

    for row in latest_rows:
        code = normalize_pollutant_code(row.get("pollutant_code", ""))
        value = row.get("value", 0.0)
        flag = row.get("flag", "N")
        ts = row.get("ts")

        pol_info = get_pollutant_info(code)
        pol_name = pol_info["name"] if pol_info else code
        unit = pol_info["unit"] if pol_info else ""

        threshold = thresholds_map.get(code)
        comp_status, risk_level, pct_str = _assess_compliance(value, threshold)

        if risk_level == "critical":
            exceed_count += 1
        elif risk_level == "warning":
            warning_count += 1

        readings.append(
            PollutantReading(
                pollutant=pol_name,
                pollutant_code=code,
                current_value=round(value, 4),
                unit=unit,
                threshold=threshold,
                compliance_status=comp_status,
                risk_level=risk_level,
                percentage_of_limit=pct_str,
                data_quality=FLAG_DESCRIPTIONS.get(flag, f"标记: {flag}"),
                measurement_time=ts.strftime("%Y-%m-%d %H:%M:%S") if isinstance(ts, datetime) else str(ts or ""),
            ).model_dump()
        )

    # Industry standard info
    industry_info = INDUSTRY_STANDARD_MAP.get(device.industry_type or "", {})
    standard_name = device.national_standard or industry_info.get("standard_name", "")

    # Summary
    parts = [f"{device.name}（{target_org_name}）当前共监测{len(readings)}项指标"]
    if exceed_count:
        parts.append(f"{exceed_count}项超标")
    if warning_count:
        parts.append(f"{warning_count}项接近超标")
    if not exceed_count and not warning_count:
        parts.append("全部达标")
    summary_text = "，".join(parts) + "。"

    return LatestDataResponse(
        success=True,
        data={
            "device_name": device.name,
            "device_mn": device.mn,
            "enterprise": target_org_name,
            "industry_type": industry_info.get("name", device.industry_type or ""),
            "national_standard": standard_name,
            "readings": readings,
            "exceed_count": exceed_count,
            "warning_count": warning_count,
        },
        summary=summary_text,
    )
