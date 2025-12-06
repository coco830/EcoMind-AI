"""API dependencies for authentication and authorization."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.postgres import get_db
from app.models.user import User, UserRole
from app.models.organization import Organization

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


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

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
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


async def require_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require admin role."""
    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


async def require_operator(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require operator or admin role; allow superadmin bypass."""
    if current_user.is_superadmin:
        return current_user

    if current_user.role not in [UserRole.ADMIN.value, UserRole.OPERATOR.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator privileges required",
        )
    return current_user


async def require_superadmin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require superadmin privileges (platform-level admin)."""
    if not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmin privileges required",
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
