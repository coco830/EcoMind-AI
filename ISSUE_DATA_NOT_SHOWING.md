# 问题报告：前端无法显示监测数据

## 问题概述

EcoMind-AI 环保监测平台前端仪表盘无法显示设备上报的监测数据。所有污染物指标（COD、氨氮、pH、瞬时流量等）均显示为 `--`（无数据），但云托管日志显示数据确实在接收。

---

## 环境信息

| 组件 | 技术栈 | 部署位置 |
|------|--------|----------|
| 前端 | Vue 3 + Vite + Element Plus | 腾讯云 CloudBase 静态托管 |
| 后端 | Python 3.11 + FastAPI | 腾讯云 CloudBase 云托管 |
| 时序数据库 | TDengine | 腾讯云托管版 |
| 业务数据库 | PostgreSQL (CynosDB) | 腾讯云 |
| 数据协议 | HJ 212-2017 环境监测标准 | TCP 端口 9880 |

---

## 现象描述

### 1. 设备数据确实在到达后端
云托管日志显示：
```
Device authenticated successfully mn=125301024WHYY1
Monitoring data processed mn=125301024WHYY1 cn=2011 data_type=realtime pollutant_count=1
pollutant_code=w00000 value=0.08
```

### 2. 前端 API 返回空数组
```
GET /api/v1/dashboard/device-pollutants?device_id=125301024WHYY1&hours=24
Response: []
Response Time: 10-13ms (很快返回，说明查询执行了但没数据)
```

### 3. 仪表盘显示
- 设备总数: 1 ✓
- 设备在线: 1 ✓
- 数据点数: 0 ✗ (应该有数据)
- 所有污染物值: `--` ✗

---

## 数据流架构

```
设备 (HJ212协议 TCP)
       ↓
tcp_server.py (TCP Gateway, 端口9880)
       ↓ 解析
hj212_parser.py (协议解析)
       ↓ 认证
device_registry.py (查PostgreSQL验证设备)
       ↓ 存储
tdengine_client.py (写入TDengine)
       ↓
┌──────────────────────────────────────┐
│  TDengine 数据库                      │
│  ├── meters_data (宽表)              │
│  └── monitoring_data (窄表) ← API查询 │
└──────────────────────────────────────┘
       ↓
dashboard.py (API端点)
       ↓
前端 Vue 组件
```

---

## 已尝试的修复

### 修复1: 参数名不匹配 (核心问题)

**文件**: `backend/app/gateway/tcp_server.py` 第350-358行

**问题**: 调用 `insert_monitoring_data()` 时参数名写错了

```python
# 错误代码 (修复前)
await tdengine.insert_monitoring_data(
    device_id=packet.mn,
    pollutant_code=pol_code,
    org_id=org_id,
    ts=data_time,        # ❌ 错误！参数名是 ts
    value=float(value),
    flag=str(flag),
    status=0,
)

# 正确代码 (修复后)
await tdengine.insert_monitoring_data(
    device_id=packet.mn,
    pollutant_code=pol_code,
    org_id=org_id,
    timestamp=data_time,  # ✅ 正确！参数名是 timestamp
    value=float(value),
    flag=str(flag),
    status=0,
)
```

**方法定义** (`tdengine_client.py` 第353-362行):
```python
async def insert_monitoring_data(
    self,
    device_id: str,
    pollutant_code: str,
    org_id: str,
    timestamp: datetime,  # ← 参数名是 timestamp，不是 ts
    value: float,
    flag: str = "N",
    status: int = 0
) -> bool:
```

**状态**: 已在本地修复，已打包新的 `backend-deploy.zip`，已部署到云托管，但问题仍然存在。

---

### 修复2: 时区问题

**文件**: `backend/app/api/v1/dashboard.py`

**问题**: 设备发送北京时间(UTC+8)，服务器可能是UTC，查询时间范围不匹配

**修复**: 添加9小时缓冲
```python
# 修复前
end_time = datetime.now()
start_time = end_time - timedelta(hours=hours)

# 修复后
end_time = datetime.now() + timedelta(hours=9)  # 未来缓冲
start_time = end_time - timedelta(hours=hours + 9)  # 额外缓冲
```

**状态**: 已修复并部署，问题仍然存在。

---

## 待排查的可能原因

### 1. TDengine Mock 模式
`tdengine_client.py` 第22行:
```python
MOCK_MODE = os.getenv("TDENGINE_MOCK", "false").lower() in ("true", "1", "yes")
```
如果 `TDENGINE_MOCK=true`，数据只存内存，不写真实数据库。

**需要检查**: 云托管环境变量设置

### 2. 宽表写入成功，窄表写入失败
`tcp_server.py` 同时写入两个表：
- 第317-338行: 写入宽表 `meters_data`
- 第341-366行: 写入窄表 `monitoring_data`

但 API 只查询窄表。如果窄表写入失败（因为参数名错误），数据就查不到。

**需要检查**: 云托管日志是否有 `Failed to insert monitoring data (narrow table)` 错误

### 3. 异常被静默捕获
```python
try:
    await tdengine.insert_monitoring_data(...)
except Exception as e:
    logger.error("Failed to insert monitoring data (narrow table)", ...)
    # 没有抛出异常，继续执行
```

错误可能只记录了日志但没有明显提示。

### 4. 部署缓存问题
云托管可能有镜像缓存，新代码可能没有真正生效。

### 5. TDengine 连接问题
需要确认 TDengine REST API 连接是否正常建立。

---

## 关键文件

| 文件 | 路径 | 作用 |
|------|------|------|
| TCP网关 | `backend/app/gateway/tcp_server.py` | 接收设备数据，写入数据库 |
| 协议解析 | `backend/app/gateway/hj212_parser.py` | 解析HJ212数据包 |
| 设备认证 | `backend/app/gateway/device_registry.py` | 验证设备MN号 |
| 数据库客户端 | `backend/app/db/tdengine_client.py` | TDengine操作 |
| 仪表盘API | `backend/app/api/v1/dashboard.py` | 前端数据接口 |
| 配置 | `backend/app/core/config.py` | 环境变量配置 |

---

## 建议的调试方向

1. **检查云托管日志**，搜索:
   - `TypeError` (参数名错误会报这个)
   - `Failed to insert`
   - `TDengine error`

2. **检查环境变量**:
   - `TDENGINE_MOCK` 应该是 `false` 或未设置
   - TDengine 连接参数是否正确

3. **直接查询 TDengine** (如果有权限):
   ```sql
   SELECT * FROM monitoring_data LIMIT 10;
   SELECT * FROM meters_data LIMIT 10;
   ```

4. **添加调试日志**: 在 `insert_monitoring_data` 方法入口添加日志确认是否被调用

5. **确认部署生效**: 可以在代码中添加一个明显的标记（如版本号），通过API确认新代码是否真正部署

---

## 部署包位置

最新修复后的部署包: `E:\EcoMind-AI\backend\backend-deploy.zip`

包含文件:
- `app/` (完整后端代码)
- `alembic/` (数据库迁移)
- `requirements.txt`
- `requirements-cloudbase.txt`
- `alembic.ini`
- `Dockerfile`
- `Dockerfile.cloudbase`
- `cloudbaserc.json`
