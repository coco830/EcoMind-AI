from __future__ import annotations

"""Alarm management API endpoints."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.postgres import get_db
from app.models.alarm import Alarm, AlarmCreate, AlarmResponse, AlarmStatus, AlarmLevel
from app.models.device import Device
from app.models.user import User
from app.api.deps import get_current_active_user, require_superadmin, can_cross_tenant_read
from app.services.openclaw_webhook import get_openclaw_webhook_notifier
from app.services.alarm_service import AlarmService

router = APIRouter()
logger = structlog.get_logger()


def _build_org_filter_query(query, current_user: User, join_device: bool = True):
    """Add organization filter to alarm query based on user's org.

    Args:
        query: SQLAlchemy query
        current_user: Current authenticated user
        join_device: Whether to join Device table (set False if already joined via selectinload)
    """
    if can_cross_tenant_read(current_user):
        return query
    if current_user.org_id:
        if join_device:
            query = query.join(Device, Alarm.device_id == Device.id).where(
                Device.org_id == current_user.org_id
            )
        else:
            query = query.where(Device.org_id == current_user.org_id)
    return query


@router.get("", response_model=list[AlarmResponse])
async def list_alarms(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    device_id: UUID | None = None,
    alarm_status: AlarmStatus | None = None,
    level: AlarmLevel | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> list[AlarmResponse]:
    """List alarms with optional filters. Filtered by user's organization.

    Uses selectinload to eagerly load device relationship, avoiding N+1 queries.
    """
    # Use selectinload to preload device relationship (avoids N+1 queries)
    query = select(Alarm).options(
        selectinload(Alarm.device).selectinload(Device.organization)
    )

    # Apply organization filter
    query = _build_org_filter_query(query, current_user)

    conditions = []
    if device_id:
        conditions.append(Alarm.device_id == device_id)
    if alarm_status:
        conditions.append(Alarm.status == alarm_status.value)
    if level:
        conditions.append(Alarm.level == level.value)
    if start_time:
        conditions.append(Alarm.created_at >= start_time)
    if end_time:
        conditions.append(Alarm.created_at <= end_time)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(Alarm.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    alarms = result.scalars().all()

    return [AlarmResponse.model_validate(a) for a in alarms]


@router.get("/pending", response_model=list[AlarmResponse])
async def list_pending_alarms(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    limit: int = Query(100, ge=1, le=1000),
) -> list[AlarmResponse]:
    """List pending (unacknowledged) alarms. Filtered by user's organization.

    Uses selectinload to eagerly load device relationship, avoiding N+1 queries.
    """
    # Use selectinload to preload device relationship (avoids N+1 queries)
    query = (
        select(Alarm)
        .options(selectinload(Alarm.device).selectinload(Device.organization))
        .where(Alarm.status == AlarmStatus.PENDING.value)
    )

    # Apply organization filter
    query = _build_org_filter_query(query, current_user)

    query = query.order_by(Alarm.created_at.desc()).limit(limit)
    result = await db.execute(query)
    alarms = result.scalars().all()

    return [AlarmResponse.model_validate(a) for a in alarms]


def _check_alarm_access(
    alarm: Alarm,
    current_user: User,
) -> None:
    """Check if user has access to the alarm via device's organization.

    Note: This function expects alarm.device to be preloaded via selectinload
    to avoid N+1 query issues. Use selectinload(Alarm.device) when querying.
    """
    if can_cross_tenant_read(current_user):
        return

    if current_user.org_id:
        # Use preloaded device relationship (avoids N+1 query)
        if alarm.device and alarm.device.org_id != current_user.org_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this alarm",
            )


@router.get("/{alarm_id}", response_model=AlarmResponse)
async def get_alarm(
    alarm_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> AlarmResponse:
    """Get alarm by ID. Access controlled by organization."""
    result = await db.execute(
        select(Alarm)
        .options(selectinload(Alarm.device))
        .where(Alarm.id == alarm_id)
    )
    alarm = result.scalar_one_or_none()

    if alarm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alarm not found",
        )

    # Check organization access (uses preloaded device)
    _check_alarm_access(alarm, current_user)

    return AlarmResponse.model_validate(alarm)


@router.post("", response_model=AlarmResponse, status_code=status.HTTP_201_CREATED)
async def create_alarm(
    alarm_data: AlarmCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superadmin)],
    notify_openclaw: bool = Query(True, description="是否触发 OpenClaw webhook 推送"),
) -> AlarmResponse:
    """Create a new alarm manually."""
    alarm = Alarm(
        device_id=alarm_data.device_id,
        alarm_type=alarm_data.alarm_type.value,
        level=alarm_data.level.value,
        pollutant_code=alarm_data.pollutant_code,
        message=alarm_data.message,
        value=alarm_data.value,
        threshold=alarm_data.threshold,
    )
    db.add(alarm)
    await db.flush()
    await db.refresh(alarm)

    if notify_openclaw:
        try:
            device_result = await db.execute(
                select(Device)
                .options(selectinload(Device.organization))
                .where(Device.id == alarm.device_id)
                .limit(1)
            )
            device = device_result.scalar_one_or_none()
            notifier = get_openclaw_webhook_notifier()
            pushed = await notifier.notify_alarm(alarm, device)
            logger.info(
                "Manual alarm webhook push attempted",
                alarm_id=str(alarm.id),
                pushed=pushed,
                notify_openclaw=notify_openclaw,
            )
        except Exception as exc:
            logger.warning(
                "Manual alarm webhook push failed",
                alarm_id=str(alarm.id),
                error=str(exc),
            )

    device_result = await db.execute(
        select(Device)
        .options(selectinload(Device.organization))
        .where(Device.id == alarm.device_id)
        .limit(1)
    )
    device = device_result.scalar_one_or_none()
    await AlarmService(db).sync_video_events_with_alarm(alarm, device=device)

    return AlarmResponse.model_validate(alarm)


@router.post("/{alarm_id}/acknowledge", response_model=AlarmResponse)
async def acknowledge_alarm(
    alarm_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superadmin)],
) -> AlarmResponse:
    """Acknowledge an alarm. Access controlled by organization."""
    result = await db.execute(
        select(Alarm)
        .options(selectinload(Alarm.device))
        .where(Alarm.id == alarm_id)
    )
    alarm = result.scalar_one_or_none()

    if alarm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alarm not found",
        )

    # Check organization access (uses preloaded device)
    _check_alarm_access(alarm, current_user)

    if alarm.status != AlarmStatus.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alarm is not in pending status",
        )

    alarm.status = AlarmStatus.ACKNOWLEDGED.value
    alarm.acknowledged_by = current_user.id
    alarm.acknowledged_at = datetime.utcnow()

    await db.flush()
    await AlarmService(db).sync_video_events_with_alarm(alarm, device=alarm.device)
    await db.refresh(alarm)

    return AlarmResponse.model_validate(alarm)


@router.post("/{alarm_id}/resolve", response_model=AlarmResponse)
async def resolve_alarm(
    alarm_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superadmin)],
) -> AlarmResponse:
    """Resolve an alarm. Access controlled by organization."""
    result = await db.execute(
        select(Alarm)
        .options(selectinload(Alarm.device))
        .where(Alarm.id == alarm_id)
    )
    alarm = result.scalar_one_or_none()

    if alarm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alarm not found",
        )

    # Check organization access (uses preloaded device)
    _check_alarm_access(alarm, current_user)

    if alarm.status == AlarmStatus.RESOLVED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alarm is already resolved",
        )

    alarm.status = AlarmStatus.RESOLVED.value
    alarm.resolved_at = datetime.utcnow()

    await db.flush()
    await AlarmService(db).sync_video_events_with_alarm(alarm, device=alarm.device)
    await db.refresh(alarm)

    return AlarmResponse.model_validate(alarm)


@router.delete("/{alarm_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_alarm(
    alarm_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superadmin)],
):
    """Delete an alarm. Access controlled by organization."""
    result = await db.execute(
        select(Alarm)
        .options(selectinload(Alarm.device))
        .where(Alarm.id == alarm_id)
    )
    alarm = result.scalar_one_or_none()

    if alarm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alarm not found",
        )

    # Check organization access (uses preloaded device)
    _check_alarm_access(alarm, current_user)

    await db.delete(alarm)


@router.get("/stats/summary")
async def get_alarm_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> dict:
    """Get alarm statistics summary. Filtered by user's organization.

    Uses database-level aggregation for better performance instead of loading all rows.
    """
    from sqlalchemy import case, func as sql_func

    # Base query with organization filter
    base_query = select(Alarm.id)
    if (not can_cross_tenant_read(current_user)) and current_user.org_id:
        base_query = base_query.join(Device, Alarm.device_id == Device.id).where(
            Device.org_id == current_user.org_id
        )

    # Count by status using database aggregation
    status_query = (
        select(
            sql_func.count().label("total"),
            sql_func.count().filter(Alarm.status == AlarmStatus.PENDING.value).label("pending"),
            sql_func.count().filter(Alarm.status == AlarmStatus.ACKNOWLEDGED.value).label("acknowledged"),
            sql_func.count().filter(Alarm.status == AlarmStatus.RESOLVED.value).label("resolved"),
            sql_func.count().filter(Alarm.level == AlarmLevel.INFO.value).label("info"),
            sql_func.count().filter(Alarm.level == AlarmLevel.WARNING.value).label("warning"),
            sql_func.count().filter(Alarm.level == AlarmLevel.CRITICAL.value).label("critical"),
        )
    )

    # Apply organization filter
    if (not can_cross_tenant_read(current_user)) and current_user.org_id:
        status_query = status_query.select_from(Alarm).join(
            Device, Alarm.device_id == Device.id
        ).where(Device.org_id == current_user.org_id)
    else:
        status_query = status_query.select_from(Alarm)

    result = await db.execute(status_query)
    row = result.one()

    stats = {
        "total": row.total or 0,
        "pending": row.pending or 0,
        "acknowledged": row.acknowledged or 0,
        "resolved": row.resolved or 0,
        "by_level": {
            "info": row.info or 0,
            "warning": row.warning or 0,
            "critical": row.critical or 0,
        },
    }

    return stats
