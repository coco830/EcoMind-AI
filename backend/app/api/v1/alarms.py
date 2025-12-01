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


def _build_org_filter_query(query, current_user: User, join_device: bool = True):
    """Add organization filter to alarm query based on user's org.

    Args:
        query: SQLAlchemy query
        current_user: Current authenticated user
        join_device: Whether to join Device table (set False if already joined via selectinload)
    """
    if current_user.is_superadmin:
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
    if current_user.is_superadmin:
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
    await db.refresh(alarm)

    return AlarmResponse.model_validate(alarm)


@router.post("/{alarm_id}/resolve", response_model=AlarmResponse)
async def resolve_alarm(
    alarm_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_operator)],
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
    await db.refresh(alarm)

    return AlarmResponse.model_validate(alarm)


@router.delete("/{alarm_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alarm(
    alarm_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_operator)],
) -> None:
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
    if not current_user.is_superadmin and current_user.org_id:
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
    if not current_user.is_superadmin and current_user.org_id:
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
