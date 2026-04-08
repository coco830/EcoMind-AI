"""LLM-friendly response schemas for OpenAPI agent integrations.

All responses are designed to be easily understood by LLM agents,
with Chinese descriptions, compliance status, and summary fields.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.models.base import BaseSchema


# ---------------------------------------------------------------------------
# Common wrapper
# ---------------------------------------------------------------------------

class OpenApiResponse(BaseSchema):
    """Standard wrapper for all OpenAPI responses."""
    success: bool = True
    data: Any = None
    summary: str = Field(default="", description="一句话总结，帮助 LLM 组织回答")


class OpenApiError(BaseSchema):
    """LLM-friendly error response."""
    success: bool = False
    error_code: str
    message: str
    possible_reasons: list[str] = Field(default_factory=list)
    suggestion: str = ""


# ---------------------------------------------------------------------------
# Tool 1: get_device_status
# ---------------------------------------------------------------------------

class DeviceStatusItem(BaseModel):
    """Single device status for LLM consumption."""
    device_name: str = Field(description="设备名称")
    enterprise: str = Field(description="所属企业名称")
    device_type: str = Field(description="设备类型（水质/大气/噪声/土壤）")
    status: str = Field(description="当前状态（在线/离线/报警/维护）")
    industry_type: str = Field(default="", description="行业类型")
    national_standard: str = Field(default="", description="执行标准")
    address: str = Field(default="", description="安装地址")
    last_heartbeat: str = Field(default="", description="最后通讯时间")
    online_duration: str = Field(default="", description="在线时长描述")

DEVICE_TYPE_NAMES = {
    "water": "水质监测",
    "air": "大气监测",
    "noise": "噪声监测",
    "soil": "土壤监测",
}

DEVICE_STATUS_NAMES = {
    "online": "在线",
    "offline": "离线",
    "alarm": "报警",
    "maintenance": "维护中",
}


class DeviceStatusSummary(BaseModel):
    """Aggregated device status summary."""
    total: int = Field(description="设备总数")
    online: int = Field(description="在线数量")
    offline: int = Field(description="离线数量")
    alarm: int = Field(description="报警数量")
    maintenance: int = Field(description="维护中数量")


class DeviceStatusResponse(OpenApiResponse):
    """Response for get_device_status tool."""
    data: Optional[dict] = None  # Will contain {"devices": [...], "status_summary": {...}}


# ---------------------------------------------------------------------------
# Tool 2: get_latest_data
# ---------------------------------------------------------------------------

class PollutantReading(BaseModel):
    """Single pollutant reading for LLM consumption."""
    pollutant: str = Field(description="污染物名称，如 COD (化学需氧量)")
    pollutant_code: str = Field(description="HJ212 标准编码")
    current_value: float = Field(description="当前监测值")
    unit: str = Field(description="计量单位")
    threshold: Optional[float] = Field(None, description="排放标准限值")
    compliance_status: str = Field(default="未知", description="达标状态：达标/接近超标/超标/未知")
    risk_level: str = Field(default="normal", description="风险等级：normal/warning/critical")
    percentage_of_limit: str = Field(default="", description="占限值百分比")
    data_quality: str = Field(default="正常", description="数据质量描述")
    measurement_time: str = Field(default="", description="测量时间")


FLAG_DESCRIPTIONS = {
    "N": "正常（实时自动采集）",
    "D": "设备故障（数据可能不准确）",
    "M": "手工录入数据",
    "C": "校准数据",
    "T": "超测量上限",
    "": "正常",
}


class LatestDataResponse(OpenApiResponse):
    """Response for get_latest_data tool."""
    data: Optional[dict] = None  # {"device_name", "enterprise", "readings": [...], "standard": "..."}


# ---------------------------------------------------------------------------
# Tool 3: get_active_alarms
# ---------------------------------------------------------------------------

class AlarmItem(BaseModel):
    """Single alarm for LLM consumption."""
    alarm_id: str = Field(description="报警记录ID")
    device_name: str = Field(description="设备名称")
    enterprise: str = Field(description="所属企业")
    alarm_type: str = Field(description="报警类型")
    severity: str = Field(description="严重程度：信息/警告/严重")
    pollutant: str = Field(default="", description="相关污染物")
    message: str = Field(description="报警描述")
    current_value: str = Field(default="", description="当前值")
    threshold: str = Field(default="", description="阈值")
    created_at: str = Field(description="报警时间")
    duration: str = Field(default="", description="持续时长")

ALARM_TYPE_NAMES = {
    "threshold": "超标报警",
    "anomaly": "AI异常检测",
    "offline": "设备离线",
    "flag": "数据标记异常",
}

ALARM_LEVEL_NAMES = {
    "info": "信息",
    "warning": "警告",
    "critical": "严重",
}


class AlarmsSummary(BaseModel):
    """Alarm statistics summary."""
    total_pending: int = Field(description="待处理报警总数")
    critical: int = Field(default=0, description="严重报警数")
    warning: int = Field(default=0, description="警告数")
    info: int = Field(default=0, description="信息提示数")


class ActiveAlarmsResponse(OpenApiResponse):
    """Response for get_active_alarms tool."""
    data: Optional[dict] = None  # {"alarms": [...], "summary": {...}}


# ---------------------------------------------------------------------------
# Tool 4: get_ai_prediction
# ---------------------------------------------------------------------------

class PredictionPoint(BaseModel):
    """Single prediction data point."""
    time: str = Field(description="预测时间点")
    predicted_value: float = Field(description="预测值")
    lower_bound: Optional[float] = Field(None, description="置信区间下限")
    upper_bound: Optional[float] = Field(None, description="置信区间上限")


class PredictionResponse(OpenApiResponse):
    """Response for get_ai_prediction tool."""
    data: Optional[dict] = None
    # {
    #   "device_name", "enterprise", "pollutant", "unit", "threshold",
    #   "current_value", "prediction_hours",
    #   "predictions": [...],
    #   "risk_assessment": {"max_predicted", "min_predicted", "exceed_risk", "risk_time"},
    # }


# ---------------------------------------------------------------------------
# Tool 5: get_ai_report
# ---------------------------------------------------------------------------

class AiReportResponse(OpenApiResponse):
    """Response for get_ai_report tool."""
    data: Optional[dict] = None
    # {
    #   "device_name", "enterprise", "report_date",
    #   "report_content", "report_status",
    #   "stats_snapshot": {...},
    # }
