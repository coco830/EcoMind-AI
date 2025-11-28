# Research: EcoMind-AI 智慧环保 SaaS 平台 MVP

**Feature**: 001-ecomind-mvp
**Date**: 2025-11-24
**Status**: Complete

## 1. HJ 212 协议解析

### Decision
采用状态机模式实现 HJ 212 协议解析器，支持 2017 和 2025 双标准。

### Rationale
- HJ 212 报文结构复杂，包含嵌套的键值对和特殊分隔符
- 状态机模式比正则表达式更可靠，符合 Constitution 要求
- 可以优雅处理粘包/拆包问题

### HJ 212 报文格式
```
##数据段长度数据段CRC16\r\n
```

**数据段结构**:
```
QN=YYYYMMDDHHmmsszzz;ST=系统编码;CN=命令编码;PW=访问密码;MN=设备唯一标识;Flag=标志位;CP=&&数据区&&
```

**关键字段**:
- `QN`: 请求编号，时间戳格式
- `ST`: 系统编码（如 22=地表水，31=大气）
- `CN`: 命令编码（如 2011=实时数据，2051=分钟数据）
- `MN`: 设备唯一标识（14位）
- `Flag`: 标志位（V=版本，D=数据标记）
- `CP`: 数据内容区

**HJ 212-2025 新增**:
- SM4 国密加密（通过 Flag 中的加密标志判断）
- 工况数据（`p` 前缀参数）
- 用电数据（`d` 前缀参数）

### Alternatives Considered
| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| 正则表达式 | 实现简单 | 难以处理嵌套、可维护性差 | ❌ 违反 Constitution |
| 字符串分割 | 直观 | 无法处理边界情况 | ❌ 不够健壮 |
| 状态机 | 健壮、可扩展 | 实现复杂度稍高 | ✅ 采用 |

---

## 2. SM4 国密加密

### Decision
使用 `gmssl` 库实现 SM4 解密，ECB 模式。

### Rationale
- `gmssl` 是 Python 生态中最成熟的国密库
- HJ 212-2025 标准要求 SM4/ECB 模式
- 符合国家密码管理要求

### Implementation Notes
```python
# SM4 解密示例结构
from gmssl.sm4 import CryptSM4, SM4_DECRYPT

def decrypt_sm4(ciphertext: bytes, key: bytes) -> bytes:
    crypt = CryptSM4()
    crypt.set_key(key, SM4_DECRYPT)
    return crypt.crypt_ecb(ciphertext)
```

### Key Management
- 密钥通过配置文件管理
- 支持按设备 MN 号配置不同密钥
- 默认无密钥时报文视为明文

### Alternatives Considered
| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| gmssl | 纯 Python、稳定 | 性能一般 | ✅ 采用 |
| pycryptodome | 性能好 | 无原生 SM4 支持 | ❌ |
| 自实现 | 可控 | 安全风险高 | ❌ |

---

## 3. TCP Gateway 架构

### Decision
使用 asyncio 原生 TCP Server，单进程多协程模式。

### Rationale
- asyncio 是 Python 3.11+ 的标准异步方案
- 单进程避免进程间通信复杂性
- 500 并发在单进程下可以轻松处理

### Architecture
```
TCP Client (数采仪)
        │
        ▼
┌─────────────────────┐
│  asyncio TCP Server │
│  (ConnectionHandler)│
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│   HJ212 Parser      │
│   + SM4 Decrypt     │
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│   TDengine Writer   │
│   (Batch Insert)    │
└─────────────────────┘
```

### Connection Management
- 每个连接绑定设备 MN 号
- 心跳超时 5 分钟自动断开
- 支持断线重连，状态自动恢复

### Alternatives Considered
| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| asyncio | 标准库、简单 | 单进程 | ✅ 采用 (MVP 足够) |
| Twisted | 成熟 | 学习曲线、重 | ❌ 违反简洁原则 |
| uvloop + asyncio | 性能更好 | 需要额外依赖 | ⚠️ 可选优化 |

---

## 4. 时序数据库 TDengine

### Decision
使用 TDengine 存储监测数据，通过 Python connector 进行读写。

### Rationale
- TDengine 专为 IoT 时序数据设计
- 支持超级表（STable）实现多设备数据管理
- 内置降采样和聚合函数

### Schema Design
```sql
-- 超级表定义
CREATE STABLE monitoring_data (
    ts TIMESTAMP,
    param_code VARCHAR(20),
    param_value DOUBLE,
    flag TINYINT,
    is_anomaly BOOL
) TAGS (
    mn VARCHAR(20),
    st VARCHAR(4)
);

-- 每个设备创建子表
CREATE TABLE device_{mn} USING monitoring_data TAGS ('{mn}', '{st}');
```

