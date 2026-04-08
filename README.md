# 📘 EcoMind-AI（当前实现版）

> **定位**：智慧环保 SaaS 平台（数据采集、合规监控、AI 分析、智能体协同）  
> **适用对象**：开发团队、AI 编程助手（Cursor / Copilot / Codex 等）  
> **最后更新**：2026-04-07（已同步视频联动 Phase 1、Phase 2、P1 接入台账/安装验收、Demo 联调能力与企业接入清单）

---

## 1) 项目概述

EcoMind-AI 的核心目标是构建一个 **轻硬件、重软件、AI 驱动** 的环保运维平台：

- **数据层**：兼容 HJ 212 协议采集链路，覆盖设备状态与监测数据
- **分析层**：支持异常检测、趋势预测、日报诊断
- **应用层**：企业管理端 + 监管聚合端 + 视频联动中心
- **智能体层（新增）**：通过 `/openapi/*` 将核心能力开放给 OpenClaw 等 Agent 平台

---

## 2) 今日状态（2026-04-07）

### ✅ Phase 1（API 适配层）已落地

已完成：

1. 新增 `backend-cloudrun/app/api/openapi/` 路由模块
2. 实现 6 个 Agent 工具接口（P0 + 报警确认）
3. 实现 API Key 鉴权（`X-API-Key`）与工具权限控制
4. 新增 API Key 管理接口（`/api/v1/api-keys`）
5. 支持双模式 Key：`single_org`（企业隔离）/ `all_orgs`（全企业查询）
6. 输出并维护智能体导入文档：
   - `docs/openapi_agent_schema.json`
   - `docs/openclaw_agent_prompt.md`

### ✅ AI 接口增强（兜底机制）已落地

- **预测接口兜底**：当请求污染物数据不足时，自动回退到该设备最近有数据的污染物
- **报告接口兜底**：当目标日期无报告时，自动回退到最近可用的已完成日报
- 响应内新增可解释字段，便于 Agent 透明告知用户（见第 6 节）

### ✅ 视频联动第一阶段已落地

已完成：

1. 新增后端 `video` 业务域：视频通道、视频事件、汇总统计
2. 提供 `/api/v1/video/*` JWT 接口，支持视频通道增删改查、事件登记、事件确认/解决
3. 新增前端“视频联动”板块，集中管理通道配置与事件台账
4. 在“设备管理”“告警管理”中新增深链入口，可按设备或告警上下文跳转视频联动中心
5. 为后续接入 `GB/T28181 / RTSP / ONVIF / 外部 VMS` 预留了协议、接入方式和证据链接字段

当前边界：

- 本阶段管理的是**视频元数据、联动事件和证据地址**，不直接承载原始长视频存储
- 原始视频流建议继续由企业侧 NVR / 视频平台承载，EcoMind-AI 负责联动、证据和 AI 上下文

### ✅ 视频联动第二阶段（告警自动联动）已落地

已完成：

1. 阈值超标、AI异常、设备离线、Flag 异常告警创建后，自动生成关联的视频联动事件
2. 人工创建告警后，同样自动生成视频联动事件
3. 告警确认后，关联视频事件自动同步为“已确认”
4. 告警解决后，关联视频事件自动同步为“已解决”
5. 设备恢复在线时，离线告警被批量解决，对应视频事件也同步解决

联动策略：

- 若设备存在启用 `ai_enabled=true` 的视频通道，优先对这些通道生成联动事件
- 若没有启用 AI 的通道，则回落到该设备下全部视频通道
- 同一个告警在同一个视频通道上只生成一条关联事件，避免联动风暴

### ✅ 视频联动 P1（视频接入台账 + 安装验收管理）已落地

已完成：

1. 在 `VideoChannel` 上新增建设生命周期字段：`待勘点 / 待安装 / 待联网 / 联调中 / 已验收 / 已投运`
2. 新增接入准备与验收字段：网络承载、固定 IP、安装位置、勘点负责人、实施安装人、验收人、验收时间、验收说明
3. `GET /api/v1/video/channels` 新增 `lifecycle_status` 过滤能力，可直接按项目交付阶段查看
4. 前端 `VideoCenter` 升级为单页台账中心，可同时查看视频通道、安装验收信息和联动事件
5. 汇总卡片增加待勘点、待安装、待联网、联调中、已验收/投运等项目交付指标

适用场景：

- 当前企业侧 **尚未提供 VMS / GB28181 / RTSP** 时，先将视频点位建设工作沉淀为平台内台账
- 平台先承载“项目交付管理 + 证据联动管理”，后续再平滑接入真实视频流
- `preview_url / playback_url` 可暂时为空，待企业视频平台具备后再补齐

