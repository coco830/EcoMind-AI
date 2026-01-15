"""Invitation code management API endpoints.

Only superadmin users can manage invitation codes.
Each invitation code is bound to a specific organization.
"""

import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.postgres import get_db
from app.models.invitation import (
    InvitationCode,
    InvitationCodeCreate,
    InvitationCodeResponse,
    InvitationCodeUpdate,
    InvitationStatus,
)
from app.models.organization import Organization, OrganizationStatus
from app.models.user import User
from app.models.device import Device
from app.models.self_inspection import SelfInspectionReport, SelfInspectionData
from app.api.deps import get_current_active_user
import structlog

logger = structlog.get_logger()

router = APIRouter()


def require_superadmin(current_user: User = Depends(get_current_active_user)) -> User:
    """Dependency to require superadmin role."""
    if not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superadmin can manage invitation codes",
        )
    return current_user


def generate_invitation_code(length: int = 12) -> str:
    """Generate a random invitation code.

    Format: XXXX-XXXX-XXXX (uppercase letters and digits)
    """
    chars = string.ascii_uppercase + string.digits
    # Remove confusing characters
    chars = chars.replace('O', '').replace('0', '').replace('I', '').replace('1', '').replace('L', '')

    code_parts = []
    for _ in range(3):
        part = ''.join(secrets.choice(chars) for _ in range(4))
        code_parts.append(part)

    return '-'.join(code_parts)


def _invitation_to_response(invitation: InvitationCode) -> InvitationCodeResponse:
    """Convert InvitationCode ORM to response model with org_name."""
    return InvitationCodeResponse(
        id=invitation.id,
        code=invitation.code,
        name=invitation.name,
        description=invitation.description,
        org_id=invitation.org_id,
        org_name=invitation.organization.name if invitation.organization else None,
        max_uses=invitation.max_uses,
        used_count=invitation.used_count,
        expires_at=invitation.expires_at,
        status=InvitationStatus(invitation.status),
        is_active=invitation.is_active,
        created_at=invitation.created_at,
        updated_at=invitation.updated_at,
    )


@router.post("", response_model=InvitationCodeResponse, status_code=status.HTTP_201_CREATED)
async def create_invitation_code(
    data: InvitationCodeCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superadmin)],
) -> InvitationCodeResponse:
    """Create a new invitation code with associated organization.

    Only superadmin can create invitation codes.
    Creates a new organization bound to this invitation code.
    All users registering with this code will join the same organization.
    """
    # Generate unique invitation code
    for _ in range(10):
        code = generate_invitation_code()
        result = await db.execute(
            select(InvitationCode).where(InvitationCode.code == code)
        )
        if not result.scalar_one_or_none():
            break
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate unique invitation code",
        )

    # Create organization for this invitation code
    org_code = f"ORG_{uuid4().hex[:8].upper()}"
    organization = Organization(
        name=data.name,
        code=org_code,
        address="",
        contact_name="",
        contact_phone="",
    )
    db.add(organization)
    await db.flush()
    await db.refresh(organization)

    # Calculate expiration time
    expires_at = None
    if data.expires_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=data.expires_days)

    # Create invitation code bound to the organization
    invitation = InvitationCode(
        code=code,
        name=data.name,
        description=data.description,
        org_id=organization.id,
        max_uses=data.max_uses,
        expires_at=expires_at,
        created_by=current_user.id,
    )

    db.add(invitation)
    await db.flush()
    await db.refresh(invitation)

    # Reload with organization relationship
    result = await db.execute(
        select(InvitationCode)
        .options(selectinload(InvitationCode.organization))
        .where(InvitationCode.id == invitation.id)
    )
    invitation = result.scalar_one()

    return _invitation_to_response(invitation)


@router.get("", response_model=list[InvitationCodeResponse])
async def list_invitation_codes(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superadmin)],
    status_filter: InvitationStatus | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> list[InvitationCodeResponse]:
    """List all invitation codes with their associated organizations.

    Only superadmin can view invitation codes.
    """
    query = (
        select(InvitationCode)
        .options(selectinload(InvitationCode.organization))
        .order_by(InvitationCode.created_at.desc())
    )

    if status_filter:
        query = query.where(InvitationCode.status == status_filter.value)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    codes = result.scalars().all()

    return [_invitation_to_response(c) for c in codes]


