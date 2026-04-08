from __future__ import annotations

"""Video linkage models and schemas."""

import json
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base, GUID
from app.models.base import BaseSchema


class VideoPointType(str, Enum):
    """Standardized video point types for pollution-source scenarios."""

    STATION_ROOM = "station_room"
    WASTEWATER_OUTLET = "wastewater_outlet"
    WASTEGAS_OUTLET = "wastegas_outlet"
    MANUAL_SAMPLING = "manual_sampling"
    CUSTOM = "custom"


class VideoProtocol(str, Enum):
    """Supported upstream video access protocols."""

    GB28181 = "gb28181"
    RTSP = "rtsp"
    ONVIF = "onvif"
    HTTP_LINK = "http_link"
    OTHER = "other"


class VideoAccessMethod(str, Enum):
    """How the channel is connected into the platform."""

    OPERATOR_PLATFORM = "operator_platform"
    CITY_PLATFORM = "city_platform"
    DIRECT = "direct"
    EXTERNAL_LINK = "external_link"


class VideoChannelStatus(str, Enum):
    """Video channel health/status."""

    ONLINE = "online"
    OFFLINE = "offline"
    FAULT = "fault"
    UNKNOWN = "unknown"


class VideoLifecycleStatus(str, Enum):
    """Delivery lifecycle for channel installation and acceptance."""

    PENDING_SURVEY = "pending_survey"
    PENDING_INSTALLATION = "pending_installation"
    PENDING_NETWORKING = "pending_networking"
    COMMISSIONING = "commissioning"
    ACCEPTED = "accepted"
    ACTIVE = "active"


class VideoEventType(str, Enum):
    """Event types for video inspection/linkage."""

    STREAM_OFFLINE = "stream_offline"
    OCCLUSION = "occlusion"
    INTRUSION = "intrusion"
    LOITERING = "loitering"
    WASTEWATER_VISUAL_ANOMALY = "wastewater_visual_anomaly"
    SMOKE_PLUME_CHANGE = "smoke_plume_change"
    MANUAL_SAMPLING = "manual_sampling"
    AI_LINKAGE = "ai_linkage"
    CUSTOM = "custom"


class VideoEventSource(str, Enum):
    """Where a video event came from."""

    MANUAL = "manual"
    EXTERNAL_CALLBACK = "external_callback"
    AI_LINKAGE = "ai_linkage"
    INSPECTION = "inspection"


