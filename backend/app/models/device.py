from __future__ import annotations

"""Device models."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import String, DateTime, ForeignKey, Float, Text, func, UniqueConstraint, Index

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


class IndustryType(str, Enum):
    """Industry type enumeration - 行业类型枚举."""

    MUNICIPAL_WASTEWATER = "municipal_wastewater"  # 城镇污水处理厂
    ELECTROPLATING = "electroplating"  # 电镀工业
    TEXTILE_DYEING = "textile_dyeing"  # 纺织染整工业
    THERMAL_POWER = "thermal_power"  # 火电厂
    PHARMACEUTICAL = "pharmaceutical"  # 制药工业
    PAPER_MAKING = "paper_making"  # 造纸工业
    PETROCHEMICAL = "petrochemical"  # 石油化工
    STEEL = "steel"  # 钢铁工业
    CEMENT = "cement"  # 水泥工业
    OTHER = "other"  # 其他（通用标准）


# 行业类型与执行标准映射
INDUSTRY_STANDARD_MAP: dict[str, dict[str, str]] = {
    "municipal_wastewater": {
        "name": "城镇污水处理厂",
        "standard": "GB 18918-2002",
        "standard_name": "城镇污水处理厂污染物排放标准",
    },
    "electroplating": {
        "name": "电镀工业",
        "standard": "GB 21900-2008",
        "standard_name": "电镀污染物排放标准",
    },
    "textile_dyeing": {
        "name": "纺织染整工业",
        "standard": "GB 4287-2012",
        "standard_name": "纺织染整工业水污染物排放标准",
    },
    "thermal_power": {
        "name": "火电厂",
        "standard": "GB 13223-2011",
        "standard_name": "火电厂大气污染物排放标准",
    },
    "pharmaceutical": {
        "name": "制药工业",
        "standard": "GB 21903-2008",
        "standard_name": "制药工业水污染物排放标准",
    },
    "paper_making": {
        "name": "造纸工业",
        "standard": "GB 3544-2008",
        "standard_name": "制浆造纸工业水污染物排放标准",
    },
    "petrochemical": {
        "name": "石油化工",
        "standard": "GB 31571-2015",
        "standard_name": "石油化学工业污染物排放标准",
    },
    "steel": {
        "name": "钢铁工业",
        "standard": "GB 13456-2012",
        "standard_name": "钢铁工业水污染物排放标准",
    },
    "cement": {
        "name": "水泥工业",
        "standard": "GB 4915-2013",
        "standard_name": "水泥工业大气污染物排放标准",
    },
    "other": {
        "name": "其他",
        "standard": "GB 8978-1996",
        "standard_name": "污水综合排放标准",
    },
}


class Device(Base):
    """Device ORM model."""

    __tablename__ = "devices"
    __table_args__ = (
        # MN is unique within each organization (multi-tenant isolation)
        UniqueConstraint('mn', 'org_id', name='uq_device_mn_org'),
        # Index for filtering by org and status (common query pattern)
        Index('ix_device_org_status', 'org_id', 'status'),
        # Index for filtering by org_id alone
        Index('ix_device_org_id', 'org_id'),
        # Index for filtering by status
        Index('ix_device_status', 'status'),
        # Index for last_heartbeat queries (device health monitoring)
        Index('ix_device_last_heartbeat', 'last_heartbeat'),
        # Index for created_at (device listing sorted by creation)
        Index('ix_device_created_at', 'created_at'),
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
    # 行业类型和执行标准
    industry_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    national_standard: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    address: Mapped[Optional[str]] = mapped_column(String(512))
    pollutant_codes: Mapped[Optional[str]] = mapped_column(String(512))  # Comma-separated
    thresholds: Mapped[Optional[str]] = mapped_column(Text)  # JSON string for threshold config
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="devices")
    alarms: Mapped[list["Alarm"]] = relationship(back_populates="device")
    daily_reports: Mapped[list["DailyReport"]] = relationship(back_populates="device")


class PollutantThreshold(BaseModel):
    """Threshold configuration for a single pollutant."""

    pollutant_code: str = Field(..., description="污染物代码，如 w01018")
    pollutant_name: str = Field(default="", description="污染物名称，如 COD")
    enabled: bool = Field(default=True, description="是否启用该污染物阈值")
    warning_value: float = Field(..., ge=0, description="预警值")
    alarm_value: float = Field(..., ge=0, description="报警值")
    unit: str = Field(default="mg/L", description="单位")


class ThresholdConfig(BaseModel):
    """Threshold configuration for a device."""

    enabled: bool = Field(default=True, description="是否启用阈值检测")
    pollutants: list[PollutantThreshold] = Field(default_factory=list, description="各污染物阈值")

    def get_threshold(self, pollutant_code: str, include_disabled: bool = False) -> Optional[PollutantThreshold]:
        """Get threshold for a specific pollutant."""
        for p in self.pollutants:
            if p.pollutant_code == pollutant_code:
                # Ignore disabled thresholds unless explicitly requested
                if not include_disabled and getattr(p, "enabled", True) is False:
                    return None
                return p
        return None


class DeviceCreate(BaseSchema):
    """Schema for creating a device."""

    mn: str = Field(..., min_length=1, max_length=24)
    name: str = Field(..., min_length=1, max_length=128)
    device_type: DeviceType
    org_id: Optional[UUID] = Field(None, description="组织ID，如不提供则使用当前用户的组织")
    industry_type: Optional[IndustryType] = Field(None, description="行业类型")
    national_standard: Optional[str] = Field(None, max_length=128, description="执行标准号，如 GB 18918-2002")
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    address: Optional[str] = Field(None, max_length=512)
    pollutant_codes: Optional[list[str]] = None
    thresholds: Optional[ThresholdConfig] = Field(None, description="阈值配置")


class DeviceResponse(BaseSchema):
    """Schema for device response."""

    id: UUID
    mn: str
    name: str
    device_type: DeviceType
    status: DeviceStatus
    org_id: UUID
    industry_type: Optional[IndustryType] = None
    national_standard: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    pollutant_codes: Optional[list[str]] = None
    thresholds: Optional[ThresholdConfig] = None
    last_heartbeat: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


# Import for type hints
from app.models.organization import Organization
from app.models.alarm import Alarm
from app.models.daily_report import DailyReport