@router.get("/stats")
async def get_invitation_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superadmin)],
) -> dict:
    """Get invitation code statistics.

    Only superadmin can view statistics.
    """
    # Total count
    total_result = await db.execute(select(func.count(InvitationCode.id)))
    total = total_result.scalar() or 0

    # Active count
    active_result = await db.execute(
        select(func.count(InvitationCode.id)).where(
            InvitationCode.status == InvitationStatus.ACTIVE.value,
            InvitationCode.is_active == True
        )
    )
    active = active_result.scalar() or 0

    # Used count
    used_result = await db.execute(
        select(func.count(InvitationCode.id)).where(
            InvitationCode.status == InvitationStatus.USED.value
        )
    )
    used = used_result.scalar() or 0

    # Total registrations via invitation
    total_uses_result = await db.execute(
        select(func.sum(InvitationCode.used_count))
    )
    total_uses = total_uses_result.scalar() or 0

    return {
        "total_codes": total,
        "active_codes": active,
        "used_codes": used,
        "total_registrations": total_uses,
    }


@router.get("/{code_id}", response_model=InvitationCodeResponse)
async def get_invitation_code(
    code_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superadmin)],
) -> InvitationCodeResponse:
    """Get a specific invitation code by ID.

    Only superadmin can view invitation code details.
    """
    result = await db.execute(
        select(InvitationCode)
        .options(selectinload(InvitationCode.organization))
        .where(InvitationCode.id == code_id)
    )
    invitation = result.scalar_one_or_none()

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation code not found",
        )

    return _invitation_to_response(invitation)


@router.put("/{code_id}", response_model=InvitationCodeResponse)
async def update_invitation_code(
    code_id: UUID,
    data: InvitationCodeUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superadmin)],
) -> InvitationCodeResponse:
    """Update an invitation code and its associated organization name.

    Only superadmin can update invitation codes.
    """
    result = await db.execute(
        select(InvitationCode)
        .options(selectinload(InvitationCode.organization))
        .where(InvitationCode.id == code_id)
    )
    invitation = result.scalar_one_or_none()

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation code not found",
        )

    # Update fields
    if data.name is not None:
        invitation.name = data.name
        # Also update organization name to keep them in sync
        if invitation.organization:
            invitation.organization.name = data.name
    if data.description is not None:
        invitation.description = data.description
    if data.max_uses is not None:
        invitation.max_uses = data.max_uses
    if data.is_active is not None:
        invitation.is_active = data.is_active
        if not data.is_active:
            invitation.status = InvitationStatus.DISABLED.value
        elif invitation.used_count >= invitation.max_uses and invitation.max_uses != -1:
            invitation.status = InvitationStatus.USED.value
        else:
            invitation.status = InvitationStatus.ACTIVE.value

    await db.flush()
    await db.refresh(invitation)

    return _invitation_to_response(invitation)