class VideoEventLevel(str, Enum):
    """Severity level for video events."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class VideoEventStatus(str, Enum):
    """Workflow status for video events."""

    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class VideoChannel(Base):
    """Video channel linked to one monitoring device."""

    __tablename__ = "video_channels"
    __table_args__ = (
        UniqueConstraint("device_id", "name", name="uq_video_channel_device_name"),
        Index("ix_video_channel_org_status", "org_id", "status"),
        Index("ix_video_channel_device_id", "device_id"),
        Index("ix_video_channel_device_mn", "device_mn"),
        Index("ix_video_channel_point_type", "point_type"),
    )

    id: Mapped[UUID] = mapped_column(GUID, primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        GUID, ForeignKey("organizations.id"), nullable=False, index=True
    )
    device_id: Mapped[UUID] = mapped_column(
        GUID, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    device_mn: Mapped[str] = mapped_column(String(24), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    point_type: Mapped[str] = mapped_column(String(32), nullable=False)
    protocol: Mapped[str] = mapped_column(String(32), nullable=False, default=VideoProtocol.GB28181.value)
    access_method: Mapped[str] = mapped_column(
        String(32), nullable=False, default=VideoAccessMethod.OPERATOR_PLATFORM.value
    )
    lifecycle_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=VideoLifecycleStatus.PENDING_SURVEY.value
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=VideoChannelStatus.UNKNOWN.value)
    vendor: Mapped[Optional[str]] = mapped_column(String(64))
    channel_code: Mapped[Optional[str]] = mapped_column(String(128))
    network_provider: Mapped[Optional[str]] = mapped_column(String(64))
    fixed_ip: Mapped[Optional[str]] = mapped_column(String(64))
    install_location: Mapped[Optional[str]] = mapped_column(Text)
    surveyor_name: Mapped[Optional[str]] = mapped_column(String(64))
    installer_name: Mapped[Optional[str]] = mapped_column(String(64))
    accepted_by: Mapped[Optional[str]] = mapped_column(String(64))
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    acceptance_notes: Mapped[Optional[str]] = mapped_column(Text)
    preview_url: Mapped[Optional[str]] = mapped_column(String(1024))
    playback_url: Mapped[Optional[str]] = mapped_column(String(1024))
    ai_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    organization: Mapped["Organization"] = relationship()
    device: Mapped["Device"] = relationship()


class VideoEvent(Base):
    """Video inspection or linkage event."""

    __tablename__ = "video_events"
    __table_args__ = (
        Index("ix_video_event_org_occurred", "org_id", "occurred_at"),
        Index("ix_video_event_channel_occurred", "channel_id", "occurred_at"),
        Index("ix_video_event_device_occurred", "device_id", "occurred_at"),
        Index("ix_video_event_status_level", "status", "level"),
        Index("ix_video_event_related_alarm", "related_alarm_id"),
    )

    id: Mapped[UUID] = mapped_column(GUID, primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        GUID, ForeignKey("organizations.id"), nullable=False, index=True
    )
    channel_id: Mapped[UUID] = mapped_column(
        GUID, ForeignKey("video_channels.id", ondelete="CASCADE"), nullable=False
    )
    device_id: Mapped[UUID] = mapped_column(
        GUID, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    device_mn: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    related_alarm_id: Mapped[Optional[UUID]] = mapped_column(
        GUID, ForeignKey("alarms.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default=VideoEventSource.MANUAL.value)
    level: Mapped[str] = mapped_column(String(32), nullable=False, default=VideoEventLevel.WARNING.value)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=VideoEventStatus.PENDING.value)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    snapshot_uri: Mapped[Optional[str]] = mapped_column(String(1024))
    clip_uri: Mapped[Optional[str]] = mapped_column(String(1024))
    extra_data: Mapped[Optional[str]] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    organization: Mapped["Organization"] = relationship()
    channel: Mapped["VideoChannel"] = relationship()
    device: Mapped["Device"] = relationship()
    related_alarm: Mapped[Optional["Alarm"]] = relationship()


def serialize_video_extra_data(extra_data: dict[str, Any] | None) -> str | None:
    """Serialize event extra data to JSON."""

    if not extra_data:
        return None
    return json.dumps(extra_data, ensure_ascii=False)


def deserialize_video_extra_data(extra_data_json: str | None) -> dict[str, Any] | None:
    """Deserialize event extra data JSON."""

    if not extra_data_json:
        return None
    try:
        data = json.loads(extra_data_json)
        return data if isinstance(data, dict) else None
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


class VideoChannelCreate(BaseSchema):
    """Schema for creating a video channel."""

    device_id: UUID
    name: str = Field(..., min_length=1, max_length=128)
    point_type: VideoPointType
    protocol: VideoProtocol = VideoProtocol.GB28181
    access_method: VideoAccessMethod = VideoAccessMethod.OPERATOR_PLATFORM
    lifecycle_status: VideoLifecycleStatus = VideoLifecycleStatus.PENDING_SURVEY
    status: VideoChannelStatus = VideoChannelStatus.UNKNOWN
    vendor: Optional[str] = Field(None, max_length=64)
    channel_code: Optional[str] = Field(None, max_length=128)
    network_provider: Optional[str] = Field(None, max_length=64)
    fixed_ip: Optional[str] = Field(None, max_length=64)
    install_location: Optional[str] = None
    surveyor_name: Optional[str] = Field(None, max_length=64)
    installer_name: Optional[str] = Field(None, max_length=64)
    accepted_by: Optional[str] = Field(None, max_length=64)
    accepted_at: Optional[datetime] = None
    acceptance_notes: Optional[str] = None
    preview_url: Optional[str] = Field(None, max_length=1024)
    playback_url: Optional[str] = Field(None, max_length=1024)
    ai_enabled: bool = False
    notes: Optional[str] = None
    last_seen_at: Optional[datetime] = None


class VideoChannelUpdate(BaseSchema):
    """Schema for updating a video channel."""

    device_id: UUID
    name: str = Field(..., min_length=1, max_length=128)
    point_type: VideoPointType
    protocol: VideoProtocol = VideoProtocol.GB28181
    access_method: VideoAccessMethod = VideoAccessMethod.OPERATOR_PLATFORM
    lifecycle_status: VideoLifecycleStatus = VideoLifecycleStatus.PENDING_SURVEY
    status: VideoChannelStatus = VideoChannelStatus.UNKNOWN
    vendor: Optional[str] = Field(None, max_length=64)
    channel_code: Optional[str] = Field(None, max_length=128)
    network_provider: Optional[str] = Field(None, max_length=64)
    fixed_ip: Optional[str] = Field(None, max_length=64)
    install_location: Optional[str] = None
    surveyor_name: Optional[str] = Field(None, max_length=64)
    installer_name: Optional[str] = Field(None, max_length=64)
    accepted_by: Optional[str] = Field(None, max_length=64)
    accepted_at: Optional[datetime] = None
    acceptance_notes: Optional[str] = None
    preview_url: Optional[str] = Field(None, max_length=1024)
    playback_url: Optional[str] = Field(None, max_length=1024)
    ai_enabled: bool = False
    notes: Optional[str] = None
    last_seen_at: Optional[datetime] = None


class VideoChannelResponse(BaseSchema):
    """Schema returned for video channel listing/detail."""

    id: UUID
    org_id: UUID
    device_id: UUID
    device_mn: str
    device_name: Optional[str] = None
    name: str
    point_type: VideoPointType
    protocol: VideoProtocol
    access_method: VideoAccessMethod
    lifecycle_status: VideoLifecycleStatus
    status: VideoChannelStatus
    vendor: Optional[str] = None
    channel_code: Optional[str] = None
    network_provider: Optional[str] = None
    fixed_ip: Optional[str] = None
    install_location: Optional[str] = None
    surveyor_name: Optional[str] = None
    installer_name: Optional[str] = None
    accepted_by: Optional[str] = None
    accepted_at: Optional[datetime] = None
    acceptance_notes: Optional[str] = None
    preview_url: Optional[str] = None
    playback_url: Optional[str] = None
    ai_enabled: bool = False
    notes: Optional[str] = None
    last_seen_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class VideoEventCreate(BaseSchema):
    """Schema for creating a video event."""

    channel_id: UUID
    related_alarm_id: Optional[UUID] = None
    event_type: VideoEventType
    source: VideoEventSource = VideoEventSource.MANUAL
    level: VideoEventLevel = VideoEventLevel.WARNING
    title: str = Field(..., min_length=1, max_length=160)
    summary: Optional[str] = None
    snapshot_uri: Optional[str] = Field(None, max_length=1024)
    clip_uri: Optional[str] = Field(None, max_length=1024)
    extra_data: Optional[dict[str, Any]] = None
    occurred_at: Optional[datetime] = None


class VideoEventResponse(BaseSchema):
    """Schema returned for video event listing/detail."""

    id: UUID
    org_id: UUID
    channel_id: UUID
    channel_name: Optional[str] = None
    device_id: UUID
    device_mn: str
    device_name: Optional[str] = None
    related_alarm_id: Optional[UUID] = None
    event_type: VideoEventType
    source: VideoEventSource
    level: VideoEventLevel
    status: VideoEventStatus
    title: str
    summary: Optional[str] = None
    snapshot_uri: Optional[str] = None
    clip_uri: Optional[str] = None
    extra_data: Optional[dict[str, Any]] = None
    occurred_at: datetime
    created_at: datetime
    updated_at: Optional[datetime] = None


class VideoSummary(BaseSchema):
    """Summary metrics for the video linkage center."""

    total_channels: int = 0
    pending_survey_channels: int = 0
    pending_installation_channels: int = 0
    pending_networking_channels: int = 0
    commissioning_channels: int = 0
    accepted_channels: int = 0
    online_channels: int = 0
    ai_enabled_channels: int = 0
    fault_channels: int = 0
    today_events: int = 0
    pending_events: int = 0
    linked_alarm_events: int = 0


class VideoDemoSeedRequest(BaseSchema):
    """Request body for injecting demo video ledger data."""

    org_id: Optional[UUID] = None
    device_id: Optional[UUID] = None
    replace_existing: bool = True
    create_demo_devices_if_missing: bool = True


class VideoDemoSeedResponse(BaseSchema):
    """Result of injecting demo video ledger data."""

    success: bool = True
    message: str
    org_id: UUID
    device_count: int = 0
    created_devices: int = 0
    created_channels: int = 0
    created_events: int = 0
    created_alarms: int = 0


from app.models.alarm import Alarm
from app.models.device import Device
from app.models.organization import Organization
