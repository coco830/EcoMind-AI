"""User models."""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import EmailStr, Field
from sqlalchemy import String, DateTime, ForeignKey, func

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base, GUID
from app.models.base import BaseSchema


class UserRole(str, Enum):
    """User role enumeration."""

    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class User(Base):
    """User ORM model."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        GUID, primary_key=True, default=uuid4
    )
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(32), default=UserRole.VIEWER.value)
    is_active: Mapped[bool] = mapped_column(default=True)
    is_superadmin: Mapped[bool] = mapped_column(default=False)
    org_id: Mapped[UUID | None] = mapped_column(
        GUID, ForeignKey("organizations.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="users")


class UserCreate(BaseSchema):
    """Schema for creating a user."""

    username: str = Field(..., min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(None, max_length=128)
    role: UserRole = UserRole.OPERATOR  # Changed from VIEWER to OPERATOR for new users
    org_id: UUID | None = None
    invitation_code: str | None = Field(None, description="邀请码（公开注册必填）")


class UserInDB(BaseSchema):
    """Schema for user stored in database."""

    id: UUID
    username: str
    email: str
    hashed_password: str
    full_name: str | None = None
    role: UserRole
    is_active: bool
    is_superadmin: bool = False
    org_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class UserResponse(BaseSchema):
    """Schema for user response (without password)."""

    id: UUID
    username: str
    email: str
    full_name: str | None = None
    role: UserRole
    is_active: bool
    is_superadmin: bool = False
    org_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


# Import for type hints
from app.models.organization import Organization
