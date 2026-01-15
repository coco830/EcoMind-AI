from __future__ import annotations

"""Self-inspection report models for OCR-based inspection data management."""

from datetime import datetime, date
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import String, DateTime, ForeignKey, Float, Text, Boolean, Integer, Date, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base, GUID
from app.models.base import BaseSchema


class InspectionStatus(str, Enum):
    """Inspection report status enumeration."""

    PENDING = "pending"  # 待校验
    VERIFIED = "verified"  # 已校验
    REJECTED = "rejected"  # 已拒绝


class SelfInspectionReport(Base):
    """Self-inspection report ORM model - 企业自行检测报告."""

    __tablename__ = "self_inspection_reports"
    __table_args__ = (
        Index('ix_self_inspection_org_id', 'org_id'),
        Index('ix_self_inspection_date', 'inspection_date'),
        Index('ix_self_inspection_status', 'status'),
    )

    id: Mapped[UUID] = mapped_column(GUID, primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(GUID, ForeignKey("organizations.id"), nullable=False)

    # 检测报告基本信息
    inspection_date: Mapped[date] = mapped_column(Date, nullable=False)  # 检测日期
    inspection_agency: Mapped[str] = mapped_column(String(256), nullable=False)  # 检测机构名称
    report_number: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)  # 报告编号

    # 文件信息
    original_file_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)  # 原始报告文件路径
    original_file_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)  # 原始文件名

    # OCR识别信息
    ocr_raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # OCR原始识别文本
    ocr_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # OCR识别置信度

    # 状态信息
    status: Mapped[str] = mapped_column(String(32), default=InspectionStatus.PENDING.value)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否人工校验
    verified_by: Mapped[Optional[UUID]] = mapped_column(GUID, ForeignKey("users.id"), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # 备注
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="self_inspection_reports")
    data_items: Mapped[list["SelfInspectionData"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )


class SelfInspectionData(Base):
    """Self-inspection data item ORM model - 自检数据明细."""

    __tablename__ = "self_inspection_data"
    __table_args__ = (
        Index('ix_self_inspection_data_report_id', 'report_id'),
        Index('ix_self_inspection_data_pollutant', 'pollutant_code'),
    )

    id: Mapped[UUID] = mapped_column(GUID, primary_key=True, default=uuid4)
    report_id: Mapped[UUID] = mapped_column(GUID, ForeignKey("self_inspection_reports.id"), nullable=False)

    # 污染物信息
    pollutant_code: Mapped[str] = mapped_column(String(32), nullable=False)  # 污染物代码
    pollutant_name: Mapped[str] = mapped_column(String(128), nullable=False)  # 污染物名称

    # 检测值 (支持科学计数法字符串，如 "4.0×10²")
    value: Mapped[str] = mapped_column(String(64), nullable=False)  # 检测值
    unit: Mapped[str] = mapped_column(String(32), default="mg/L")  # 单位

    # 标准限值 (支持科学计数法字符串)
    standard_limit: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # 标准限值
    is_compliant: Mapped[bool] = mapped_column(Boolean, default=True)  # 是否达标

    # 采样信息
    sampling_point: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)  # 采样点位
    sampling_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)  # 采样时间

    # 备注
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    report: Mapped["SelfInspectionReport"] = relationship(back_populates="data_items")


# ============== Pydantic Schemas ==============

class SelfInspectionDataCreate(BaseSchema):
    """Schema for creating inspection data item."""

    pollutant_code: str = Field(..., min_length=1, max_length=32)
    pollutant_name: str = Field(..., min_length=1, max_length=128)
    value: str = Field(..., min_length=1, max_length=64)  # 支持科学计数法如 "4.0×10²"
    unit: str = Field(default="mg/L", max_length=32)
    standard_limit: Optional[str] = Field(None, max_length=64)  # 支持科学计数法
    is_compliant: bool = Field(default=True)
    sampling_point: Optional[str] = Field(None, max_length=256)
    sampling_time: Optional[datetime] = None
    remarks: Optional[str] = None


