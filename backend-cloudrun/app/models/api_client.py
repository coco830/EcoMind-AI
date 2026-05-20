"""API Client model for OpenAPI key-based authentication."""

from __future__ import annotations

import secrets
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import String, DateTime, ForeignKey, Integer, Boolean, Text, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base, GUID
from app.models.base import BaseSchema


def generate_api_key() -> str:
    """Generate a secure API key with ecomind_ prefix."""
    return f"ecomind_{secrets.token_urlsafe(32)}"


class ApiClientScope(str, Enum):
    """API client data access scope."""

    SINGLE_ORG = "single_org"
    ALL_ORGS = "all_orgs"


class ApiClient(Base):
    """API Client ORM model for external integrations (e.g. OpenClaw)."""

    __tablename__ = "api_clients"
    __table_args__ = (
        Index("ix_api_client_api_key", "api_key", unique=True),
        Index("ix_api_client_org_id", "org_id"),
    )

    id: Mapped[UUID] = mapped_column(GUID, primary_key=True, default=uuid4)
    api_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, default=generate_api_key)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    org_id: Mapped[UUID] = mapped_column(
        GUID,
        ForeignKey("organizations.id"),
        nullable=False,
        comment="Owner org. For all_orgs keys this field is for ownership/audit, not query filtering.",
    )
    access_scope: Mapped[str] = mapped_column(String(32), default=ApiClientScope.SINGLE_ORG.value, nullable=False)
    permissions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list of allowed tools
    rate_limit: Mapped[int] = mapped_column(Integer, default=60)  # calls per minute
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    organization: Mapped["Organization"] = relationship()


class ApiClientCreate(BaseSchema):
    """Schema for creating an API client."""
    name: str = Field(..., min_length=1, max_length=128)
    org_id: UUID = Field(..., description="归属组织ID。all_orgs模式下用于审计归属，不做数据过滤")
    access_scope: ApiClientScope = Field(default=ApiClientScope.SINGLE_ORG)
    permissions: Optional[list[str]] = None
    rate_limit: int = Field(default=60, ge=1, le=600)
    expires_at: Optional[datetime] = None


class ApiClientResponse(BaseSchema):
    """Schema for API client response."""
    id: UUID
    api_key: str
    name: str
    org_id: UUID
    access_scope: str
    permissions: Optional[str] = None
    rate_limit: int
    is_active: bool
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# Import for type hints
from app.models.organization import Organization
