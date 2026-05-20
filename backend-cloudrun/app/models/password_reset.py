"""Password reset token model."""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import EmailStr, Field
from sqlalchemy import String, DateTime, ForeignKey, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.postgres import Base, GUID
from app.models.base import BaseSchema


class PasswordResetToken(Base):
    """Password reset token ORM model."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[UUID] = mapped_column(GUID, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(GUID, ForeignKey("users.id"), nullable=False)
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ForgotPasswordRequest(BaseSchema):
    """Schema for forgot password request."""

    email: EmailStr


class ResetPasswordRequest(BaseSchema):
    """Schema for reset password request."""

    token: str
    new_password: str = Field(..., min_length=8, max_length=128)


class ForgotPasswordResponse(BaseSchema):
    """Schema for forgot password response."""

    message: str
    success: bool


class ResetPasswordResponse(BaseSchema):
    """Schema for reset password response."""

    message: str
    success: bool
