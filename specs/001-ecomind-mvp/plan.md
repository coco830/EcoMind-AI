# Implementation Plan: EcoMind-AI 智慧环保 SaaS 平台 MVP

**Branch**: `001-ecomind-mvp` | **Date**: 2025-11-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-ecomind-mvp/spec.md`

## Summary

构建一个"轻硬件、重软件、AI驱动"的环保管家平台，实现 HJ 212 协议数据接入、实时监控驾驶舱、多参数数据查询、AI 异常检测和设备管理功能。系统采用前后端分离架构，后端基于 FastAPI + TDengine，前端基于 Vue 3 + Element Plus。

## Technical Context

**Language/Version**: Python 3.11+ (后端), TypeScript/JavaScript (前端)
**Primary Dependencies**:
- 后端: FastAPI, asyncio + uvloop, Pydantic, gmssl, Scikit-learn/XGBoost, LangChain
- 前端: Vue 3 (Composition API), Vite, Element Plus, ECharts 5, Pinia, Axios

**Storage**:
- 时序数据库: TDengine (存储监测数据，支持高速写入和时间范围查询)
- 业务数据库: PostgreSQL (生产环境) / SQLite (开发环境) - 用户、设备、报警等业务数据

**Testing**: pytest (后端), Vitest (前端)
**Target Platform**: Linux Server (Docker 部署), 现代浏览器 (Chrome/Edge/Firefox)
**Project Type**: Web Application (前后端分离)

**Performance Goals**:
- TCP Gateway: 支持 500+ 并发连接，报文处理延迟 < 100ms
- API: p95 响应时间 < 200ms
- 前端: 首屏加载 < 3s，图表渲染 < 1s

**Constraints**:
- 报警延迟 < 3s
- 数据查询响应 < 5s (一个月数据量)
- 系统可用性 99.5%

**Scale/Scope**:
- MVP 阶段: 500 台数采仪并发
- 数据保留: 3 年
- 用户规模: 100 用户

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. 协议严格化 (Protocol Strictness)

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 专用 Parser 类 | ✅ 计划符合 | 将在 `backend/app/protocols/` 创建 `HJ212Parser` 类 |
| CRC16 校验 | ✅ 计划符合 | 解析器将实现 CRC16 校验，失败丢弃并记录日志 |
| SM4 解密钩子 | ✅ 计划符合 | 预留 `if encryption_enabled: decrypt()` 结构 |
| 参数编码集中管理 | ✅ 计划符合 | 所有 `w/d/p` 参数编码定义在 `enums.py` 或 `mappings.py` |
| 禁止硬编码 | ✅ 计划符合 | 参数编码和配置项统一管理 |
| 双标准兼容 | ✅ 计划符合 | 同时支持 HJ 212-2017 和 HJ 212-2025 |

### II. 后端代码规范 (Backend Style)

| 检查项 | 状态 | 说明 |
|--------|------|------|
| Type Hinting | ✅ 计划符合 | 所有函数包含类型注解，通过 mypy 检查 |
| Pydantic | ✅ 计划符合 | API 请求/响应和数据模型均使用 Pydantic |
| Async First | ✅ 计划符合 | 所有 I/O 操作使用 async/await |
| 禁止重型框架 | ✅ 计划符合 | 仅使用 FastAPI，不引入 Django |
| 精简依赖 | ✅ 计划符合 | requirements.txt 仅包含必要依赖 |

### III. 前端生成约束 (Frontend Constraints)

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 组件一致性 | ✅ 计划符合 | 仅使用 Element Plus |
| 响应式布局 | ✅ 计划符合 | 适配 1920x1080 和 1366x768 |
| Mock Data | ✅ 计划符合 | 前端包含 mock 数据支持独立开发 |
| ECharts 封装 | ✅ 计划符合 | 图表配置封装为 Composables/Components |

### IV. 工程化结构 (Project Structure)

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 目录结构 | ✅ 计划符合 | 严格遵循 Constitution 定义的结构 |
| protocols 目录 | ✅ 计划符合 | HJ212 解析器放在 `backend/app/protocols/` |
| services 目录 | ✅ 计划符合 | 业务逻辑放在 `backend/app/services/` |

### V. 测试与质量 (Testing & Quality)

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 协议解析器测试 | ✅ 计划符合 | 为 Parser 编写单元测试 |
| API 集成测试 | ✅ 计划符合 | 为端点编写集成测试 |
| pytest 框架 | ✅ 计划符合 | 使用 pytest |
| CI/CD 测试 | ✅ 计划符合 | 测试失败阻止合并 |

### VI. 简洁性原则 (Simplicity)

| 检查项 | 状态 | 说明 |
|--------|------|------|
| YAGNI | ✅ 计划符合 | 仅实现 MVP 所需功能 |
| 最简实现 | ✅ 计划符合 | 从基础功能开始迭代 |
| 禁止过度设计 | ✅ 计划符合 | 避免不必要的抽象层 |

**宪法检查结果**: ✅ 全部通过，可以进入 Phase 0

## Project Structure

### Documentation (this feature)

```text
specs/001-ecomind-mvp/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (OpenAPI specs)
│   ├── gateway-api.yaml
│   ├── data-api.yaml
│   ├── device-api.yaml
│   └── auth-api.yaml
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── __init__.py
│   ├── core/                    # 配置、安全、SM4算法
│   │   ├── __init__.py
│   │   ├── config.py            # 环境配置
│   │   ├── security.py          # 认证/授权
│   │   └── sm4.py               # SM4 加解密封装
│   ├── protocols/               # HJ212 解析器核心
│   │   ├── __init__.py
│   │   ├── parser.py            # HJ212Parser 类
│   │   ├── enums.py             # 参数编码枚举
│   │   ├── mappings.py          # 参数名称映射
│   │   └── crc.py               # CRC16 校验
│   ├── gateway/                 # TCP Server
│   │   ├── __init__.py
│   │   ├── server.py            # asyncio TCP Server
│   │   └── handler.py           # 连接处理器
│   ├── models/                  # Pydantic Models
│   │   ├── __init__.py
│   │   ├── device.py            # 设备模型
│   │   ├── monitoring.py        # 监测数据模型
│   │   ├── alarm.py             # 报警模型
│   │   └── user.py              # 用户模型
│   ├── api/                     # FastAPI Routers
│   │   ├── __init__.py
│   │   ├── router.py            # 路由聚合
│   │   ├── auth.py              # 认证端点
│   │   ├── devices.py           # 设备管理端点
│   │   ├── data.py              # 数据查询端点
│   │   └── alarms.py            # 报警端点
│   ├── services/                # 业务逻辑
│   │   ├── __init__.py
│   │   ├── device_service.py    # 设备管理服务
│   │   ├── data_service.py      # 数据查询服务
│   │   ├── alarm_service.py     # 报警服务
│   │   └── ai_service.py        # AI 异常检测服务
│   └── db/                      # 数据库操作
│       ├── __init__.py
│       ├── tdengine.py          # TDengine 连接
│       └── postgres.py          # PostgreSQL 连接
├── tests/
│   ├── __init__.py
│   ├── unit/
│   │   ├── test_parser.py       # 解析器单元测试
│   │   └── test_crc.py          # CRC 单元测试
│   ├── integration/
│   │   ├── test_gateway.py      # 网关集成测试
│   │   └── test_api.py          # API 集成测试
│   └── conftest.py              # pytest fixtures
├── main.py                      # 应用入口
└── requirements.txt             # Python 依赖

