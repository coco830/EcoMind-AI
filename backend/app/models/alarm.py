"""Alarm models."""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import String, DateTime, ForeignKey, Text, func, Integer

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base, GUID
from app.models.base import BaseSchema


class AlarmStatus(str, Enum):
    """Alarm status enumeration."""

    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class AlarmLevel(str, Enum):
    """Alarm severity level enumeration."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlarmType(str, Enum):
    """Alarm type enumeration."""

    THRESHOLD = "threshold"  # 阈值超标
    ANOMALY = "anomaly"  # AI异常检测
    OFFLINE = "offline"  # 设备离线
    FLAG = "flag"  # 数据Flag异常


class Alarm(Base):
    """Alarm ORM model."""

    __tablename__ = "alarms"

    id: Mapped[UUID] = mapped_column(
        GUID, primary_key=True, default=uuid4
    )
    device_id: Mapped[UUID] = mapped_column(
        GUID, ForeignKey("devices.id"), nullable=False
    )
    alarm_type: Mapped[str] = mapped_column(String(32), nullable=False)
    level: Mapped[str] = mapped_column(String(32), default=AlarmLevel.WARNING.value)
    status: Mapped[str] = mapped_column(String(32), default=AlarmStatus.PENDING.value)
    pollutant_code: Mapped[str | None] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[str | None] = mapped_column(String(64))  # Recorded value
    threshold: Mapped[str | None] = mapped_column(String(64))  # Threshold value
    acknowledged_by: Mapped[UUID | None] = mapped_column(GUID)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sms_sent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_sms_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    device: Mapped["Device"] = relationship(back_populates="alarms")


class AlarmCreate(BaseSchema):
    """Schema for creating an alarm."""

    device_id: UUID
    alarm_type: AlarmType
    level: AlarmLevel = AlarmLevel.WARNING
    pollutant_code: str | None = Field(None, max_length=32)
    message: str = Field(..., min_length=1)
    value: str | None = Field(None, max_length=64)
    threshold: str | None = Field(None, max_length=64)


class AlarmResponse(BaseSchema):
    """Schema for alarm response."""

    id: UUID
    device_id: UUID
    alarm_type: AlarmType
    level: AlarmLevel
    status: AlarmStatus
    pollutant_code: str | None = None
    message: str
    value: str | None = None
    threshold: str | None = None
    acknowledged_by: UUID | None = None
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    sms_sent_count: int = 0
    last_sms_time: datetime | None = None
    created_at: datetime
    updated_at: datetime


# Import for type hints
from app.models.device import Device
