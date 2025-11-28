"""Organization management API endpoints (Superadmin only)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db
from app.models.organization import Organization, OrganizationCreate, OrganizationResponse
from app.models.user import User
from app.models.device import Device
from app.api.deps import require_superadmin

router = APIRouter()


class OrganizationUpdate(BaseModel):
    """Schema for updating an organization."""

    name: str | None = Field(None, min_length=1, max_length=255)
    address: str | None = Field(None, max_length=512)
    contact_name: str | None = Field(None, max_length=64)
    contact_phone: str | None = Field(None, max_length=20)


class OrganizationWithStats(OrganizationResponse):
    """Organization response with statistics."""

    user_count: int = 0
    device_count: int = 0


@router.get("", response_model=list[OrganizationResponse])
async def list_organizations(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superadmin)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> list[OrganizationResponse]:
    """List all organizations (superadmin only)."""
    query = select(Organization).offset(skip).limit(limit)
    result = await db.execute(query)
    organizations = result.scalars().all()

    return [OrganizationResponse.model_validate(org) for org in organizations]


@router.get("/{org_id}", response_model=OrganizationWithStats)
async def get_organization(
    org_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superadmin)],
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

    return OrganizationWithStats(
        id=org.id,
        name=org.name,
        code=org.code,
        address=org.address,
        contact_name=org.contact_name,
        contact_phone=org.contact_phone,
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

    await db.flush()
    await db.refresh(org)

    return OrganizationResponse.model_validate(org)


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    org_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superadmin)],
) -> None:
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
