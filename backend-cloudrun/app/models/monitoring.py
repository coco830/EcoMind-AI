from __future__ import annotations

"""Monitoring data models (for TDengine time-series data)."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.models.base import BaseSchema


class MonitoringDataCreate(BaseSchema):
    """Schema for creating monitoring data."""

    device_id: str = Field(..., max_length=64)
    pollutant_code: str = Field(..., max_length=32)
    org_id: str = Field(..., max_length=64)
    ts: datetime
    value: float
    flag: str = Field(default="N", max_length=10)
    status: int = Field(default=0, ge=0)


class MonitoringData(BaseSchema):
    """Schema for monitoring data record."""

    ts: datetime
    device_id: str
    pollutant_code: str
    value: float
    flag: str
    status: int


class MonitoringDataResponse(BaseSchema):
    """Schema for monitoring data response."""

    ts: datetime
    device_id: str
    pollutant_code: str
    value: float
    flag: str
    status: int


class MonitoringDataQuery(BaseSchema):
    """Schema for querying monitoring data."""

    device_id: str | None = None
    pollutant_code: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    limit: int = Field(default=1000, ge=1, le=10000)


class MonitoringDataStats(BaseSchema):
    """Schema for monitoring data statistics."""

    device_id: str
    pollutant_code: str
    min_value: float
    max_value: float
    avg_value: float
    count: int
    start_time: datetime
    end_time: datetime
