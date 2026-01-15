from __future__ import annotations

"""User models."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import EmailStr, Field
from sqlalchemy import String, DateTime, ForeignKey, func

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base, GUID
from app.models.base import BaseSchema


class UserRole(str, Enum):
    """User role enumeration.

    角色权限说明：
    - SUPERADMIN: 超级管理员（环保管家），拥有全部权限
    - DOC_EDITOR: 文档编辑（技术文案），可编辑文档数据，其他只读
    - VIEWER: 只读用户（销售），所有页面只读，用于演示
    - REGULATOR: 监管用户（主管部门），仅可访问监管驾驶舱聚合数据
    """

    SUPERADMIN = "superadmin"      # 超级管理员 - 全部权限
    DOC_EDITOR = "doc_editor"      # 文档编辑 - 文档数据读写 + 其他只读
    VIEWER = "viewer"              # 只读用户 - 所有只读
    REGULATOR = "regulator"        # 监管用户 - 仅监管端聚合数据


class User(Base):
    """User ORM model."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        GUID, primary_key=True, default=uuid4
    )
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(32), default=UserRole.VIEWER.value)
    is_active: Mapped[bool] = mapped_column(default=True)
    is_superadmin: Mapped[bool] = mapped_column(default=False)
    org_id: Mapped[Optional[UUID]] = mapped_column(
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
    full_name: Optional[str] = Field(None, max_length=128)
    role: UserRole = UserRole.VIEWER  # New users start as viewer, role upgrades by superadmin
    org_id: Optional[UUID] = None
    invitation_code: Optional[str] = Field(None, description="邀请码（公开注册必填）")


class UserInDB(BaseSchema):
    """Schema for user stored in database."""

    id: UUID
    username: str
    email: str
    hashed_password: str
    full_name: Optional[str] = None
    role: UserRole
    is_active: bool
    is_superadmin: bool = False
    org_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


class UserResponse(BaseSchema):
    """Schema for user response (without password)."""

    id: UUID
    username: str
    email: str
    full_name: Optional[str] = None
    role: UserRole
    is_active: bool
    is_superadmin: bool = False
    org_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


# Import for type hints
from app.models.organization import Organization
