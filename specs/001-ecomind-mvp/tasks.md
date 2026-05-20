# Tasks: EcoMind-AI 智慧环保 SaaS 平台 MVP

**Input**: Design documents from `/specs/001-ecomind-mvp/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/, research.md, quickstart.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `backend/app/`, `backend/tests/`
- **Frontend**: `frontend/src/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create backend project structure with directories: app/core, app/protocols, app/gateway, app/models, app/api, app/services, app/db in backend/
- [ ] T002 Create frontend project structure with directories: api, components, views, stores, router, mock in frontend/src/
- [ ] T003 [P] Initialize Python project with requirements.txt in backend/ (FastAPI, uvicorn, pydantic, asyncio, gmssl, scikit-learn, taospy)
- [ ] T004 [P] Initialize Vue 3 project with package.json in frontend/ (Vue 3, Vite, Element Plus, ECharts 5, Pinia, Axios)
- [ ] T005 [P] Create docker-compose.yml with TDengine, PostgreSQL, backend, frontend services at repository root
- [ ] T006 [P] Configure Python linting with pyproject.toml (black, mypy, ruff) in backend/
- [ ] T007 [P] Configure TypeScript/ESLint with .eslintrc.cjs in frontend/

**Checkpoint**: Project structure ready, dependencies installed

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Database & Configuration

- [ ] T008 Create environment configuration module in backend/app/core/config.py with Pydantic Settings
- [ ] T009 Implement TDengine connection pool in backend/app/db/tdengine.py with async support
- [ ] T010 [P] Implement PostgreSQL connection with SQLAlchemy async in backend/app/db/postgres.py
- [ ] T011 Create database initialization script in backend/app/db/init.py (TDengine STables, PostgreSQL tables)

### Shared Models & Enums

- [ ] T012 [P] Create HJ212 parameter code enums in backend/app/protocols/enums.py (w/d/p codes with names and units)
- [ ] T013 [P] Create parameter name mappings in backend/app/protocols/mappings.py
- [ ] T014 [P] Create Organization Pydantic model in backend/app/models/organization.py
- [ ] T015 [P] Create User Pydantic model with role enum in backend/app/models/user.py
- [ ] T016 [P] Create Device Pydantic model with status enum in backend/app/models/device.py
- [ ] T017 [P] Create MonitoringData Pydantic model in backend/app/models/monitoring.py
- [ ] T018 [P] Create Alarm Pydantic model with type/level/status enums in backend/app/models/alarm.py

### Authentication Framework

- [ ] T019 Implement JWT token utilities in backend/app/core/security.py (create_token, verify_token, hash_password)
- [ ] T020 Implement authentication middleware in backend/app/api/deps.py (get_current_user dependency)
- [ ] T021 Create auth router with login/logout/me endpoints in backend/app/api/auth.py

### API Structure

- [ ] T022 Create FastAPI app entry point in backend/main.py with CORS and routers
- [ ] T023 Create API router aggregation in backend/app/api/router.py
- [ ] T024 Configure error handling and logging in backend/app/core/logging.py

### Frontend Foundation

- [ ] T025 Create Axios instance with interceptors in frontend/src/api/index.ts
- [ ] T026 [P] Create auth API client in frontend/src/api/auth.ts
- [ ] T027 [P] Create Pinia auth store in frontend/src/stores/auth.ts
- [ ] T028 Create Vue Router configuration with guards in frontend/src/router/index.ts
- [ ] T029 Create Login page with Element Plus form in frontend/src/views/Login.vue
- [ ] T030 Create App.vue with layout structure in frontend/src/App.vue
- [ ] T031 Create main.ts with Pinia, Router, Element Plus setup in frontend/src/main.ts

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - 数采仪数据接入与解析 (Priority: P1) 🎯 MVP

**Goal**: 实现 HJ 212 协议解析和 TCP 网关，支持数采仪数据接入和存储

**Independent Test**: 使用模拟数采仪发送 HJ 212 报文，验证解析和存储

### Implementation for User Story 1

#### Protocol Parser

