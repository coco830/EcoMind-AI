"""Organization models."""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base, GUID
from app.models.base import BaseSchema


class Organization(Base):
    """Organization ORM model."""

    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(
        GUID, primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    address: Mapped[str | None] = mapped_column(String(512))
    contact_name: Mapped[str | None] = mapped_column(String(64))
    contact_phone: Mapped[str | None] = mapped_column(String(20))
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


class OrganizationCreate(BaseSchema):
    """Schema for creating an organization."""

    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=64)
    address: str | None = Field(None, max_length=512)
    contact_name: str | None = Field(None, max_length=64)
    contact_phone: str | None = Field(None, max_length=20)


class OrganizationResponse(BaseSchema):
    """Schema for organization response."""

    id: UUID
    name: str
    code: str
    address: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    created_at: datetime
    updated_at: datetime


# Import for type hints
from app.models.user import User
from app.models.device import Device
from app.models.invitation import InvitationCode
