from __future__ import annotations

"""Daily Report models for AI-generated device analysis reports."""

from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import String, DateTime, Date, ForeignKey, Text, func, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base, GUID
from app.models.base import BaseSchema


class ReportStatus(str, Enum):
    """Report generation status."""

    PENDING = "pending"       # 待生成
    GENERATING = "generating"  # 生成中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 生成失败


class DailyReport(Base):
    """Daily Report ORM model.

    Stores AI-generated daily analysis reports for devices.
    Each device has at most one report per day.
    """

    __tablename__ = "daily_reports"
    __table_args__ = (
        # Unique constraint: one report per device per day
        UniqueConstraint('device_id', 'report_date', name='uq_device_report_date'),
        # Index for querying by device
        Index('ix_daily_report_device', 'device_id'),
        # Index for querying by date
        Index('ix_daily_report_date', 'report_date'),
        # Index for querying by status
        Index('ix_daily_report_status', 'status'),
    )

    id: Mapped[UUID] = mapped_column(
        GUID, primary_key=True, default=uuid4
    )
    device_id: Mapped[UUID] = mapped_column(
        GUID, ForeignKey("devices.id"), nullable=False
    )
    report_date: Mapped[date] = mapped_column(
        Date, nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), default=ReportStatus.PENDING.value
    )

    # Report content
    report_content: Mapped[Optional[str]] = mapped_column(Text)

    # Statistics snapshot (JSON string)
    stats_snapshot: Mapped[Optional[str]] = mapped_column(Text)

    # Metadata
    pollutant_count: Mapped[Optional[int]] = mapped_column()
    data_points: Mapped[Optional[int]] = mapped_column()
    domain: Mapped[Optional[str]] = mapped_column(String(32))

    # Error info if failed
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    device: Mapped["Device"] = relationship(back_populates="daily_reports")


class DailyReportCreate(BaseSchema):
    """Schema for creating a daily report."""

    device_id: UUID
    report_date: date


class DailyReportResponse(BaseSchema):
    """Schema for daily report response."""

    id: UUID
    device_id: UUID
    report_date: date
    status: ReportStatus
    report_content: str | None = None
    stats_snapshot: str | None = None
    pollutant_count: int | None = None
    data_points: int | None = None
    domain: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    generated_at: datetime | None = None


# Import for type hints
from app.models.device import Device
