# Data Model: EcoMind-AI 智慧环保 SaaS 平台 MVP

**Feature**: 001-ecomind-mvp
**Date**: 2025-11-24

## Overview

本文档定义系统的核心数据实体及其关系。数据分为两类存储：
- **时序数据**: 存储在 TDengine，包括监测数据、报警记录
- **业务数据**: 存储在 PostgreSQL，包括设备、用户、组织

---

## Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────┐
│   Organization  │───────│      User       │
│   (组织/企业)    │ 1:N   │    (用户)       │
└─────────────────┘       └─────────────────┘
        │                         │
        │ 1:N                     │ N:M
        ▼                         ▼
┌─────────────────┐       ┌─────────────────┐
│     Device      │───────│   UserDevice    │
│   (数采仪设备)   │       │   (权限关联)    │
└─────────────────┘       └─────────────────┘
        │
        │ 1:N (TDengine 超级表)
        ▼
┌─────────────────┐       ┌─────────────────┐
│ MonitoringData  │───────│     Alarm       │
│   (监测数据)     │ 1:N   │    (报警)       │
└─────────────────┘       └─────────────────┘
```

---

## Entity Definitions

### 1. Organization (组织/企业)

**描述**: 监控设备所属的企业或组织单位

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | 主键 |
| name | String(100) | NOT NULL, UNIQUE | 组织名称 |
| code | String(20) | UNIQUE | 统一社会信用代码 |
| address | String(200) | | 地址 |
| contact_name | String(50) | | 联系人 |
| contact_phone | String(20) | | 联系电话 |
| created_at | DateTime | NOT NULL | 创建时间 |
| updated_at | DateTime | NOT NULL | 更新时间 |

**Validation Rules**:
- `name` 长度 2-100 字符
- `code` 格式为 18 位统一社会信用代码（可选）

---

### 2. User (用户)

**描述**: 系统操作用户

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | 主键 |
| username | String(50) | NOT NULL, UNIQUE | 用户名 |
| password_hash | String(128) | NOT NULL | 密码哈希 (bcrypt) |
| email | String(100) | UNIQUE | 邮箱 |
| role | Enum | NOT NULL | 角色: admin/operator/viewer |
| organization_id | UUID | FK -> Organization | 所属组织 |
| is_active | Boolean | NOT NULL, DEFAULT true | 是否激活 |
| last_login | DateTime | | 最后登录时间 |
| created_at | DateTime | NOT NULL | 创建时间 |
| updated_at | DateTime | NOT NULL | 更新时间 |

**Role Enum**:
- `admin`: 管理员，可管理所有资源
- `operator`: 操作员，可查看数据和处理报警
- `viewer`: 查看者，只能查看数据

**Validation Rules**:
- `username` 长度 3-50 字符，字母数字下划线
- `password` 原始密码长度 8-32 字符，包含大小写和数字
- `email` 有效邮箱格式

---

### 3. Device (数采仪设备)

**描述**: 接入系统的数采仪设备

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | 主键 |
| mn | String(20) | NOT NULL, UNIQUE | 设备唯一标识 (MN号) |
| name | String(100) | NOT NULL | 设备名称/排口名称 |
| organization_id | UUID | FK -> Organization, NOT NULL | 所属组织 |
| st | String(4) | NOT NULL | 系统编码 (如 22=水, 31=气) |
| latitude | Decimal(10,7) | | 纬度 |
| longitude | Decimal(10,7) | | 经度 |
| status | Enum | NOT NULL, DEFAULT 'offline' | 在线状态 |
| last_data_time | DateTime | | 最后数据时间 |
| last_heartbeat | DateTime | | 最后心跳时间 |
| sm4_key | String(32) | | SM4 加密密钥 (Hex) |
| created_at | DateTime | NOT NULL | 创建时间 |
| updated_at | DateTime | NOT NULL | 更新时间 |

**Status Enum**:
- `online`: 在线（5分钟内有数据）
- `offline`: 离线（超过5分钟无数据）
- `warning`: 预警（数据异常但仍在上报）
- `disabled`: 停用

**ST (系统编码) 常用值**:
| Code | Description |
|------|-------------|
| 21 | 地表水质量监测 |
| 22 | 空气质量监测 |
| 31 | 大气环境污染源 |
| 32 | 地表水体环境污染源 |
| 51 | 噪声监测 |

**Validation Rules**:
- `mn` 长度 14-24 字符
- `st` 长度 2-4 字符
- `latitude` 范围 -90 到 90
- `longitude` 范围 -180 到 180

---

### 4. MonitoringData (监测数据) - TDengine

**描述**: 时序监测数据，存储在 TDengine 超级表中

**Super Table (STable) Schema**:
```sql
CREATE STABLE monitoring_data (
    ts TIMESTAMP,
    param_code NCHAR(20),
    rtd DOUBLE,           -- 实时值
    min DOUBLE,           -- 最小值
    max DOUBLE,           -- 最大值
    avg DOUBLE,           -- 平均值
    flag NCHAR(1),        -- 数据标记
    is_anomaly BOOL,      -- 异常标记
    anomaly_reason NCHAR(100)  -- 异常原因
) TAGS (
    mn NCHAR(20),
    st NCHAR(4),
    param_name NCHAR(50)
);
```

| Field | Type | Description |
|-------|------|-------------|
| ts | Timestamp | 数据时间戳 (主键) |
| param_code | String(20) | 参数编码 (如 w01001, d20101) |
| rtd | Double | 实时值 (Real-Time Data) |
| min | Double | 分钟/小时最小值 |
| max | Double | 分钟/小时最大值 |
| avg | Double | 分钟/小时平均值 |
| flag | Char(1) | 数据标记 (N=正常, D=故障, M=维护, C=校准) |
| is_anomaly | Boolean | AI 异常检测标记 |
| anomaly_reason | String(100) | 异常原因说明 |

**Tags**:
| Tag | Type | Description |
|-----|------|-------------|
| mn | String(20) | 设备 MN 号 |
| st | String(4) | 系统编码 |
| param_name | String(50) | 参数名称 |

**常用参数编码**:

| Code | Category | Name | Unit |
|------|----------|------|------|
| w01001 | 污染物 | pH值 | - |
| w01010 | 污染物 | 水温 | ℃ |
| w01018 | 污染物 | 化学需氧量 (COD) | mg/L |
| w21003 | 污染物 | 氨氮 | mg/L |
| w21011 | 污染物 | 总磷 | mg/L |
| a34004 | 污染物 | PM2.5 | μg/m³ |
| d20101 | 用电 | 风机电流 | A |
| d20102 | 用电 | 水泵电流 | A |
| p20001 | 工况 | 风机运行状态 | - |
| p20002 | 工况 | 水泵运行状态 | - |

---

### 5. Alarm (报警记录)

**描述**: 系统产生的报警记录

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | 主键 |
| device_id | UUID | FK -> Device, NOT NULL | 关联设备 |
| type | Enum | NOT NULL | 报警类型 |
| level | Enum | NOT NULL | 报警级别 |
| param_code | String(20) | | 相关参数编码 |
| threshold | Double | | 阈值 |
| actual_value | Double | | 实际值 |
| message | String(500) | NOT NULL | 报警描述 |
| status | Enum | NOT NULL, DEFAULT 'pending' | 处理状态 |
| acknowledged_by | UUID | FK -> User | 确认人 |
| acknowledged_at | DateTime | | 确认时间 |
| resolved_at | DateTime | | 解决时间 |
| created_at | DateTime | NOT NULL | 创建时间 |

**Type Enum (报警类型)**:
- `exceed`: 超标报警
- `offline`: 设备离线
- `anomaly`: AI 检测异常
- `fault`: 设备故障 (Flag=D)
- `maintenance`: 设备维护 (Flag=M)

**Level Enum (报警级别)**:
- `critical`: 严重（红色）
- `warning`: 警告（橙色）
- `info`: 提示（黄色）

**Status Enum (处理状态)**:
- `pending`: 待处理
- `acknowledged`: 已确认
- `resolved`: 已解决
- `ignored`: 已忽略

---

## State Transitions

### Device Status State Machine

```
           ┌─────────────────┐
           │    disabled     │
           └────────┬────────┘
                    │ enable
                    ▼
           ┌─────────────────┐
      ┌────│     offline     │◄────┐
      │    └────────┬────────┘     │
      │             │ receive data │ timeout (5min)
      │             ▼              │
      │    ┌─────────────────┐     │
      │    │     online      │─────┘
      │    └────────┬────────┘
      │             │ anomaly detected
      │             ▼
      │    ┌─────────────────┐
      │    │    warning      │
      │    └─────────────────┘
      │             │ disable
      └─────────────┴──────────────►