### ✅ 视频联动 Demo 联调能力已落地

已完成：

1. 新增 `POST /api/v1/video/demo/inject`，可为指定企业或设备一键生成演示视频台账
2. 演示数据包含建设阶段、网络信息、验收字段、手工视频事件和告警联动事件
3. 若当前企业下还没有设备，可自动补建演示设备，便于无真实流阶段先验证页面和流程
4. 前端 `VideoCenter` 新增“导入演示数据”按钮，方便现场演示和联调准备

适用场景：

- 还没有企业真实视频流，但需要先验证 `页面 / 接口 / 权限 / 告警联动`
- 需要给环保管家、实施方、业主方演示未来接入后的管理形态
- 需要先把视频台账和验收流程跑顺，再等待企业侧接口准备完成

---

## 3) 技术栈（当前实际）

### 后端

- FastAPI（异步 API）
- SQLAlchemy Async（MySQL / SQLite）
- slowapi（限流）
- structlog（日志）
- AI 预测：Prophet / NeuralProphet / 简单均值自动降级
- AI 报告：日报缓存 + LLM 生成链路
- 视频联动：Video Channel / Event 元数据建模 + 接入台账/安装验收管理 + 外部视频平台链接接入

### 前端

- Vue 3 + Vite
- Element Plus
- ECharts
- Pinia

---

## 4) 目录结构（关键路径）

```text
EcoMind-AI/
├── backend-cloudrun/
│   ├── app/
│   │   ├── api/
│   │   │   ├── v1/                    # 业务 API（JWT）
│   │   │   │   └── video.py           # 视频联动接口
│   │   │   └── openapi/               # Agent API（API Key）
│   │   │       ├── router.py
│   │   │       ├── auth.py
│   │   │       ├── device_tools.py
│   │   │       ├── data_tools.py
│   │   │       ├── alarm_tools.py
│   │   │       ├── ai_tools.py
│   │   │       └── schemas.py
│   │   ├── models/
│   │   │   └── api_client.py          # API Key 客户端模型
│   │   │   └── video.py               # 视频通道 / 事件模型
│   │   ├── services/
│   │   │   └── video_service.py       # 视频联动服务层
│   │   └── main.py                    # 挂载 /api/v1 与 /openapi
├── docs/
│   ├── OPENCLAW_INTEGRATION_PROPOSAL.md
│   ├── VIDEO_ENTERPRISE_ACCESS_CHECKLIST.md
│   ├── openapi_agent_schema.json
│   └── openclaw_agent_prompt.md
└── frontend/
    └── src/
        ├── api/
        │   └── video.ts               # 视频联动前端 API
        └── views/
            └── VideoCenter.vue        # 视频联动中心
```

---

## 5) OpenAPI（Agent）接口总览

基础前缀：`/openapi`  
认证方式：Header `X-API-Key: ecomind_xxx`

访问模式：

- `single_org`：Key 绑定企业，接口默认查询该企业
- `all_orgs`：Key 可查全部企业，但每次调用必须传 `enterprise_name` 或 `org_id`

### 5.1 可用工具（当前 6 个）

1. `GET /openapi/device/status` → `get_device_status`
2. `GET /openapi/data/latest` → `get_latest_data`
3. `GET /openapi/alarm/active` → `get_active_alarms`
4. `POST /openapi/alarm/acknowledge` → `acknowledge_alarm`
5. `GET /openapi/ai/predict` → `get_ai_prediction`
6. `GET /openapi/ai/report` → `get_ai_report`

### 5.2 API Key 管理（平台后台）

前缀：`/api/v1/api-keys`（需 superadmin JWT）

- `POST /api/v1/api-keys`：创建 API Key
- `GET /api/v1/api-keys`：查询 API Key 列表
- `PATCH /api/v1/api-keys/{client_id}/toggle`：启用/禁用
- `DELETE /api/v1/api-keys/{client_id}`：吊销

创建 `all_orgs` Key 时建议：

- `access_scope=all_orgs`
- `permissions` 按最小化原则配置（仅开放确需工具）
- 对调用日志做审计（查询企业、接口、时间、调用方）

---

## 5.3 视频联动板块（当前范围）

前端入口：

- 左侧菜单新增：`视频联动`
- `设备管理` 页新增“查看”入口，可按设备上下文跳转
- `告警管理` 页新增“视频联动”入口，可按告警上下文跳转

后端接口前缀：`/api/v1/video`

已实现接口：