- [ ] T032 [P] [US1] Implement CRC16 checksum calculation in backend/app/protocols/crc.py
- [ ] T033 [P] [US1] Implement SM4 encryption/decryption wrapper using gmssl in backend/app/core/sm4.py
- [ ] T034 [US1] Implement HJ212Parser class with state machine in backend/app/protocols/parser.py (parse header, extract fields, CRC validation, SM4 decrypt hook)
- [ ] T035 [US1] Add parser unit tests in backend/tests/unit/test_parser.py (normal packets, encrypted packets, CRC errors, malformed data)
- [ ] T036 [US1] Add CRC unit tests in backend/tests/unit/test_crc.py

#### TCP Gateway

- [ ] T037 [US1] Implement TCP connection handler in backend/app/gateway/handler.py (packet buffering, frame detection with ## and &&)
- [ ] T038 [US1] Implement asyncio TCP server in backend/app/gateway/server.py (accept connections, manage clients by MN)
- [ ] T039 [US1] Add gateway integration tests in backend/tests/integration/test_gateway.py

#### Data Storage

- [ ] T040 [US1] Implement monitoring data writer service in backend/app/services/data_service.py (batch insert to TDengine)
- [ ] T041 [US1] Integrate parser with gateway handler for data flow in backend/app/gateway/handler.py

#### Test Tools

- [ ] T042 [US1] Create test packet sender script in backend/tests/tools/send_test_packet.py (simulate data collector)

**Checkpoint**: User Story 1 complete - TCP gateway receives HJ212 packets, parses them, and stores in TDengine

---

## Phase 4: User Story 2 - 实时监控驾驶舱 (Priority: P2)

**Goal**: 实现可视化监控驾驶舱，包含 GIS 地图、报警滚动、指标卡片

**Independent Test**: 使用 Mock 数据展示完整驾驶舱界面

### Implementation for User Story 2

#### Backend APIs

- [ ] T043 [P] [US2] Implement dashboard data API in backend/app/api/data.py (GET /api/data/dashboard, /api/data/map)
- [ ] T044 [P] [US2] Implement realtime alarm WebSocket in backend/app/api/alarms.py (GET /api/alarms/realtime)
- [ ] T045 [US2] Implement dashboard service in backend/app/services/dashboard_service.py (aggregate device stats, alarm stats, trend data)

#### Frontend Components

- [ ] T046 [P] [US2] Create ECharts hook in frontend/src/components/charts/useChart.ts
- [ ] T047 [P] [US2] Create RealTimeLineChart component in frontend/src/components/charts/RealTimeLineChart.vue
- [ ] T048 [P] [US2] Create GIS map component in frontend/src/components/map/GisMap.vue (use ECharts map or Leaflet)
- [ ] T049 [P] [US2] Create alarm scroller component in frontend/src/components/common/AlarmScroller.vue
- [ ] T050 [P] [US2] Create stats card component in frontend/src/components/common/StatsCard.vue

#### Frontend Page & Store

- [ ] T051 [US2] Create data API client in frontend/src/api/data.ts
- [ ] T052 [P] [US2] Create alarms API client in frontend/src/api/alarms.ts
- [ ] T053 [US2] Create alarm store with WebSocket in frontend/src/stores/alarm.ts
- [ ] T054 [US2] Create Dashboard page in frontend/src/views/Dashboard.vue (integrate map, alarm scroller, stats cards, trend chart)

#### Mock Data

- [ ] T055 [P] [US2] Create mock monitoring data in frontend/src/mock/monitoring.ts
- [ ] T056 [P] [US2] Create mock device data in frontend/src/mock/devices.ts
- [ ] T057 [US2] Create mock service setup in frontend/src/mock/index.ts

**Checkpoint**: User Story 2 complete - Dashboard shows real-time data, alarms scroll, map displays device locations

---

## Phase 5: User Story 3 - 多参数数据查询与对比 (Priority: P3)

**Goal**: 实现历史数据查询和多参数叠加对比显示

**Independent Test**: 使用预置历史数据验证查询和对比功能

### Implementation for User Story 3

#### Backend APIs

- [ ] T058 [US3] Implement history data query API in backend/app/api/data.py (GET /api/data/history with time range, aggregation)
- [ ] T059 [US3] Implement compare data API in backend/app/api/data.py (GET /api/data/compare with dual-axis support)
- [ ] T060 [US3] Implement data export API in backend/app/api/data.py (GET /api/data/export as CSV)
- [ ] T061 [US3] Extend data service with TDengine time-range queries in backend/app/services/data_service.py

#### Frontend Components

- [ ] T062 [US3] Create DualAxisChart component in frontend/src/components/charts/DualAxisChart.vue
- [ ] T063 [P] [US3] Create DataTable component in frontend/src/components/common/DataTable.vue
- [ ] T064 [P] [US3] Create date range picker wrapper in frontend/src/components/common/DateRangePicker.vue

#### Frontend Page

- [ ] T065 [US3] Create DataQuery page in frontend/src/views/DataQuery.vue (device selector, param selector, date range, chart, table, export button)
- [ ] T066 [US3] Add data query routes to router in frontend/src/router/index.ts

**Checkpoint**: User Story 3 complete - Users can query history data and compare multiple parameters with dual Y-axis

---

## Phase 6: User Story 4 - AI 异常检测与标记 (Priority: P4)

**Goal**: 实现 AI 异常检测，标记可疑数据

**Independent Test**: 使用已知异常数据集验证检测准确性

### Implementation for User Story 4

#### AI Service

- [ ] T067 [US4] Implement rule engine for Flag validation in backend/app/services/ai_service.py (Flag=D/M/C detection)
- [ ] T068 [US4] Implement XGBoost anomaly detection model in backend/app/services/ai_service.py (current-concentration correlation)
- [ ] T069 [US4] Create model training script in backend/scripts/train_model.py
- [ ] T070 [US4] Integrate AI service with data ingestion pipeline in backend/app/gateway/handler.py

#### Backend APIs

- [ ] T071 [US4] Add is_anomaly and anomaly_reason fields to data query responses in backend/app/api/data.py
- [ ] T072 [US4] Create anomaly report API in backend/app/api/data.py (GET /api/data/anomalies)

#### Frontend Integration

- [ ] T073 [US4] Update RealTimeLineChart to highlight anomaly points in frontend/src/components/charts/RealTimeLineChart.vue
- [ ] T074 [US4] Update DualAxisChart to show anomaly markers in frontend/src/components/charts/DualAxisChart.vue
- [ ] T075 [US4] Create anomaly detail popover component in frontend/src/components/common/AnomalyPopover.vue
- [ ] T076 [US4] Update DataQuery page to show anomaly reasons on click in frontend/src/views/DataQuery.vue

**Checkpoint**: User Story 4 complete - AI detects and marks anomalies, UI highlights suspicious data points

---

## Phase 7: User Story 5 - 设备管理与状态监控 (Priority: P5)

**Goal**: 实现设备管理 CRUD 和在线状态监控

**Independent Test**: 模拟设备上下线，验证状态更新和告警

### Implementation for User Story 5

#### Backend APIs

- [ ] T077 [P] [US5] Implement device CRUD API in backend/app/api/devices.py (GET/POST/PUT/DELETE /api/devices)
- [ ] T078 [P] [US5] Implement device stats API in backend/app/api/devices.py (GET /api/devices/stats)
- [ ] T079 [US5] Implement device service in backend/app/services/device_service.py (CRUD operations, status management)
- [ ] T080 [US5] Implement heartbeat timeout checker in backend/app/services/device_service.py (mark offline after 5min)
- [ ] T081 [US5] Integrate device status updates with gateway connection events in backend/app/gateway/handler.py

#### Alarm Integration

- [ ] T082 [US5] Implement alarm CRUD API in backend/app/api/alarms.py (GET/acknowledge/resolve)
- [ ] T083 [US5] Implement alarm service in backend/app/services/alarm_service.py (create alarms on device offline, exceed threshold)

#### Frontend

- [ ] T084 [US5] Create devices API client in frontend/src/api/devices.ts
- [ ] T085 [US5] Create device store in frontend/src/stores/device.ts
- [ ] T086 [US5] Create DeviceManage page in frontend/src/views/DeviceManage.vue (table, add/edit form, status badges)
- [ ] T087 [US5] Create AlarmList page in frontend/src/views/AlarmList.vue (filter, acknowledge, resolve actions)
- [ ] T088 [US5] Add device and alarm routes to router in frontend/src/router/index.ts

**Checkpoint**: User Story 5 complete - Admin can manage devices, view status, handle alarms

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T089 [P] Create seed data script for demo in backend/app/db/seed.py (sample devices, users, organizations)
- [ ] T090 [P] Add API documentation with OpenAPI schemas in backend/main.py
- [ ] T091 Run mypy type checking on entire backend codebase
- [ ] T092 [P] Run ESLint on frontend codebase
- [ ] T093 Optimize TDengine queries for large time ranges in backend/app/services/data_service.py
- [ ] T094 Add response caching for dashboard API in backend/app/api/data.py
- [ ] T095 Create production Dockerfile for backend in backend/Dockerfile
- [ ] T096 [P] Create production Dockerfile for frontend in frontend/Dockerfile
- [ ] T097 Update docker-compose.yml for production deployment
- [ ] T098 Validate quickstart.md steps work end-to-end
- [ ] T099 Performance test: verify 500 concurrent connections with test script

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)
    │
    ▼