```

### Alarm Status State Machine

```
     ┌─────────────────┐
     │     pending     │
     └────────┬────────┘
              │
     ┌────────┴────────┐
     │                 │
     ▼                 ▼
┌─────────┐      ┌─────────┐
│acknowledged│    │ ignored │
└─────┬───┘      └─────────┘
      │
      ▼
┌─────────────────┐
│    resolved     │
└─────────────────┘
```

---

## Indexes

### PostgreSQL Indexes

```sql
-- Device
CREATE INDEX idx_device_organization ON devices(organization_id);
CREATE INDEX idx_device_status ON devices(status);
CREATE INDEX idx_device_mn ON devices(mn);

-- Alarm
CREATE INDEX idx_alarm_device ON alarms(device_id);
CREATE INDEX idx_alarm_status ON alarms(status);
CREATE INDEX idx_alarm_type ON alarms(type);
CREATE INDEX idx_alarm_created ON alarms(created_at DESC);

-- User
CREATE INDEX idx_user_organization ON users(organization_id);
CREATE INDEX idx_user_role ON users(role);
```

### TDengine Indexes

TDengine 自动为 Tags 创建索引，无需手动创建。时间戳 `ts` 是主键，自动排序。

---

## Data Retention

| Data Type | Retention Period | Storage |
|-----------|------------------|---------|
| 监测数据 (原始) | 3 年 | TDengine |
| 监测数据 (聚合) | 5 年 | TDengine |
| 报警记录 | 永久 | PostgreSQL |
| 用户操作日志 | 1 年 | PostgreSQL |

**TDengine 数据保留配置**:
```sql
CREATE DATABASE ecomind KEEP 1095 DAYS(2) BLOCKS(6);
```

---

## Pydantic Models (Python)

```python
# models/device.py
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
from uuid import UUID

class DeviceStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    WARNING = "warning"
    DISABLED = "disabled"

class DeviceCreate(BaseModel):
    mn: str = Field(..., min_length=14, max_length=24)
    name: str = Field(..., min_length=1, max_length=100)
    organization_id: UUID
    st: str = Field(..., min_length=2, max_length=4)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)

class DeviceResponse(DeviceCreate):
    id: UUID
    status: DeviceStatus
    last_data_time: datetime | None
    last_heartbeat: datetime | None
    created_at: datetime
    updated_at: datetime

# models/monitoring.py
class MonitoringDataPoint(BaseModel):
    ts: datetime
    param_code: str
    rtd: float | None
    min: float | None
    max: float | None
    avg: float | None
    flag: str = "N"
    is_anomaly: bool = False
    anomaly_reason: str | None = None

# models/alarm.py
class AlarmType(str, Enum):
    EXCEED = "exceed"
    OFFLINE = "offline"
    ANOMALY = "anomaly"
    FAULT = "fault"
    MAINTENANCE = "maintenance"

class AlarmLevel(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"

class AlarmStatus(str, Enum):
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    IGNORED = "ignored"
```