- `GET /api/v1/video/summary`：视频联动汇总卡片
- `GET /api/v1/video/channels`：查询视频通道（支持 `org_id / device_id / point_type / lifecycle_status / status / ai_enabled`）
- `POST /api/v1/video/channels`：创建视频通道
- `POST /api/v1/video/demo/inject`：导入演示视频台账、演示事件和联动告警
- `PUT /api/v1/video/channels/{channel_id}`：更新视频通道
- `DELETE /api/v1/video/channels/{channel_id}`：删除视频通道
- `GET /api/v1/video/events`：查询视频事件
- `POST /api/v1/video/events`：登记视频事件
- `POST /api/v1/video/events/{event_id}/acknowledge`：确认视频事件
- `POST /api/v1/video/events/{event_id}/resolve`：解决视频事件

数据设计原则：

- 视频通道绑定**一个监测设备**，同时保存 `device_id(UUID)` 与 `device_mn`
- 视频通道除协议与链接字段外，还承担**接入准备、施工、联网、验收**台账
- 视频事件既可独立登记，也可绑定 `related_alarm_id` 形成“告警 + 视频证据”闭环
- 通道层保存协议、接入方式、生命周期、网络承载、安装位置、验收信息、预览/回放链接、AI 启用状态
- 事件层保存截图地址、片段地址、事件标题、处置状态和附加元数据

推荐使用方式：

1. 在 `设备管理` 中为每个站房/排口建立视频通道台账，并先录入建设阶段
2. 在 `视频联动` 中维护网络、机位、勘点、安装和验收信息，形成交付闭环
3. 若暂无真实视频流，可先点击“导入演示数据”验证页面和接口流程
4. 告警发生后，从 `告警管理` 跳转到 `视频联动`，登记或查看关联证据
5. 后续接入外部视频平台回调时，将识别结果落入 `video_events`
6. 再将 `video_events + alarms + monitoring_data` 一起送入 AI 诊断链路

自动联动行为：

- 平台告警服务会在告警创建成功后自动尝试生成 `AI_LINKAGE` 类型视频事件
- 视频事件会记录 `related_alarm_id`，用于从告警页深链定位
- 当告警状态变更时，相关视频事件状态会同步推进

---

## 6) AI 接口“自动回退”字段（重要）

### 6.1 `get_ai_prediction` 回退字段

当请求污染物数据不足时，系统会自动回退：

- `used_fallback_pollutant`：是否回退
- `requested_pollutant` / `requested_pollutant_code`：原请求污染物
- `pollutant` / `pollutant_code`：实际用于预测的污染物
- `attempted_pollutant_codes`：尝试顺序（可解释性）

### 6.2 `get_ai_report` 回退字段

当目标日期无可用报告时，系统会自动回退到最近可用报告：

- `used_fallback_report`：是否回退
- `requested_report_date`：请求日期
- `actual_report_date`：实际命中日期
- `fallback_reason`：回退原因说明
- `report_date`：兼容字段（等同实际报告日期）

> Agent 侧回答规范：如果 `used_fallback_* = true`，必须显式告知用户“已自动回退”。

---

## 7) 联调建议（OpenClaw）

1. 创建 API Key（`/api/v1/api-keys`）
2. 在 OpenClaw 导入 `docs/openapi_agent_schema.json`
3. 粘贴 `docs/openclaw_agent_prompt.md` 到系统提示词
4. 逐个测试 6 个工具（推荐顺序）：
   - `get_device_status`
   - `get_latest_data`
   - `get_active_alarms`
   - `get_ai_prediction`
   - `get_ai_report`
   - `acknowledge_alarm`
5. 验证回退字段解释是否符合预期

---

## 8) 关键文档索引

- 集成方案总文档：`docs/OPENCLAW_INTEGRATION_PROPOSAL.md`
- OpenAPI 导入文件：`docs/openapi_agent_schema.json`
- 智能体提示词模板：`docs/openclaw_agent_prompt.md`
- 企业侧视频接入清单：`docs/VIDEO_ENTERPRISE_ACCESS_CHECKLIST.md`

---

## 9) 给后续 AI 的工作约束（精简版）

1. **不破坏双 API 体系**：`/api/v1`（前端/JWT）与 `/openapi`（Agent/API Key）分层保持稳定
2. **接口返回优先可解释性**：对 Agent 返回需包含摘要与业务语义，避免裸技术错误
3. **多租户安全优先**：严格按 `org_id` 隔离数据
4. **回退要透明**：触发回退必须有字段标识和可读说明
5. **优先复用现有 Service 层**：避免在 OpenAPI 层复制业务逻辑

---

## 10) 下一步建议

- Phase 2：完成 OpenClaw 端到端场景回归测试（巡检/预测/报警/报告）
- Phase 3：逐步扩展 P1/P2 工具与主动推送能力（Webhook、企微、钉钉）
