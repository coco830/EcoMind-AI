"""Active alarms tool endpoint for OpenAPI agent integrations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.openapi.auth import ApiClientContext, require_tool_permission, resolve_target_org
from app.api.openapi.schemas import (
    ActiveAlarmsResponse,
    AlarmItem,
    AlarmsSummary,
    ALARM_TYPE_NAMES,
    ALARM_LEVEL_NAMES,
)
from app.core.pollutant_library import get_pollutant_name
from app.db.postgres import get_db
from app.models.alarm import Alarm, AlarmStatus, AlarmLevel
from app.models.device import Device
from app.services.alarm_service import AlarmService

router = APIRouter()
logger = structlog.get_logger()


def _format_duration(created_at: datetime) -> str:
    """Format alarm duration as human-readable string."""
    now = datetime.now(timezone.utc)
    ca = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
    delta = now - ca
    minutes = int(delta.total_seconds() / 60)
    if minutes < 1:
        return "刚刚发生"
    if minutes < 60:
        return f"持续{minutes}分钟"
    hours = minutes // 60
    if hours < 24:
        remaining = minutes % 60
        return f"持续{hours}小时{remaining}分钟"
    days = hours // 24
    return f"持续{days}天"


@router.get(
    "/alarm/active",
    response_model=ActiveAlarmsResponse,
    summary="查询当前活跃报警",
    description="获取当前未处理的报警列表，包含报警详情、严重程度和持续时长。供智能体了解企业当前报警情况并协助处置。",
)
async def get_active_alarms(
    ctx: Annotated[ApiClientContext, Depends(require_tool_permission("get_active_alarms"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    enterprise_name: str | None = Query(None, description="企业名称（all_orgs Key 必填，支持模糊匹配）"),
    org_id: UUID | None = Query(None, description="组织ID（可选，优先于 enterprise_name）"),
    level: str | None = Query(None, description="按严重程度筛选: info/warning/critical"),
    limit: int = Query(20, ge=1, le=100, description="返回数量上限"),
) -> ActiveAlarmsResponse:
    """Get active (pending) alarms for the bound organization."""
    target_org_id, target_org_name = await resolve_target_org(
        ctx=ctx,
        db=db,
        enterprise_name=enterprise_name,
        org_id=org_id,
    )

    query = (
        select(Alarm)
        .join(Device, Alarm.device_id == Device.id)
        .options(selectinload(Alarm.device).selectinload(Device.organization))
        .where(
            and_(
                Device.org_id == target_org_id,
                Alarm.status == AlarmStatus.PENDING.value,
            )
        )
    )
    if level:
        query = query.where(Alarm.level == level)

    query = query.order_by(Alarm.created_at.desc()).limit(limit)
    result = await db.execute(query)
    alarms = result.scalars().all()

    # Build LLM-friendly alarm list
    alarm_items: list[dict] = []
    level_counts = {"critical": 0, "warning": 0, "info": 0}

    for a in alarms:
        level_counts[a.level] = level_counts.get(a.level, 0) + 1
        device = a.device
        device_name = device.name if device else "未知设备"

        pollutant_display = ""
        if a.pollutant_code:
            pollutant_display = get_pollutant_name(a.pollutant_code)

        alarm_items.append(
            AlarmItem(
                alarm_id=str(a.id),
                device_name=device_name,
                enterprise=target_org_name,
                alarm_type=ALARM_TYPE_NAMES.get(a.alarm_type, a.alarm_type),
                severity=ALARM_LEVEL_NAMES.get(a.level, a.level),
                pollutant=pollutant_display,
                message=a.message,
                current_value=a.value or "",
                threshold=a.threshold or "",
                created_at=a.created_at.strftime("%Y-%m-%d %H:%M:%S") if a.created_at else "",
                duration=_format_duration(a.created_at) if a.created_at else "",
            ).model_dump()
        )

    summary_obj = AlarmsSummary(
        total_pending=len(alarms),
        critical=level_counts.get("critical", 0),
        warning=level_counts.get("warning", 0),
        info=level_counts.get("info", 0),
    )

    # Natural language summary
    if not alarms:
        summary_text = f"{target_org_name}当前没有未处理的报警，设备运行正常。"
    else:
        parts = [f"{target_org_name}当前有{len(alarms)}条未处理报警"]
        if summary_obj.critical:
            parts.append(f"其中{summary_obj.critical}条严重")
        if summary_obj.warning:
            parts.append(f"{summary_obj.warning}条警告")
        summary_text = "，".join(parts) + "，建议尽快处理。"

    return ActiveAlarmsResponse(
        success=True,
        data={
            "enterprise": target_org_name,
            "alarms": alarm_items,
            "summary": summary_obj.model_dump(),
        },
        summary=summary_text,
    )


@router.post(
    "/alarm/acknowledge",
    response_model=ActiveAlarmsResponse,
    summary="确认报警",
    description="确认（处理）一条报警记录，将其状态从'待处理'更新为'已确认'。",
)
async def acknowledge_alarm(
    ctx: Annotated[ApiClientContext, Depends(require_tool_permission("acknowledge_alarm"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    enterprise_name: str | None = Query(None, description="企业名称（all_orgs Key 必填，支持模糊匹配）"),
    org_id: UUID | None = Query(None, description="组织ID（可选，优先于 enterprise_name）"),
    alarm_id: str = Query(..., description="报警记录ID"),
) -> ActiveAlarmsResponse:
    """Acknowledge a pending alarm."""
    target_org_id, _ = await resolve_target_org(
        ctx=ctx,
        db=db,
        enterprise_name=enterprise_name,
        org_id=org_id,
    )

    try:
        alarm_uuid = UUID(alarm_id)
    except ValueError:
        return ActiveAlarmsResponse(
            success=False, data=None,
            summary=f"无效的报警ID格式: {alarm_id}",
        )

    result = await db.execute(
        select(Alarm)
        .join(Device, Alarm.device_id == Device.id)
        .options(selectinload(Alarm.device))
        .where(and_(Alarm.id == alarm_uuid, Device.org_id == target_org_id))
    )
    alarm = result.scalar_one_or_none()

    if not alarm:
        return ActiveAlarmsResponse(
            success=False, data=None,
            summary="未找到该报警记录，可能不属于当前企业或ID不正确",
        )

    if alarm.status != AlarmStatus.PENDING.value:
        return ActiveAlarmsResponse(
            success=False, data=None,
            summary=f"该报警已处于'{alarm.status}'状态，无需重复确认",
        )

    alarm.status = AlarmStatus.ACKNOWLEDGED.value
    alarm.acknowledged_at = datetime.now(timezone.utc)
    await db.commit()
    await AlarmService(db).sync_video_events_with_alarm(alarm, device=alarm.device)

    device_name = alarm.device.name if alarm.device else "未知设备"
    return ActiveAlarmsResponse(
        success=True,
        data={"alarm_id": alarm_id, "new_status": "已确认"},
        summary=f"已成功确认报警「{device_name} - {alarm.message[:30]}」，状态已更新为'已确认'。",
    )
