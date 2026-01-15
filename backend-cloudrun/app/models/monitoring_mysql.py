"""MySQL-based monitoring data models for time-series storage.

用于在 CloudBase MySQL 中存储监测数据，替代 TDengine。
设计原则：
1. monitoring_data: 原始时序数据表（按月分区）
2. monitoring_daily_stats: 每日聚合统计表（用于热力图和报表）
"""

from datetime import datetime, date
from typing import Optional
from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import (
    Column, String, Float, Integer, DateTime, Date, Text,
    Index, UniqueConstraint, ForeignKey
)
from sqlalchemy.dialects.mysql import DOUBLE

from app.db.postgres import Base
from app.models.base import BaseSchema


class MonitoringDataMySQL(Base):
    """MySQL 原始监测数据表

    存储每个设备每个时间点的监测数据。
    建议按月分区以优化查询性能。

    预计数据量: 50企业 × 3设备 × 288条/天 × 30天 ≈ 130万条/月
    """
    __tablename__ = "monitoring_data"

    # 主键使用自增ID，避免UUID性能问题
    id = Column(Integer, primary_key=True, autoincrement=True)

    # 时间戳 - 数据采集时间
    ts = Column(DateTime, nullable=False, index=True)

    # 设备信息
    device_id = Column(String(64), nullable=False, index=True)  # 设备MN号
    device_name = Column(String(128), nullable=True)  # 设备名称（冗余，方便查询）

    # 组织信息
    org_id = Column(String(64), nullable=False, index=True)

    # 污染物信息
    pollutant_code = Column(String(32), nullable=False, index=True)  # 如 w01018, w21003
    pollutant_name = Column(String(64), nullable=True)  # 污染物名称（冗余）

    # 监测值
    value = Column(DOUBLE, nullable=False)  # 监测值
    flag = Column(String(8), default="N")  # 数据标记 N=正常
    status = Column(Integer, default=0)  # 状态码

    # 数据类型
    data_type = Column(String(16), default="realtime")  # realtime/minute/hour/day

    # 元数据
    created_at = Column(DateTime, default=datetime.utcnow)

    # 复合索引优化常见查询
    __table_args__ = (
        Index('idx_device_ts', 'device_id', 'ts'),
        Index('idx_org_ts', 'org_id', 'ts'),
        Index('idx_device_pollutant_ts', 'device_id', 'pollutant_code', 'ts'),
        Index('idx_ts_data_type', 'ts', 'data_type'),
    )


class MonitoringDailyStats(Base):
    """每日监测数据统计表

    存储每个设备每个污染物的每日聚合数据。
    用于：
    1. 热力图展示
    2. 趋势分析
    3. 日报/周报/月报生成
    4. 数据飞轮训练数据
    """
    __tablename__ = "monitoring_daily_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 统计日期
    stat_date = Column(Date, nullable=False, index=True)

    # 设备信息
    device_id = Column(String(64), nullable=False, index=True)
    device_name = Column(String(128), nullable=True)

    # 组织信息
    org_id = Column(String(64), nullable=False, index=True)

    # 污染物信息
    pollutant_code = Column(String(32), nullable=False, index=True)
    pollutant_name = Column(String(64), nullable=True)

    # 统计值
    min_value = Column(DOUBLE, nullable=True)  # 最小值
    max_value = Column(DOUBLE, nullable=True)  # 最大值
    avg_value = Column(DOUBLE, nullable=True)  # 平均值
    sum_value = Column(DOUBLE, nullable=True)  # 总和
    data_count = Column(Integer, default=0)    # 数据点数量

    # 超标统计
    exceed_count = Column(Integer, default=0)  # 超标次数
    exceed_rate = Column(Float, default=0.0)   # 超标率 (0-1)

    # 数据质量
    valid_count = Column(Integer, default=0)   # 有效数据数量
    invalid_count = Column(Integer, default=0) # 无效数据数量

    # 元数据
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 唯一约束：每个设备每个污染物每天只有一条记录
    __table_args__ = (
        UniqueConstraint('stat_date', 'device_id', 'pollutant_code', name='uq_daily_stats'),
        Index('idx_stats_org_date', 'org_id', 'stat_date'),
        Index('idx_stats_device_date', 'device_id', 'stat_date'),
    )


class MonitoringHourlyStats(Base):
    """每小时监测数据统计表

    存储每个设备每个污染物的每小时聚合数据。
    用于更精细的趋势分析。
    """
    __tablename__ = "monitoring_hourly_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 统计时间（精确到小时）
    stat_hour = Column(DateTime, nullable=False, index=True)

    # 设备信息
    device_id = Column(String(64), nullable=False, index=True)
    org_id = Column(String(64), nullable=False, index=True)

    # 污染物信息
    pollutant_code = Column(String(32), nullable=False, index=True)

    # 统计值
    min_value = Column(DOUBLE, nullable=True)
    max_value = Column(DOUBLE, nullable=True)
    avg_value = Column(DOUBLE, nullable=True)
    data_count = Column(Integer, default=0)

    # 元数据
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('stat_hour', 'device_id', 'pollutant_code', name='uq_hourly_stats'),
        Index('idx_hourly_device', 'device_id', 'stat_hour'),
    )


# ============ Pydantic Schemas ============

class MonitoringDataMySQLCreate(BaseSchema):
    """创建监测数据的Schema"""
    device_id: str = Field(..., max_length=64)
    device_name: Optional[str] = Field(None, max_length=128)
    org_id: str = Field(..., max_length=64)
    pollutant_code: str = Field(..., max_length=32)
    pollutant_name: Optional[str] = Field(None, max_length=64)
    ts: datetime
    value: float
    flag: str = Field(default="N", max_length=8)
    status: int = Field(default=0, ge=0)
    data_type: str = Field(default="realtime", max_length=16)


class MonitoringDataMySQLResponse(BaseSchema):
    """监测数据响应Schema"""
    id: int
    ts: datetime
    device_id: str
    device_name: Optional[str]
    org_id: str
    pollutant_code: str
    pollutant_name: Optional[str]
    value: float
    flag: str
    status: int
    data_type: str


class MonitoringDailyStatsResponse(BaseSchema):
    """每日统计响应Schema"""
    id: int
    stat_date: date
    device_id: str
    device_name: Optional[str]
    org_id: str
    pollutant_code: str
    pollutant_name: Optional[str]
    min_value: Optional[float]
    max_value: Optional[float]
    avg_value: Optional[float]
    data_count: int
    exceed_count: int
    exceed_rate: float


class HeatmapDataPoint(BaseSchema):
    """热力图数据点Schema"""
    lat: float  # 纬度
    lng: float  # 经度
    value: float  # 监测值
    device_id: str
    device_name: str
    pollutant_code: str
    pollutant_name: str
    stat_date: date