class SelfInspectionDataResponse(BaseSchema):
    """Schema for inspection data item response."""

    id: UUID
    report_id: UUID
    pollutant_code: str
    pollutant_name: str
    value: str  # 支持科学计数法字符串
    unit: str
    standard_limit: Optional[str] = None  # 支持科学计数法字符串
    is_compliant: bool
    sampling_point: Optional[str] = None
    sampling_time: Optional[datetime] = None
    remarks: Optional[str] = None
    created_at: datetime


class SelfInspectionReportCreate(BaseSchema):
    """Schema for creating inspection report."""

    inspection_date: date
    inspection_agency: str = Field(..., min_length=1, max_length=256)
    report_number: Optional[str] = Field(None, max_length=128)
    remarks: Optional[str] = None
    data_items: list[SelfInspectionDataCreate] = Field(default_factory=list)


class SelfInspectionReportUpdate(BaseSchema):
    """Schema for updating inspection report."""

    inspection_date: Optional[date] = None
    inspection_agency: Optional[str] = Field(None, max_length=256)
    report_number: Optional[str] = Field(None, max_length=128)
    status: Optional[InspectionStatus] = None
    remarks: Optional[str] = None
    data_items: Optional[list[SelfInspectionDataCreate]] = None


class SelfInspectionReportResponse(BaseSchema):
    """Schema for inspection report response."""

    id: UUID
    org_id: UUID
    inspection_date: date
    inspection_agency: str
    report_number: Optional[str] = None
    original_file_name: Optional[str] = None
    ocr_confidence: Optional[float] = None
    status: InspectionStatus
    is_verified: bool
    verified_at: Optional[datetime] = None
    remarks: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    data_items: list[SelfInspectionDataResponse] = Field(default_factory=list)


class SelfInspectionReportListResponse(BaseSchema):
    """Schema for inspection report list item (without data_items for performance)."""

    id: UUID
    org_id: UUID
    inspection_date: date
    inspection_agency: str
    report_number: Optional[str] = None
    original_file_name: Optional[str] = None
    status: InspectionStatus
    is_verified: bool
    data_count: int = 0  # 数据项数量
    created_at: datetime


class OCRUploadResponse(BaseSchema):
    """Schema for OCR upload response."""

    report_id: UUID
    ocr_confidence: Optional[float] = None
    recognized_data: list[SelfInspectionDataCreate] = Field(default_factory=list)
    raw_text: Optional[str] = None
    message: str = "OCR识别完成，请校验数据"


class TrendAnalysisRequest(BaseSchema):
    """Schema for trend analysis request."""

    start_date: date
    end_date: date
    pollutant_codes: Optional[list[str]] = None
    target_org_id: Optional[UUID] = None  # 超级管理员按企业过滤


class TrendDataPoint(BaseSchema):
    """Schema for trend data point."""

    date: date
    pollutant_code: str
    pollutant_name: str
    value: str  # 支持科学计数法字符串
    unit: str
    standard_limit: Optional[str] = None  # 支持科学计数法字符串
    is_compliant: bool


class TrendAnalysisResponse(BaseSchema):
    """Schema for trend analysis response."""

    start_date: date
    end_date: date
    data_points: list[TrendDataPoint] = Field(default_factory=list)
    statistics: dict = Field(default_factory=dict)  # 统计信息


class AIReportRequest(BaseSchema):
    """Schema for AI report generation request."""

    start_date: date
    end_date: date
    report_type: str = Field(default="monthly", pattern="^(monthly|quarterly)$")
    include_flow_data: bool = Field(default=False, description="是否整合数采仪瞬时流量数据")
    calculate_pollutant_load: bool = Field(default=False, description="是否计算污染负荷")
    target_org_id: Optional[UUID] = Field(default=None, description="目标组织ID（超级管理员生成报告时指定）")


class AIReportResponse(BaseSchema):
    """Schema for AI report response."""

    report_id: Optional[UUID] = None
    period: str
    generated_at: datetime
    summary: str  # AI生成的摘要
    recommendations: list[str] = Field(default_factory=list)  # AI运维建议
    data_source_note: str = "本报告基于企业提交的第三方检测机构报告数据生成，数据准确性以原始检测报告为准。"
    flow_data: Optional[dict] = Field(default=None, description="数采仪在线数据摘要（如流量等）")
    online_data: Optional[dict] = Field(default=None, description="数采仪在线数据统计（按指标汇总）")
    pollutant_loads: Optional[dict] = Field(default=None, description="污染负荷数据（流量×浓度）")