### Performance Optimization
- 批量写入（每 100 条或每秒）
- 使用连接池
- 查询时指定时间范围减少扫描

### Alternatives Considered
| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| TDengine | IoT 专用、高性能 | 学习成本 | ✅ 采用 |
| InfluxDB | 成熟 | 资源占用高 | ❌ |
| TimescaleDB | PostgreSQL 扩展 | 部署复杂 | ❌ |

---

## 5. AI 异常检测

### Decision
采用 XGBoost 实现电流-浓度关联分析，结合规则引擎。

### Rationale
- XGBoost 对表格数据效果好
- 可解释性强，适合监管场景
- 规则引擎处理简单阈值告警

### Detection Strategy

**层级 1: 规则引擎**
- Flag=D/M/C 标记无效数据
- 浓度超标判断
- 设备离线检测

**层级 2: ML 模型**
- 输入: 电流值、流量、历史浓度
- 输出: 预测浓度
- 异常判定: |实际 - 预测| > 阈值

### Model Training
```python
# 特征工程示例
features = [
    'current_value',      # 电流值
    'flow_rate',          # 流量
    'hour_of_day',        # 时间特征
    'historical_avg_7d',  # 7天历史均值
]
target = 'concentration'  # 污染物浓度
```

### Alternatives Considered
| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| XGBoost | 高效、可解释 | 需要标注数据 | ✅ 采用 |
| 深度学习 | 自动特征 | 黑盒、数据量要求高 | ❌ MVP 不需要 |
| 纯规则 | 简单 | 无法发现复杂模式 | ❌ 不足 |

---

## 6. 前端技术方案

### Decision
Vue 3 + Element Plus + ECharts 5，Composition API 风格。

### Rationale
- Element Plus 是 B 端最成熟的 UI 库
- ECharts 对环保曲线支持完善
- Composition API 便于逻辑复用

### Key Components

**图表封装**:
```typescript
// useChart.ts
export function useChart(options: EChartsOption) {
  const chartRef = ref<HTMLElement>()
  const chartInstance = ref<ECharts>()

  onMounted(() => {
    chartInstance.value = echarts.init(chartRef.value)
    chartInstance.value.setOption(options)
  })

  return { chartRef, chartInstance }
}
```

**响应式布局**:
- 使用 Element Plus 的 Grid 系统
- 支持 1920x1080 和 1366x768
- Dashboard 使用 CSS Grid 实现卡片布局

### Mock Data Strategy
- 开发阶段使用 Mock Service Worker (MSW)
- Mock 数据结构与真实 API 一致
- 通过环境变量切换

---

## 7. 认证方案

### Decision
采用 JWT + Session 混合模式。

### Rationale
- JWT 适合 API 认证
- Session 适合 Web 页面状态管理
- 混合模式兼顾安全性和便利性

### Implementation
```
Login Flow:
1. 用户提交用户名密码
2. 后端验证后生成 JWT Token
3. Token 存储在 HttpOnly Cookie
4. 后续请求自动携带 Cookie
```

### Token Structure
```json
{
  "sub": "user_id",
  "username": "admin",
  "role": "operator",
  "exp": 1700000000
}
```

---

## 8. 部署方案

### Decision
使用 Docker Compose 一键部署。

### Rationale
- 简化开发环境搭建
- 便于 MVP 演示
- 生产环境可平滑迁移到 K8s

### Services
```yaml
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"   # API
      - "9999:9999"   # TCP Gateway
    depends_on:
      - tdengine
      - postgres

  frontend:
    build: ./frontend
    ports:
      - "3000:80"

  tdengine:
    image: tdengine/tdengine:3.0
    ports:
      - "6030:6030"

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: ecomind
      POSTGRES_USER: ecomind
      POSTGRES_PASSWORD: ${DB_PASSWORD}
```

---

## Summary

所有技术决策已完成，无需进一步澄清。技术栈完全符合 README 和 Constitution 要求：

| 领域 | 决策 | 状态 |
|------|------|------|
| 协议解析 | 状态机 Parser | ✅ |
| 国密加密 | gmssl SM4 | ✅ |
| TCP 网关 | asyncio Server | ✅ |
| 时序存储 | TDengine | ✅ |
| AI 检测 | XGBoost + 规则 | ✅ |
| 前端框架 | Vue 3 + Element Plus | ✅ |
| 认证方案 | JWT + Session | ✅ |
| 部署方案 | Docker Compose | ✅ |
