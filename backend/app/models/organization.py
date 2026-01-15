from __future__ import annotations

"""Organization models."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base, GUID
from app.models.base import BaseSchema


class OrganizationStatus(str, Enum):
    """Organization status enum."""
    ACTIVE = "active"
    INACTIVE = "inactive"


class Organization(Base):
    """Organization ORM model."""

    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(
        GUID, primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    address: Mapped[Optional[str]] = mapped_column(String(512))
    contact_name: Mapped[Optional[str]] = mapped_column(String(64))
    contact_phone: Mapped[Optional[str]] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(
        String(20), default=OrganizationStatus.ACTIVE.value, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    users: Mapped[list["User"]] = relationship(back_populates="organization")
    devices: Mapped[list["Device"]] = relationship(back_populates="organization")
    invitation_codes: Mapped[list["InvitationCode"]] = relationship(back_populates="organization")
    self_inspection_reports: Mapped[list["SelfInspectionReport"]] = relationship(back_populates="organization")


class OrganizationCreate(BaseSchema):
    """Schema for creating an organization."""

    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=64)
    address: Optional[str] = Field(None, max_length=512)
    contact_name: Optional[str] = Field(None, max_length=64)
    contact_phone: Optional[str] = Field(None, max_length=20)


class OrganizationResponse(BaseSchema):
    """Schema for organization response."""

    id: UUID
    name: str
    code: str
    address: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    status: str = OrganizationStatus.ACTIVE.value
    created_at: datetime
    updated_at: datetime


# Import for type hints
from app.models.user import User
from app.models.device import Device
from app.models.invitation import InvitationCode
from app.models.self_inspection import SelfInspectionReport
