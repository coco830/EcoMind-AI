"""Authentication API endpoints.

Security:
- Rate limiting on login and register endpoints to prevent brute force attacks
- Login: 5 attempts per minute per IP
- Register: 3 attempts per minute per IP
- Password reset: 3 attempts per minute per IP
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.core.rate_limiter import limiter
from app.db.postgres import get_db
from app.models.user import User, UserCreate, UserResponse
from app.models.password_reset import (
    PasswordResetToken,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordResponse,
)
from app.api.deps import get_current_active_user
from app.services.email_service import email_service

router = APIRouter()


class Token(BaseModel):
    """Token response model."""

    access_token: str
    token_type: str = "bearer"


class LoginResponse(BaseModel):
    """Login response with token and user info."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse


@router.post("/login", response_model=LoginResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LoginResponse:
    """Authenticate user by username or email and return JWT token.

    Rate limited to 5 attempts per minute per IP to prevent brute force attacks.
    """
    # Trim login identifier to handle accidental whitespace.
    login_identifier = form_data.username.strip()
    normalized_email = login_identifier.lower()
    result = await db.execute(
        select(User).where(
            or_(
                User.username == login_identifier,
                func.lower(User.email) == normalized_email,
            )
        )
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )

    access_token = create_access_token(data={"sub": str(user.id)})

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")
async def register(
    request: Request,
    user_data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Register a new user with invitation code.

    Requires a valid invitation code for registration.
    User will join the organization bound to the invitation code.
    Rate limited to 3 attempts per minute per IP to prevent abuse.
    """
    from app.models.invitation import InvitationCode, InvitationStatus
    from datetime import datetime, timezone

    # Validate invitation code (required for public registration)
    if not user_data.invitation_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邀请码是必填项",
        )

    # Look up invitation code
    code_str = user_data.invitation_code.upper().strip()
    result = await db.execute(
        select(InvitationCode).where(InvitationCode.code == code_str)
    )
    invitation = result.scalar_one_or_none()

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邀请码不存在",
        )

    if not invitation.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邀请码已被禁用",
        )

    if invitation.status in [InvitationStatus.USED.value, InvitationStatus.DISABLED.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邀请码已失效",
        )

    if invitation.expires_at and invitation.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邀请码已过期",
        )

    # Check usage limit
    if invitation.max_uses != -1 and invitation.used_count >= invitation.max_uses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邀请码已达到使用上限",
        )

    # Verify invitation code has bound organization
    if not invitation.org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邀请码配置错误，请联系管理员",
        )

    # Check if username exists
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已被注册",
        )

    # Check if email exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被注册",
        )

    # Assign role based on invitation org_type
    # - enterprise: viewer (default)
    # - regulator: regulator
    invitation_org_type = getattr(invitation, "org_type", "enterprise")
    user_role = 'viewer'
    if invitation_org_type == "regulator":
        user_role = 'regulator'

    # Create user and add to the organization bound to the invitation code
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        role=user_role,
        org_id=invitation.org_id,  # Join the organization bound to invitation code
    )
    db.add(user)

    # Update invitation code usage
    invitation.used_count += 1
    if invitation.max_uses != -1 and invitation.used_count >= invitation.max_uses:
        invitation.status = InvitationStatus.USED.value

    await db.flush()
    await db.refresh(user)

    return UserResponse.model_validate(user)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> UserResponse:
    """Get current user information."""
    return UserResponse.model_validate(current_user)


@router.post("/logout")
async def logout() -> dict[str, str]:
    """Logout current user (client should discard token)."""
    return {"message": "Successfully logged out"}


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
@limiter.limit("3/minute")
async def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ForgotPasswordResponse:
    """Request password reset email.

    Sends a password reset link to the user's email if the account exists.
    For security, always returns success even if email doesn't exist.
    Rate limited to 3 attempts per minute per IP.
    """
    settings = get_settings()

    # Find user by email
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if user and user.is_active:
        # Generate secure token
        token = secrets.token_urlsafe(32)

        # Calculate expiration time
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.password_reset_expire_minutes
        )

        # Invalidate any existing tokens for this user
        existing_tokens = await db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.is_used == False,
            )
        )
        for existing_token in existing_tokens.scalars():
            existing_token.is_used = True

        # Create new reset token
        reset_token = PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=expires_at,
        )
        db.add(reset_token)
        await db.flush()

        # Send email
        await email_service.send_password_reset_email(
            to_email=user.email,
            username=user.username,
            reset_token=token,
        )

    # Always return success for security (don't reveal if email exists)
    return ForgotPasswordResponse(
        message="如果该邮箱已注册，您将收到一封密码重置邮件",
        success=True,
    )


@router.post("/reset-password", response_model=ResetPasswordResponse)
@limiter.limit("5/minute")
async def reset_password(
    request: Request,
    data: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ResetPasswordResponse:
    """Reset password using token.

    Validates the token and updates the user's password.
    Rate limited to 5 attempts per minute per IP.
    """
    # Find the token
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token == data.token,
            PasswordResetToken.is_used == False,
        )
    )
    reset_token = result.scalar_one_or_none()

    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效或已过期的重置链接",
        )

    # Check if token is expired
    if reset_token.expires_at < datetime.now(timezone.utc):
        reset_token.is_used = True
        await db.flush()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="重置链接已过期，请重新申请",
        )

    # Find the user
    result = await db.execute(select(User).where(User.id == reset_token.user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户不存在或已被禁用",
        )

    # Update password
    user.hashed_password = get_password_hash(data.new_password)

    # Mark token as used
    reset_token.is_used = True

    await db.flush()
    await db.refresh(user)

    return ResetPasswordResponse(
        message="密码重置成功，请使用新密码登录",
        success=True,
    )


@router.get("/verify-reset-token")
async def verify_reset_token(
    token: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Verify if a password reset token is valid.

    Used by frontend to check token validity before showing reset form.
    """
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token == token,
            PasswordResetToken.is_used == False,
        )
    )
    reset_token = result.scalar_one_or_none()

    if not reset_token:
        return {"valid": False, "message": "无效的重置链接"}

    if reset_token.expires_at < datetime.now(timezone.utc):
        return {"valid": False, "message": "重置链接已过期"}

    return {"valid": True, "message": "链接有效"}
