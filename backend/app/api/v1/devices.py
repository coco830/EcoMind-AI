from __future__ import annotations

"""Device management API endpoints."""

import json
import hashlib
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.postgres import get_db
from app.core.masking import is_demo_viewer, mask_device_name
from app.models.device import (
    Device, DeviceCreate, DeviceResponse, DeviceStatus, DeviceType,
    IndustryType, ThresholdConfig, INDUSTRY_STANDARD_MAP
)
from app.models.organization import Organization
from app.models.user import User
from app.api.deps import get_current_active_user, require_superadmin, can_cross_tenant_read

router = APIRouter()


def _serialize_thresholds(thresholds: ThresholdConfig | None) -> str | None:
    """Serialize threshold config to JSON string."""
    if thresholds is None:
        return None
    return thresholds.model_dump_json()


def _deserialize_thresholds(thresholds_json: str | None) -> ThresholdConfig | None:
    """Deserialize threshold config from JSON string."""
    if not thresholds_json:
        return None
    try:
        data = json.loads(thresholds_json)
        return ThresholdConfig.model_validate(data)
    except (json.JSONDecodeError, ValueError):
        return None


def _device_to_response(device: Device, *, mask: bool = False) -> DeviceResponse:
    """Convert Device ORM model to DeviceResponse with threshold parsing."""
    # Parse pollutant_codes
    pollutant_codes = None
    if device.pollutant_codes:
        pollutant_codes = [c.strip() for c in device.pollutant_codes.split(",") if c.strip()]

    # Parse thresholds
    thresholds = _deserialize_thresholds(device.thresholds)

    # Parse industry_type if present
    industry_type = None
    if device.industry_type:
        try:
            industry_type = IndustryType(device.industry_type)
        except ValueError:
            pass

    name = device.name
    address = device.address
    latitude = device.latitude
    longitude = device.longitude
    if mask:
        name = mask_device_name(device_id=str(device.id), mn=device.mn)
        address = None
        latitude = None
        longitude = None

    return DeviceResponse(
        id=device.id,
        mn=device.mn,
        name=name,
        device_type=DeviceType(device.device_type),
        status=DeviceStatus(device.status),
        org_id=device.org_id,
        industry_type=industry_type,
        national_standard=device.national_standard,
        latitude=latitude,
        longitude=longitude,
        address=address,
        pollutant_codes=pollutant_codes,
        thresholds=thresholds,
        last_heartbeat=device.last_heartbeat,
        created_at=device.created_at,
        updated_at=device.updated_at,
    )


class DeviceListResponse:
    """Paginated device list response."""

    items: list[DeviceResponse]
    total: int
    page: int
    page_size: int


@router.get("/industry-types")
async def get_industry_types() -> list[dict]:
    """Get list of available industry types with their default standards.

    Returns a list of industry types with name, code, and associated standard.
    """
    result = []
    for code, info in INDUSTRY_STANDARD_MAP.items():
        result.append({
            "code": code,
            "name": info["name"],
            "standard": info["standard"],
            "standard_name": info["standard_name"],
        })
    return result


@router.get("/stats/summary")
async def get_device_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> dict:
    """Get device statistics summary.

    Uses database-level aggregation for better performance instead of loading all rows.
    """
    from sqlalchemy import func

    # Use database aggregation instead of loading all devices
    status_query = select(
        func.count().label("total"),
        func.count().filter(Device.status == DeviceStatus.ONLINE.value).label("online"),
        func.count().filter(Device.status == DeviceStatus.OFFLINE.value).label("offline"),
        func.count().filter(Device.status == DeviceStatus.ALARM.value).label("alarm"),
        func.count().filter(Device.status == DeviceStatus.MAINTENANCE.value).label("maintenance"),
    ).select_from(Device)

    # Superadmin/platform staff can see all devices, tenant users only see their org's devices
    if not can_cross_tenant_read(current_user) and current_user.org_id:
        status_query = status_query.where(Device.org_id == current_user.org_id)

    result = await db.execute(status_query)
    row = result.one()

    stats = {
        "total": row.total or 0,
        "online": row.online or 0,
        "offline": row.offline or 0,
        "alarm": row.alarm or 0,
        "maintenance": row.maintenance or 0,
    }

    return stats