@router.delete("/{code_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_invitation_code(
    code_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superadmin)],
):
    """删除邀请码并级联删除关联的所有数据。

    级联删除顺序:
    1. 删除关联企业的自检报告数据项 (SelfInspectionData)
    2. 删除关联企业的自检报告 (SelfInspectionReport)
    3. 删除关联企业的用户账号 (User)
    4. 删除关联企业的设备 (Device)
    5. 删除企业本身 (Organization)
    6. 删除邀请码 (InvitationCode)

    注意: 这是硬删除，数据不可恢复。
    """
    result = await db.execute(
        select(InvitationCode)
        .options(selectinload(InvitationCode.organization))
        .where(InvitationCode.id == code_id)
    )
    invitation = result.scalar_one_or_none()

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation code not found",
        )

    org = invitation.organization
    org_id = org.id if org else None
    org_name = org.name if org else "N/A"

    try:
        deleted_users: list[str] = []
        deleted_devices: list[str] = []
        deleted_reports = 0

        # 级联删除关联数据
        if org:
            # 1. 删除自检报告数据项 (通过报告ID关联)
            reports_result = await db.execute(
                select(SelfInspectionReport).where(SelfInspectionReport.org_id == org_id)
            )
            reports = reports_result.scalars().all()
            report_ids = [r.id for r in reports]

            if report_ids:
                # 删除数据项
                data_result = await db.execute(
                    select(SelfInspectionData).where(SelfInspectionData.report_id.in_(report_ids))
                )
                data_items = data_result.scalars().all()
                for item in data_items:
                    await db.delete(item)

                # 2. 删除自检报告
                for report in reports:
                    await db.delete(report)

                deleted_reports = len(report_ids)

            # 3. 删除关联用户 (排除超级管理员自己)
            users_result = await db.execute(
                select(User).where(
                    User.org_id == org_id,
                    User.id != current_user.id  # 不要删除当前超级管理员
                )
            )
            users = users_result.scalars().all()
            for user in users:
                deleted_users.append(user.username)
                await db.delete(user)

            # 4. 删除关联设备（保留历史监测数据用于数据沉淀）
            devices_result = await db.execute(
                select(Device).where(Device.org_id == org_id)
            )
            devices = devices_result.scalars().all()
            for device in devices:
                deleted_devices.append(device.mn)
                # 注意：不删除监测数据（MonitoringDataMySQL, MonitoringDailyStats, MonitoringHourlyStats）
                # 这些历史数据作为第三方服务企业的数据沉淀保留
                await db.delete(device)

            # 5. 删除企业
            await db.delete(org)

        # 6. 删除邀请码（必须与 org 同事务删除，避免外键约束）
        await db.delete(invitation)

        await db.commit()

        if org:
            logger.info(
                "Organization cascade deleted",
                org_id=str(org_id),
                org_name=org_name,
                deleted_users=deleted_users,
                deleted_devices=deleted_devices,
                deleted_reports=deleted_reports,
                monitoring_data_preserved=True,  # 监测数据已保留
                operator=current_user.username,
            )

        logger.info(
            "Invitation code deleted",
            code_id=str(code_id),
            org_name=org_name,
            operator=current_user.username,
        )
        return
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.exception(
            "Failed to delete invitation code",
            code_id=str(code_id),
            org_name=org_name,
            operator=current_user.username,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除邀请码失败，请稍后重试",
        )


@router.post("/{code_id}/regenerate", response_model=InvitationCodeResponse)
async def regenerate_invitation_code(
    code_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superadmin)],
) -> InvitationCodeResponse:
    """Regenerate a new code for an existing invitation.

    Useful when a code is leaked or needs to be changed.
    Only superadmin can regenerate codes.
    """
    result = await db.execute(
        select(InvitationCode)
        .options(selectinload(InvitationCode.organization))
        .where(InvitationCode.id == code_id)
    )
    invitation = result.scalar_one_or_none()

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation code not found",
        )

    # Generate new unique code
    for _ in range(10):
        new_code = generate_invitation_code()
        check_result = await db.execute(
            select(InvitationCode).where(InvitationCode.code == new_code)
        )
        if not check_result.scalar_one_or_none():
            break
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate unique invitation code",
        )

    invitation.code = new_code
    await db.flush()
    await db.refresh(invitation)

    return _invitation_to_response(invitation)


# Public endpoint to validate invitation code (for frontend)
@router.get("/validate/{code}")
async def validate_invitation_code(
    code: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Validate an invitation code (public endpoint).

    Returns whether the code is valid and the associated company name.
    """
    result = await db.execute(
        select(InvitationCode).where(InvitationCode.code == code.upper().strip())
    )
    invitation = result.scalar_one_or_none()

    if not invitation:
        return {"valid": False, "message": "邀请码不存在"}

    if not invitation.is_active:
        return {"valid": False, "message": "邀请码已被禁用"}

    if invitation.status == InvitationStatus.USED.value:
        return {"valid": False, "message": "邀请码已达到使用上限"}

    if invitation.status == InvitationStatus.DISABLED.value:
        return {"valid": False, "message": "邀请码已被禁用"}

    if invitation.expires_at and invitation.expires_at < datetime.now(timezone.utc):
        return {"valid": False, "message": "邀请码已过期"}

    # Check usage limit
    if invitation.max_uses != -1 and invitation.used_count >= invitation.max_uses:
        return {"valid": False, "message": "邀请码已达到使用上限"}

    return {
        "valid": True,
        "name": invitation.name,
        "message": "邀请码有效",
    }
