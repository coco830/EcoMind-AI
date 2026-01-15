from __future__ import annotations

"""Invitation code models for controlled registration."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import String, DateTime, Integer, Boolean, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base, GUID
from app.models.base import BaseSchema


class InvitationStatus(str, Enum):
    """Invitation code status."""
    ACTIVE = "active"      # 可用
    USED = "used"          # 已用完
    EXPIRED = "expired"    # 已过期
    DISABLED = "disabled"  # 已禁用


class InvitationCode(Base):
    """Invitation code ORM model.

    每个邀请码对应一个企业/组织，使用该邀请码注册的用户都会加入同一个组织。
    """

    __tablename__ = "invitation_codes"

    id: Mapped[UUID] = mapped_column(GUID, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)

    # 邀请码信息
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # 企业名称
    description: Mapped[Optional[str]] = mapped_column(Text)  # 备注说明
    org_type: Mapped[str] = mapped_column(String(32), default="enterprise")
    region_code: Mapped[Optional[str]] = mapped_column(String(64))
    region_name: Mapped[Optional[str]] = mapped_column(String(128))
    park_code: Mapped[Optional[str]] = mapped_column(String(64))
    park_name: Mapped[Optional[str]] = mapped_column(String(128))
    industry_type: Mapped[Optional[str]] = mapped_column(String(64))
    jurisdiction_level: Mapped[Optional[str]] = mapped_column(String(32))
    jurisdiction_codes: Mapped[Optional[str]] = mapped_column(Text)

    # 关联的组织 - 创建邀请码时自动创建对应组织
    org_id: Mapped[Optional[UUID]] = mapped_column(GUID, ForeignKey("organizations.id"))
    organization: Mapped["Organization"] = relationship(back_populates="invitation_codes")

    # 使用限制
    max_uses: Mapped[int] = mapped_column(Integer, default=1)  # 最大使用次数，-1为无限
    used_count: Mapped[int] = mapped_column(Integer, default=0)  # 已使用次数
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))  # 过期时间

    # 状态
    status: Mapped[str] = mapped_column(String(20), default=InvitationStatus.ACTIVE.value)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # 创建者
    created_by: Mapped[Optional[UUID]] = mapped_column(GUID)  # 创建此邀请码的管理员

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# Import for type hints
from app.models.organization import Organization


class InvitationCodeCreate(BaseSchema):
    """Schema for creating an invitation code."""
    name: str = Field(..., min_length=1, max_length=100, description="客户/企业名称")
    description: Optional[str] = Field(None, description="备注说明")
    max_uses: int = Field(1, ge=-1, description="最大使用次数，-1为无限")
    expires_days: Optional[int] = Field(None, ge=1, description="有效天数，不填则永不过期")
    org_type: Optional[str] = Field("enterprise", description="组织类型: enterprise/regulator")
    region_code: Optional[str] = Field(None, description="企业所属区域编码")
    region_name: Optional[str] = Field(None, description="企业所属区域名称")
    park_code: Optional[str] = Field(None, description="园区编码")
    park_name: Optional[str] = Field(None, description="园区名称")
    industry_type: Optional[str] = Field(None, description="行业类型编码")
    jurisdiction_level: Optional[str] = Field(None, description="监管范围层级: district/park")
    jurisdiction_codes: Optional[list[str]] = Field(
        None, description="监管辖区代码列表"
    )


class InvitationCodeResponse(BaseSchema):
    """Schema for invitation code response."""
    id: UUID
    code: str
    name: str
    description: Optional[str] = None
    org_type: Optional[str] = None
    region_code: Optional[str] = None
    region_name: Optional[str] = None
    park_code: Optional[str] = None
    park_name: Optional[str] = None
    industry_type: Optional[str] = None
    jurisdiction_level: Optional[str] = None
    jurisdiction_codes: Optional[list[str]] = None
    org_id: Optional[UUID] = None  # 关联的组织ID
    org_name: Optional[str] = None  # 组织名称（方便前端展示）
    max_uses: int
    used_count: int
    expires_at: Optional[datetime] = None
    status: InvitationStatus
    is_active: bool
    created_at: datetime
    updated_at: datetime


class InvitationCodeUpdate(BaseSchema):
    """Schema for updating an invitation code."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    max_uses: Optional[int] = Field(None, ge=-1)
    is_active: Optional[bool] = None
    region_code: Optional[str] = None
    region_name: Optional[str] = None
    park_code: Optional[str] = None
    park_name: Optional[str] = None
    industry_type: Optional[str] = None
    jurisdiction_level: Optional[str] = None
    jurisdiction_codes: Optional[list[str]] = None