frontend/
├── src/
│   ├── api/                     # Axios 封装
│   │   ├── index.ts             # Axios 实例
│   │   ├── auth.ts              # 认证 API
│   │   ├── devices.ts           # 设备 API
│   │   ├── data.ts              # 数据 API
│   │   └── alarms.ts            # 报警 API
│   ├── components/              # 公共组件
│   │   ├── charts/              # 图表组件
│   │   │   ├── RealTimeLineChart.vue
│   │   │   ├── DualAxisChart.vue
│   │   │   └── useChart.ts      # ECharts Hook
│   │   ├── map/                 # 地图组件
│   │   │   └── GisMap.vue
│   │   └── common/              # 通用组件
│   │       ├── DataTable.vue
│   │       └── AlarmScroller.vue
│   ├── views/                   # 页面
│   │   ├── Login.vue            # 登录页
│   │   ├── Dashboard.vue        # 驾驶舱
│   │   ├── DataQuery.vue        # 数据查询
│   │   ├── DeviceManage.vue     # 设备管理
│   │   └── AlarmList.vue        # 报警列表
│   ├── stores/                  # Pinia 状态
│   │   ├── index.ts
│   │   ├── auth.ts              # 认证状态
│   │   ├── device.ts            # 设备状态
│   │   └── alarm.ts             # 报警状态
│   ├── router/                  # 路由配置
│   │   └── index.ts
│   ├── mock/                    # Mock 数据
│   │   ├── index.ts
│   │   ├── devices.ts
│   │   └── monitoring.ts
│   ├── App.vue
│   └── main.ts
├── package.json
├── vite.config.ts
└── tsconfig.json

docker-compose.yml               # 一键启动
```

**Structure Decision**: 采用 Web Application 结构，前后端分离。后端严格遵循 Constitution 定义的目录结构，前端采用 Vue 3 标准项目结构。

## Complexity Tracking

> 无宪法违规，此表为空

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | N/A | N/A |
