from __future__ import annotations

"""Organization management API endpoints (Superadmin only)."""

from typing import Annotated
import hashlib
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db
from app.models.organization import Organization, OrganizationCreate, OrganizationResponse, OrganizationStatus
from app.models.user import User
from app.models.device import Device
from app.api.deps import require_superadmin, require_platform_staff_read

router = APIRouter()


class OrganizationUpdate(BaseModel):
    """Schema for updating an organization."""

    name: str | None = Field(None, min_length=1, max_length=255)
    address: str | None = Field(None, max_length=512)
    contact_name: str | None = Field(None, max_length=64)
    contact_phone: str | None = Field(None, max_length=20)
    org_type: str | None = Field(None, max_length=32)
    region_code: str | None = Field(None, max_length=64)
    region_name: str | None = Field(None, max_length=128)
    park_code: str | None = Field(None, max_length=64)
    park_name: str | None = Field(None, max_length=128)
    industry_type: str | None = Field(None, max_length=64)
    jurisdiction_level: str | None = Field(None, max_length=32)
    jurisdiction_codes: str | None = Field(None, description="JSON string of jurisdiction codes")


class OrganizationWithStats(OrganizationResponse):
    """Organization response with statistics."""

    user_count: int = 0
    device_count: int = 0


def _mask_org_name(org: Organization) -> str:
    # Stable pseudonym for sales demos
    seed = (str(org.id) + "|" + (org.code or "")).encode("utf-8")
    suffix = hashlib.sha256(seed).hexdigest()[:6].upper()
    return f"企业-{suffix}"


def _to_org_response(org: Organization, *, mask: bool) -> OrganizationResponse:
    if not mask:
        return OrganizationResponse.model_validate(org)
    # Mask identity fields for sales role
    return OrganizationResponse(
        id=org.id,
        name=_mask_org_name(org),
        code=f"ORG-{str(org.id)[-6:]}",
        address=None,
        contact_name=None,
        contact_phone=None,
        status=org.status,
        created_at=org.created_at,
        updated_at=org.updated_at,
    )


@router.get("", response_model=list[OrganizationResponse])
async def list_organizations(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_platform_staff_read)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    include_inactive: bool = Query(False, description="Include inactive organizations"),
) -> list[OrganizationResponse]:
    """List all organizations (superadmin only).

    By default only returns active organizations.
    Set include_inactive=true to include all organizations.
    """
    query = select(Organization)

    # By default, only return active organizations
    if not include_inactive:
        query = query.where(Organization.status == OrganizationStatus.ACTIVE.value)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    organizations = result.scalars().all()

    mask = (not current_user.is_superadmin) and (current_user.role == "viewer")
    return [_to_org_response(org, mask=mask) for org in organizations]


@router.get("/{org_id}", response_model=OrganizationWithStats)
async def get_organization(
    org_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_platform_staff_read)],
) -> OrganizationWithStats:
    """Get organization by ID with statistics (superadmin only)."""
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()

    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Get user count
    user_count_result = await db.execute(
        select(func.count()).select_from(User).where(User.org_id == org_id)
    )
    user_count = user_count_result.scalar() or 0

    # Get device count
    device_count_result = await db.execute(
        select(func.count()).select_from(Device).where(Device.org_id == org_id)
    )
    device_count = device_count_result.scalar() or 0

    mask = (not current_user.is_superadmin) and (current_user.role == "viewer")
    if mask:
        masked = _to_org_response(org, mask=True)
        return OrganizationWithStats(
            id=masked.id,
            name=masked.name,
            code=masked.code,
            address=masked.address,
            contact_name=masked.contact_name,
            contact_phone=masked.contact_phone,
            status=masked.status,
            created_at=masked.created_at,
            updated_at=masked.updated_at,
            user_count=user_count,
            device_count=device_count,
        )

    return OrganizationWithStats(
        id=org.id,
        name=org.name,
        code=org.code,
        address=org.address,
        contact_name=org.contact_name,
        contact_phone=org.contact_phone,
        status=org.status,
        created_at=org.created_at,
        updated_at=org.updated_at,
        user_count=user_count,
        device_count=device_count,
    )


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    org_data: OrganizationCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superadmin)],
) -> OrganizationResponse:
    """Create a new organization (superadmin only)."""
    # Check if code already exists
    result = await db.execute(
        select(Organization).where(Organization.code == org_data.code)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization with this code already exists",
        )

    org = Organization(
        name=org_data.name,
        code=org_data.code,
        address=org_data.address,
        contact_name=org_data.contact_name,
        contact_phone=org_data.contact_phone,
        org_type=org_data.org_type.value if hasattr(org_data.org_type, "value") else org_data.org_type,
        region_code=org_data.region_code,
        region_name=org_data.region_name,
        park_code=org_data.park_code,
        park_name=org_data.park_name,
        industry_type=org_data.industry_type,
        jurisdiction_level=org_data.jurisdiction_level,
        jurisdiction_codes=org_data.jurisdiction_codes,
    )
    db.add(org)
    await db.flush()
    await db.refresh(org)

    return OrganizationResponse.model_validate(org)


