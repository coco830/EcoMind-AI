"""Device status tool endpoint for OpenAPI agent integrations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.openapi.auth import ApiClientContext, require_tool_permission, resolve_target_org
from app.api.openapi.schemas import (
    DeviceStatusItem,
    DeviceStatusResponse,
    DeviceStatusSummary,
    DEVICE_TYPE_NAMES,
    DEVICE_STATUS_NAMES,
)
from app.db.postgres import get_db
from app.models.device import Device, INDUSTRY_STANDARD_MAP

router = APIRouter()
logger = structlog.get_logger()


def _format_heartbeat_duration(last_heartbeat: datetime | None) -> str:
    """Format last heartbeat into a human-readable duration string."""
    if not last_heartbeat:
        return "从未通讯"
    now = datetime.now(timezone.utc)
    hb = last_heartbeat if last_heartbeat.tzinfo else last_heartbeat.replace(tzinfo=timezone.utc)
    delta = now - hb
    minutes = int(delta.total_seconds() / 60)
    if minutes < 1:
        return "刚刚"
    if minutes < 60:
        return f"{minutes}分钟前"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}小时前"
    days = hours // 24
    return f"{days}天前"


@router.get(
    "/device/status",
    response_model=DeviceStatusResponse,
    summary="查询设备状态",
    description="查询当前 API Key 绑定企业的所有设备状态，包括在线/离线/报警统计。供智能体了解企业设备运行概况。",
)
async def get_device_status(
    ctx: Annotated[ApiClientContext, Depends(require_tool_permission("get_device_status"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    enterprise_name: str | None = Query(None, description="企业名称（all_orgs Key 必填，支持模糊匹配）"),
    org_id: UUID | None = Query(None, description="组织ID（可选，优先于 enterprise_name）"),
    status_filter: str | None = Query(None, description="按状态筛选: online/offline/alarm/maintenance"),
) -> DeviceStatusResponse:
    """Get device status for the bound organization."""
    target_org_id, target_org_name = await resolve_target_org(
        ctx=ctx,
        db=db,
        enterprise_name=enterprise_name,
        org_id=org_id,
    )

    query = (
        select(Device)
        .options(selectinload(Device.organization))
        .where(Device.org_id == target_org_id)
    )
    if status_filter:
        query = query.where(Device.status == status_filter)

    result = await db.execute(query.order_by(Device.created_at.desc()))
    devices = result.scalars().all()

    # Build LLM-friendly device list
    device_items = []
    status_counts = {"online": 0, "offline": 0, "alarm": 0, "maintenance": 0}

    for d in devices:
        status_counts[d.status] = status_counts.get(d.status, 0) + 1
        industry_info = INDUSTRY_STANDARD_MAP.get(d.industry_type or "", {})

        device_items.append(
            DeviceStatusItem(
                device_name=d.name,
                enterprise=target_org_name,
                device_type=DEVICE_TYPE_NAMES.get(d.device_type, d.device_type),
                status=DEVICE_STATUS_NAMES.get(d.status, d.status),
                industry_type=industry_info.get("name", d.industry_type or ""),
                national_standard=d.national_standard or industry_info.get("standard_name", ""),
                address=d.address or "",
                last_heartbeat=d.last_heartbeat.strftime("%Y-%m-%d %H:%M:%S") if d.last_heartbeat else "",
                online_duration=_format_heartbeat_duration(d.last_heartbeat),
            ).model_dump()
        )

    summary_obj = DeviceStatusSummary(
        total=len(devices),
        online=status_counts.get("online", 0),
        offline=status_counts.get("offline", 0),
        alarm=status_counts.get("alarm", 0),
        maintenance=status_counts.get("maintenance", 0),
    )

    # Generate natural language summary
    parts = []
    parts.append(f"{target_org_name}共有{len(devices)}台监测设备")
    if summary_obj.online:
        parts.append(f"{summary_obj.online}台在线")
    if summary_obj.offline:
        parts.append(f"{summary_obj.offline}台离线")
    if summary_obj.alarm:
        parts.append(f"{summary_obj.alarm}台报警")
    if summary_obj.maintenance:
        parts.append(f"{summary_obj.maintenance}台维护中")
    summary_text = "，".join(parts) + "。"

    return DeviceStatusResponse(
        success=True,
        data={
            "enterprise": target_org_name,
            "devices": device_items,
            "status_summary": summary_obj.model_dump(),
        },
        summary=summary_text,
    )
