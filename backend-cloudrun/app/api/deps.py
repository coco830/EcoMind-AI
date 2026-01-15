from __future__ import annotations

"""API dependencies for authentication and authorization."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import decode_access_token
from app.db.postgres import get_db
from app.models.user import User, UserRole
from app.models.organization import Organization, OrganizationType

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def _is_platform_staff(user: User) -> bool:
    """Platform staff = internal accounts under PLATFORM_ADMIN org.

    Important: We intentionally require organization.code == PLATFORM_ADMIN so that
    a tenant user with role=doc_editor/viewer cannot gain cross-tenant access.
    """
    org = getattr(user, "organization", None)
    if org is None:
        return False
    if getattr(org, "code", None) != "PLATFORM_ADMIN":
        return False
    return user.role in {UserRole.DOC_EDITOR.value, UserRole.VIEWER.value}


def can_cross_tenant_read(user: User) -> bool:
    """Allow cross-tenant read for superadmin and platform staff."""
    return bool(user.is_superadmin) or _is_platform_staff(user)


def can_cross_tenant_doc_write(user: User) -> bool:
    """Allow cross-tenant doc operations for superadmin and platform doc_editor."""
    if bool(user.is_superadmin):
        return True
    org = getattr(user, "organization", None)
    if org is None or getattr(org, "code", None) != "PLATFORM_ADMIN":
        return False
    return user.role == UserRole.DOC_EDITOR.value


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Get current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    result = await db.execute(
        select(User)
        .options(selectinload(User.organization))
        .where(User.id == UUID(user_id))
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Get current active user."""
    return current_user


async def require_superadmin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require superadmin privileges (platform-level admin).

    超级管理员权限：可以管理邀请码、用户、设备等所有数据
    """
    if not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要超级管理员权限",
        )
    return current_user


async def require_platform_staff_read(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Allow superadmin + platform staff (doc_editor/viewer under PLATFORM_ADMIN) to read cross-tenant data."""
    if current_user.is_superadmin:
        return current_user
    if not _is_platform_staff(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要平台人员权限",
        )
    return current_user


async def require_doc_editor(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require doc_editor or superadmin role.

    文档编辑权限：可以上传、编辑自检报告等文档数据
    - superadmin: 允许
    - doc_editor: 允许
    - viewer: 拒绝
    """
    if current_user.is_superadmin:
        return current_user

    if current_user.role not in [UserRole.SUPERADMIN.value, UserRole.DOC_EDITOR.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要文档编辑权限",
        )
    return current_user


async def require_write_permission(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require write permission (superadmin only for most operations).

    写入权限：仅超级管理员可以修改设备、用户等核心数据
    """
    if not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您没有写入权限，请联系管理员",
        )
    return current_user


async def get_current_org(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Organization | None:
    """Get current user's organization. Returns None for superadmins without org."""
    if current_user.org_id is None:
        return None

    result = await db.execute(
        select(Organization).where(Organization.id == current_user.org_id)
    )
    return result.scalar_one_or_none()


async def require_org_membership(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require user to belong to an organization (unless superadmin)."""
    if not current_user.is_superadmin and current_user.org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User must belong to an organization",
        )
    return current_user


async def require_regulator_access(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require regulator role or superadmin."""
    if current_user.is_superadmin:
        return current_user
    if current_user.role != UserRole.REGULATOR.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要监管权限",
        )
    org = getattr(current_user, "organization", None)
    if org is None or getattr(org, "org_type", None) != OrganizationType.REGULATOR.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="监管组织配置异常",
        )
    return current_user
