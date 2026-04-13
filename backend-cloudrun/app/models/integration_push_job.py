from __future__ import annotations

"""Integration push job models for external execution package uploads."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.postgres import Base, GUID
from app.models.base import BaseSchema


class PackagePushJobStatus(str, Enum):
    """Execution package push job status."""

    ACCEPTED = "accepted"
    FAILED = "failed"


class PackagePushJob(Base):
    """Execution package push job audit record."""

    __tablename__ = "package_push_jobs"
    __table_args__ = (
        Index("ix_package_push_jobs_org_id", "org_id"),
        Index("ix_package_push_jobs_client_id", "client_id"),
        Index("ix_package_push_jobs_status", "status"),
        Index("ix_package_push_jobs_created_at", "created_at"),
        Index("ix_package_push_jobs_source_job_id", "source_job_id"),
    )

    id: Mapped[UUID] = mapped_column(GUID, primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        GUID,
        ForeignKey("organizations.id"),
        nullable=False,
        comment="Target organization that the package belongs to.",
    )
    client_id: Mapped[Optional[UUID]] = mapped_column(
        GUID,
        ForeignKey("api_clients.id"),
        nullable=True,
        comment="API client used for the upload.",
    )

    source_job_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    package_name: Mapped[str] = mapped_column(String(256), nullable=False)
    file_name: Mapped[str] = mapped_column(String(256), nullable=False)
    package_uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    document_link: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=PackagePushJobStatus.ACCEPTED.value,
    )
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class PackagePushJobResponse(BaseSchema):
    """Schema for exposing a push job to callers."""

    id: UUID
    org_id: UUID
    client_id: UUID | None = None
    source_job_id: str | None = None
    package_name: str
    file_name: str
    package_uri: str
    document_link: str | None = None
    file_size: int
    file_sha256: str
    content_type: str | None = None
    status: PackagePushJobStatus
    message: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
