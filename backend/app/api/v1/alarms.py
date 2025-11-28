"""Alarm management API endpoints."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.postgres import get_db
from app.models.alarm import Alarm, AlarmCreate, AlarmResponse, AlarmStatus, AlarmLevel
from app.models.device import Device
from app.models.user import User
from app.api.deps import get_current_active_user, require_operator

router = APIRouter()


def _build_org_filter_query(query, current_user: User):
    """Add organization filter to alarm query based on user's org."""
    if current_user.is_superadmin:
        return query
    if current_user.org_id:
        query = query.join(Device, Alarm.device_id == Device.id).where(
            Device.org_id == current_user.org_id
        )
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
    """List alarms with optional filters. Filtered by user's organization."""
    query = select(Alarm)

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
    """List pending (unacknowledged) alarms. Filtered by user's organization."""
    query = select(Alarm).where(Alarm.status == AlarmStatus.PENDING.value)

    # Apply organization filter
    query = _build_org_filter_query(query, current_user)

    query = query.order_by(Alarm.created_at.desc()).limit(limit)
    result = await db.execute(query)
    alarms = result.scalars().all()

    return [AlarmResponse.model_validate(a) for a in alarms]


async def _check_alarm_access(
    alarm: Alarm,
    current_user: User,
    db: AsyncSession,
) -> None:
    """Check if user has access to the alarm via device's organization."""
    if current_user.is_superadmin:
        return

    if current_user.org_id:
        # Get the device to check org
        result = await db.execute(select(Device).where(Device.id == alarm.device_id))
        device = result.scalar_one_or_none()
        if device and device.org_id != current_user.org_id:
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
    result = await db.execute(select(Alarm).where(Alarm.id == alarm_id))
    alarm = result.scalar_one_or_none()

    if alarm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alarm not found",
        )

    # Check organization access
    await _check_alarm_access(alarm, current_user, db)

    return AlarmResponse.model_validate(alarm)


@router.post("", response_model=AlarmResponse, status_code=status.HTTP_201_CREATED)
async def create_alarm(
    alarm_data: AlarmCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_operator)],
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

    return AlarmResponse.model_validate(alarm)


@router.post("/{alarm_id}/acknowledge", response_model=AlarmResponse)
async def acknowledge_alarm(
    alarm_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_operator)],
) -> AlarmResponse:
    """Acknowledge an alarm. Access controlled by organization."""
    result = await db.execute(select(Alarm).where(Alarm.id == alarm_id))
    alarm = result.scalar_one_or_none()

    if alarm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alarm not found",
        )

    # Check organization access
    await _check_alarm_access(alarm, current_user, db)

    if alarm.status != AlarmStatus.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alarm is not in pending status",
        )

    alarm.status = AlarmStatus.ACKNOWLEDGED.value
    alarm.acknowledged_by = current_user.id
    alarm.acknowledged_at = datetime.utcnow()

    await db.flush()
    await db.refresh(alarm)

    return AlarmResponse.model_validate(alarm)


@router.post("/{alarm_id}/resolve", response_model=AlarmResponse)
async def resolve_alarm(
    alarm_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_operator)],
) -> AlarmResponse:
    """Resolve an alarm. Access controlled by organization."""
    result = await db.execute(select(Alarm).where(Alarm.id == alarm_id))
    alarm = result.scalar_one_or_none()

    if alarm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alarm not found",
        )

    # Check organization access
    await _check_alarm_access(alarm, current_user, db)

    if alarm.status == AlarmStatus.RESOLVED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alarm is already resolved",
        )

    alarm.status = AlarmStatus.RESOLVED.value
    alarm.resolved_at = datetime.utcnow()

    await db.flush()
    await db.refresh(alarm)

    return AlarmResponse.model_validate(alarm)


@router.delete("/{alarm_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alarm(
    alarm_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_operator)],
) -> None:
    """Delete an alarm. Access controlled by organization."""
    result = await db.execute(select(Alarm).where(Alarm.id == alarm_id))
    alarm = result.scalar_one_or_none()

    if alarm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alarm not found",
        )

    # Check organization access
    await _check_alarm_access(alarm, current_user, db)

    await db.delete(alarm)


@router.get("/stats/summary")
async def get_alarm_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> dict:
    """Get alarm statistics summary. Filtered by user's organization."""
    query = select(Alarm)

    # Apply organization filter
    query = _build_org_filter_query(query, current_user)

    result = await db.execute(query)
    alarms = result.scalars().all()

    stats = {
        "total": len(alarms),
        "pending": sum(1 for a in alarms if a.status == AlarmStatus.PENDING.value),
        "acknowledged": sum(1 for a in alarms if a.status == AlarmStatus.ACKNOWLEDGED.value),
        "resolved": sum(1 for a in alarms if a.status == AlarmStatus.RESOLVED.value),
        "by_level": {
            "info": sum(1 for a in alarms if a.level == AlarmLevel.INFO.value),
            "warning": sum(1 for a in alarms if a.level == AlarmLevel.WARNING.value),
            "critical": sum(1 for a in alarms if a.level == AlarmLevel.CRITICAL.value),
        },
    }

    return stats