Phase 2 (Foundational) ─────── BLOCKS ALL USER STORIES
    │
    ├──────────────────────────────────────────────────┐
    ▼                                                  ▼
Phase 3 (US1: 数据接入) ──► Phase 4 (US2: 驾驶舱) ──► Phase 5 (US3: 数据查询)
                                                       │
                                                       ▼
                           Phase 6 (US4: AI异常) ◄─────┘
                                  │
                                  ▼
                           Phase 7 (US5: 设备管理)
                                  │
                                  ▼
                           Phase 8 (Polish)
```

### User Story Dependencies

| Story | Depends On | Can Parallel With |
|-------|------------|-------------------|
| US1 (数据接入) | Foundational | None (critical path) |
| US2 (驾驶舱) | US1 (needs data) | US3 (frontend only) |
| US3 (数据查询) | US1 (needs data) | US2 (backend only) |
| US4 (AI异常) | US1, US3 | None |
| US5 (设备管理) | US1 | US2, US3, US4 |

### Within Each User Story

1. Backend models before services
2. Services before API endpoints
3. Frontend API clients before stores
4. Stores before views
5. [P] marked tasks can run in parallel

---

## Parallel Execution Examples

### Phase 2 Parallel Tasks

```bash
# Launch in parallel:
Task T012: Create HJ212 parameter code enums
Task T013: Create parameter name mappings
Task T014: Create Organization model
Task T015: Create User model
Task T016: Create Device model
Task T017: Create MonitoringData model
Task T018: Create Alarm model
```

### User Story 1 Parallel Tasks

```bash
# Launch in parallel:
Task T032: Implement CRC16 checksum
Task T033: Implement SM4 wrapper
```

### User Story 2 Parallel Tasks

```bash
# Backend parallel:
Task T043: Dashboard data API
Task T044: Realtime alarm WebSocket

