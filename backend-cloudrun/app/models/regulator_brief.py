from __future__ import annotations

"""Regulator brief usage tracking model."""

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, String, ForeignKey, func, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.postgres import Base, GUID


class RegulatorBriefUsage(Base):
    """Track regulator brief generation usage for rate limiting."""

    __tablename__ = "regulator_brief_usages"
    __table_args__ = (
        Index("ix_brief_usage_user_period_date", "user_id", "period", "usage_date"),
    )

    id: Mapped[UUID] = mapped_column(GUID, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(GUID, ForeignKey("users.id"), nullable=False)
    period: Mapped[str] = mapped_column(String(16), nullable=False)  # daily/monthly
    usage_date: Mapped[date] = mapped_column(Date, nullable=False)  # day or first day of month
    target_label: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