@router.put("/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: UUID,
    org_data: OrganizationUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superadmin)],
) -> OrganizationResponse:
    """Update an organization (superadmin only)."""
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()

    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Update fields if provided
    if org_data.name is not None:
        org.name = org_data.name
    if org_data.address is not None:
        org.address = org_data.address
    if org_data.contact_name is not None:
        org.contact_name = org_data.contact_name
    if org_data.contact_phone is not None:
        org.contact_phone = org_data.contact_phone
    if org_data.org_type is not None:
        org.org_type = org_data.org_type
    if org_data.region_code is not None:
        org.region_code = org_data.region_code
    if org_data.region_name is not None:
        org.region_name = org_data.region_name
    if org_data.park_code is not None:
        org.park_code = org_data.park_code
    if org_data.park_name is not None:
        org.park_name = org_data.park_name
    if org_data.industry_type is not None:
        org.industry_type = org_data.industry_type
    if org_data.jurisdiction_level is not None:
        org.jurisdiction_level = org_data.jurisdiction_level
    if org_data.jurisdiction_codes is not None:
        org.jurisdiction_codes = org_data.jurisdiction_codes

    await db.flush()
    await db.refresh(org)

    return OrganizationResponse.model_validate(org)


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_organization(
    org_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superadmin)],
):
    """Delete an organization (superadmin only). Fails if org has users or devices."""
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()

    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Check for associated users
    user_count_result = await db.execute(
        select(func.count()).select_from(User).where(User.org_id == org_id)
    )
    user_count = user_count_result.scalar() or 0
    if user_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete organization with {user_count} associated users",
        )

    # Check for associated devices
    device_count_result = await db.execute(
        select(func.count()).select_from(Device).where(Device.org_id == org_id)
    )
    device_count = device_count_result.scalar() or 0
    if device_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete organization with {device_count} associated devices",
        )

    await db.delete(org)


@router.get("/{org_id}/users", response_model=list)
async def list_organization_users(
    org_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superadmin)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> list:
    """List users belonging to an organization (superadmin only)."""
    from app.models.user import UserResponse

    # Check org exists
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    query = select(User).where(User.org_id == org_id).offset(skip).limit(limit)
    result = await db.execute(query)
    users = result.scalars().all()

    return [UserResponse.model_validate(u) for u in users]


@router.get("/{org_id}/devices", response_model=list)
async def list_organization_devices(
    org_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superadmin)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> list:
    """List devices belonging to an organization (superadmin only)."""
    from app.models.device import DeviceResponse

    # Check org exists
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    query = select(Device).where(Device.org_id == org_id).offset(skip).limit(limit)
    result = await db.execute(query)
    devices = result.scalars().all()

    # Simple conversion without threshold parsing for listing
    return [
        {
            "id": d.id,
            "mn": d.mn,
            "name": d.name,
            "device_type": d.device_type,
            "status": d.status,
            "org_id": d.org_id,
            "created_at": d.created_at,
            "updated_at": d.updated_at,
        }
        for d in devices
    ]