# Frontend parallel:
Task T046: ECharts hook
Task T047: RealTimeLineChart
Task T048: GIS map
Task T049: AlarmScroller
Task T050: StatsCard
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Send test packets to gateway, verify in TDengine
5. Deploy backend-only for data collection

### Incremental Delivery

1. **Sprint 1**: Setup + Foundational + US1 → Data collection works
2. **Sprint 2**: US2 → Dashboard visualizes data
3. **Sprint 3**: US3 → Query and analysis ready
4. **Sprint 4**: US4 + US5 → AI + Management complete
5. **Sprint 5**: Polish → Production ready

### Parallel Team Strategy

With 2 developers:

1. Both complete Setup + Foundational
2. Developer A: US1 (backend-focused)
3. Developer B: US2 frontend (with mock data)
4. After US1: Developer A continues US3-US4
5. Developer B: US5 frontend

---

## Summary

| Phase | Story | Tasks | Parallel |
|-------|-------|-------|----------|
| 1 | Setup | 7 | 5 |
| 2 | Foundational | 24 | 13 |
| 3 | US1: 数据接入 | 11 | 3 |
| 4 | US2: 驾驶舱 | 15 | 9 |
| 5 | US3: 数据查询 | 9 | 2 |
| 6 | US4: AI异常 | 10 | 0 |
| 7 | US5: 设备管理 | 12 | 2 |
| 8 | Polish | 11 | 4 |
| **Total** | | **99** | **38** |

**Suggested MVP Scope**: Complete through Phase 3 (US1) for minimum viable data collection capability.