@router.get("", response_model=list[DeviceResponse])
async def list_devices(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    org_id: UUID | None = None,
    device_status: DeviceStatus | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> list[DeviceResponse]:
    """List devices with optional filters.

    Uses selectinload to eagerly load organization relationship, avoiding N+1 queries.
    """
    # Use selectinload to preload organization relationship (avoids N+1 queries)
    query = select(Device).options(selectinload(Device.organization))

    # Superadmin/platform staff can see all devices (optionally filtered by org_id)
    # Tenant users can only see their organization's devices
    if can_cross_tenant_read(current_user):
        if org_id:
            query = query.where(Device.org_id == org_id)
    elif current_user.org_id:
        query = query.where(Device.org_id == current_user.org_id)

    if device_status:
        query = query.where(Device.status == device_status.value)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    devices = result.scalars().all()

    mask = is_demo_viewer(current_user) and can_cross_tenant_read(current_user)
    return [_device_to_response(d, mask=mask) for d in devices]


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> DeviceResponse:
    """Get device by ID."""
    result = await db.execute(
        select(Device)
        .options(selectinload(Device.organization))
        .where(Device.id == device_id)
    )
    device = result.scalar_one_or_none()

    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    # Check organization access (platform staff can read cross-tenant)
    if (not can_cross_tenant_read(current_user)) and current_user.org_id and device.org_id != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this device",
        )

    mask = is_demo_viewer(current_user) and can_cross_tenant_read(current_user)
    return _device_to_response(device, mask=mask)


@router.post("", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def create_device(
    device_data: DeviceCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superadmin)],
) -> DeviceResponse:
    """Create a new device. Non-superadmin users can only create devices in their own org."""
    import structlog
    logger = structlog.get_logger()
    logger.info("Creating device", mn=device_data.mn, name=device_data.name, org_id=str(device_data.org_id) if device_data.org_id else "None", user_org=str(current_user.org_id) if current_user.org_id else "None")

    # Determine the organization ID first
    org_id = device_data.org_id

    # If org_id not provided
    if org_id is None:
        if current_user.is_superadmin:
            # Superadmin must specify org_id when creating devices
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Superadmin must specify org_id when creating devices",
            )
        elif current_user.org_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User must belong to an organization to create devices",
            )
        else:
            org_id = current_user.org_id

    # Check organization access for non-superadmin users
    if not current_user.is_superadmin:
        if current_user.org_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User must belong to an organization",
            )
        if org_id != current_user.org_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot create device for another organization",
            )

    # Check if MN already exists WITHIN THE SAME ORGANIZATION (multi-tenant isolation)
    result = await db.execute(
        select(Device).where(Device.mn == device_data.mn, Device.org_id == org_id)
    )
    if result.scalar_one_or_none():
        logger.warning("Device MN already exists in organization", mn=device_data.mn, org_id=str(org_id))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Device with this MN already exists in your organization",
        )

    # Determine national_standard if industry_type is provided
    national_standard = device_data.national_standard
    if device_data.industry_type and not national_standard:
        # Auto-fill national_standard from industry type mapping
        industry_info = INDUSTRY_STANDARD_MAP.get(device_data.industry_type.value)
        if industry_info:
            national_standard = industry_info.get("standard")

    device = Device(
        mn=device_data.mn,
        name=device_data.name,
        device_type=device_data.device_type.value,
        org_id=org_id,
        industry_type=device_data.industry_type.value if device_data.industry_type else None,
        national_standard=national_standard,
        latitude=device_data.latitude,
        longitude=device_data.longitude,
        address=device_data.address,
        pollutant_codes=",".join(device_data.pollutant_codes) if device_data.pollutant_codes else None,
        thresholds=_serialize_thresholds(device_data.thresholds),
    )
    db.add(device)
    await db.flush()
    await db.refresh(device)

    return _device_to_response(device)


@router.put("/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: UUID,
    device_data: DeviceCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superadmin)],
) -> DeviceResponse:
    """Update an existing device. Users can only update devices in their organization."""
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()

    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    # Check organization access for existing device
    if not current_user.is_superadmin:
        if current_user.org_id is None or device.org_id != current_user.org_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this device",
            )
        # Also prevent changing device to another organization
        if device_data.org_id != current_user.org_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot transfer device to another organization",
            )

    # Determine national_standard if industry_type is provided
    national_standard = device_data.national_standard
    if device_data.industry_type and not national_standard:
        # Auto-fill national_standard from industry type mapping
        industry_info = INDUSTRY_STANDARD_MAP.get(device_data.industry_type.value)
        if industry_info:
            national_standard = industry_info.get("standard")

    # Update fields
    device.mn = device_data.mn
    device.name = device_data.name
    device.device_type = device_data.device_type.value
    device.org_id = device_data.org_id
    device.industry_type = device_data.industry_type.value if device_data.industry_type else None
    device.national_standard = national_standard
    device.latitude = device_data.latitude
    device.longitude = device_data.longitude
    device.address = device_data.address
    device.pollutant_codes = ",".join(device_data.pollutant_codes) if device_data.pollutant_codes else None
    device.thresholds = _serialize_thresholds(device_data.thresholds)

    await db.flush()
    await db.refresh(device)

    return _device_to_response(device)


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_device(
    device_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superadmin)],
):
    """Delete a device. Users can only delete devices in their organization."""
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()

    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    # Check organization access
    if not current_user.is_superadmin:
        if current_user.org_id is None or device.org_id != current_user.org_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this device",
            )

    await db.delete(device)
