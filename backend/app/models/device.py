"""Device models."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import String, DateTime, ForeignKey, Float, Text, func, UniqueConstraint

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base, GUID
from app.models.base import BaseSchema


class DeviceStatus(str, Enum):
    """Device status enumeration."""

    ONLINE = "online"
    OFFLINE = "offline"
    ALARM = "alarm"
    MAINTENANCE = "maintenance"


class DeviceType(str, Enum):
    """Device type enumeration."""

    WATER = "water"  # 水质监测
    AIR = "air"  # 大气监测
    NOISE = "noise"  # 噪声监测
    SOIL = "soil"  # 土壤监测


class Device(Base):
    """Device ORM model."""

    __tablename__ = "devices"
    __table_args__ = (
        # MN is unique within each organization (multi-tenant isolation)
        UniqueConstraint('mn', 'org_id', name='uq_device_mn_org'),
    )

    id: Mapped[UUID] = mapped_column(
        GUID, primary_key=True, default=uuid4
    )
    mn: Mapped[str] = mapped_column(String(24), nullable=False, index=True)  # 设备MN号 - unique per org
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    device_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=DeviceStatus.OFFLINE.value)
    org_id: Mapped[UUID] = mapped_column(
        GUID, ForeignKey("organizations.id"), nullable=False
    )
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    address: Mapped[str | None] = mapped_column(String(512))
    pollutant_codes: Mapped[str | None] = mapped_column(String(512))  # Comma-separated
    thresholds: Mapped[str | None] = mapped_column(Text)  # JSON string for threshold config
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="devices")
    alarms: Mapped[list["Alarm"]] = relationship(back_populates="device")


class PollutantThreshold(BaseModel):
    """Threshold configuration for a single pollutant."""

    pollutant_code: str = Field(..., description="污染物代码，如 w01018")
    pollutant_name: str = Field(default="", description="污染物名称，如 COD")
    warning_value: float = Field(..., ge=0, description="预警值")
    alarm_value: float = Field(..., ge=0, description="报警值")
    unit: str = Field(default="mg/L", description="单位")


class ThresholdConfig(BaseModel):
    """Threshold configuration for a device."""

    enabled: bool = Field(default=True, description="是否启用阈值检测")
    pollutants: list[PollutantThreshold] = Field(default_factory=list, description="各污染物阈值")

    def get_threshold(self, pollutant_code: str) -> PollutantThreshold | None:
        """Get threshold for a specific pollutant."""
        for p in self.pollutants:
            if p.pollutant_code == pollutant_code:
                return p
        return None


class DeviceCreate(BaseSchema):
    """Schema for creating a device."""

    mn: str = Field(..., min_length=1, max_length=24)
    name: str = Field(..., min_length=1, max_length=128)
    device_type: DeviceType
    org_id: UUID | None = Field(None, description="组织ID，如不提供则使用当前用户的组织")
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    address: str | None = Field(None, max_length=512)
    pollutant_codes: list[str] | None = None
    thresholds: ThresholdConfig | None = Field(None, description="阈值配置")


class DeviceResponse(BaseSchema):
    """Schema for device response."""

    id: UUID
    mn: str
    name: str
    device_type: DeviceType
    status: DeviceStatus
    org_id: UUID
    latitude: float | None = None
    longitude: float | None = None
    address: str | None = None
    pollutant_codes: list[str] | None = None
    thresholds: ThresholdConfig | None = None
    last_heartbeat: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None


# Import for type hints
from app.models.organization import Organization
from app.models.alarm import Alarm