# ============== Device Flow Schemas (Read-only from Data Acquisition Device) ==============

class FlowTrendPoint(BaseSchema):
    """Schema for flow trend data point - 流量趋势数据点."""

    ts: datetime
    value: float
    flag: str = "N"


class DeviceFlowResponse(BaseSchema):
    """Schema for device flow data response - 设备流量数据响应.

    Note: This data is READ-ONLY from the data acquisition device (数采仪).
    It is NOT stored in the self-inspection report tables.
    """

    device_id: str = Field(..., description="设备MN号")
    device_name: str = Field(..., description="设备名称")
    device_status: str = Field(..., description="设备状态 (online/offline/alarm)")
    latest_flow: Optional[float] = Field(None, description="最新瞬时流量值")
    latest_flow_ts: Optional[datetime] = Field(None, description="最新流量数据时间")
    flow_unit: str = Field(default="L/s", description="流量单位")
    data_source: str = Field(default="datacollector", description="数据来源标识")
    trend_data: Optional[list[FlowTrendPoint]] = Field(default=None, description="流量趋势数据")


class DeviceFlowListResponse(BaseSchema):
    """Schema for device flow list response - 设备流量列表响应.

    This endpoint provides READ-ONLY access to instantaneous flow data
    from the environmental monitoring data acquisition devices.
    The data is clearly labeled and NOT stored in self-inspection reports.
    """

    devices: list[DeviceFlowResponse] = Field(default_factory=list)
    org_name: str = Field(..., description="企业名称")
    query_time: datetime = Field(..., description="查询时间")
    data_source_note: str = Field(
        default="数据来自环境监测数采仪（只读），不存储到自检报告",
        description="数据来源说明"
    )


class FlowStatistics(BaseSchema):
    """Schema for flow statistics - 流量统计数据."""

    avg_flow: float = Field(..., description="平均流量")
    max_flow: float = Field(..., description="最大流量")
    min_flow: float = Field(..., description="最小流量")
    total_volume: float = Field(..., description="总流量体积 (m³)")
    unit: str = Field(default="L/s", description="流量单位")
    data_points_count: int = Field(..., description="数据点数量")


# ============== Online Monitoring Schemas (Device -> Pollutant Metric) ==============

class OnlineMetricOption(BaseSchema):
    """在线监测指标选项（来自 monitoring_data 的实际出现情况）"""

    pollutant_code: str
    pollutant_name: str
    unit: Optional[str] = None


class DeviceOnlineMetricResponse(BaseSchema):
    """设备在线监测数据响应（按指定指标返回，支持趋势点）"""

    device_id: str = Field(..., description="设备MN号")
    device_name: str = Field(..., description="设备名称")
    device_status: str = Field(..., description="设备状态 (online/offline/alarm)")
    pollutant_code: str = Field(..., description="指标代码，如 w00000/w01018")
    pollutant_name: str = Field(..., description="指标名称")
    unit: Optional[str] = Field(default=None, description="单位")
    latest_value: Optional[float] = Field(None, description="最新值")
    latest_ts: Optional[datetime] = Field(None, description="最新值时间")
    data_source: str = Field(default="datacollector", description="数据来源标识")
    trend_data: Optional[list[FlowTrendPoint]] = Field(default=None, description="趋势数据")


class DeviceOnlineMetricListResponse(BaseSchema):
    """企业在线监测数据列表（按指标）"""

    pollutant_code: str
    pollutant_name: str
    unit: Optional[str] = None
    devices: list[DeviceOnlineMetricResponse] = Field(default_factory=list)
    org_name: str = Field(..., description="企业名称")
    query_time: datetime = Field(..., description="查询时间")
    data_source_note: str = Field(
        default="数据来自环境监测数采仪（只读），不存储到自检报告",
        description="数据来源说明",
    )


# Import for type hints
from app.models.organization import Organization
