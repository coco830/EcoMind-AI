# EcoMind-AI

> 面向企业环保运维的在线监测与 AI 风险预判平台。  
> 当前仓库同时承载企业侧业务后台、AI 运维报告、视频联动底座，以及对外给小程序/智能体使用的 OpenAPI 能力。

**最后更新**：2026-04-13

## 1. 项目定位

EcoMind-AI 服务的不是“监管替代平台”，而是企业自己的环保风险前置平台。

核心目标：

- 把数采仪在线数据、现场视频证据、巡检记录、自检报告统一到一个应用里
- 在超标、异常、离线、数据质量问题真正演变成处罚或通报前，提前提示企业风险
- 给企业输出可执行结论，而不是只输出技术术语

当前平台对企业侧的价值表达应统一为：

- 疑似风险级别
- 证据片段
- 关联数采
- 建议动作

## 2. 当前已落地能力

### 2.1 企业业务主链路

- 企业建档、组织隔离、多租户权限
- 监测设备管理、HJ212 数据接入、实时/历史数据查询
- 告警管理、AI 预测、AI 运维报告
- 自检报告上传、OCR 识别、运维简报与执行包导出

### 2.2 视频联动

- 视频通道台账
- 视频事件登记与告警联动
- 建设生命周期管理：待勘点、待安装、待联网、联调中、已验收、已投运
- 截图/片段/回放链接作为证据地址统一沉淀
- 轻量视频风险判断，并进入 AI 运维报告

视频联动当前定位很明确：

- 不做另一套监管型 24 小时视频平台
- 先把“视频证据闭环”做好
- 在此基础上做轻量风险判断与数采同窗复核

### 2.3 外部系统 / 小程序 / Agent 接入

- `/openapi/*` 对外开放平台只读/桥接能力
- `X-API-Key` 鉴权
- 支持 `single_org` / `all_orgs` 两种 Key 访问范围
- 已支持运维小程序所需的监测摘要拉取、执行包回传、回传状态查询

## 3. 2026-04-13 技术实现摘要

今天已落地并应作为后续开发基线理解的内容：

### 3.1 AI 运维报告链路修复与增强

- 已修复 Pandas 频率兼容问题，`H/1H` 会统一归一化处理，避免再次出现 `Invalid frequency: H`
- 已清理 FastAPI `Query(..., regex=...)` 的弃用写法，改为类型约束
- AI 报告已适配讯飞 Spark HTTP OpenAPI 方式，新增 `spark_api_password` 支持
- AI 报告同步、流式、定时生成链路已统一接入 `video_risk_assessment`

### 3.2 视频证据闭环进入 AI 报告

- 基于 `video_channels + video_events + snapshot_uri/clip_uri + related_alarm_id`
- 结合数采同窗数据做轻量风险评分
- 在 AI 报告返回体顶层输出 `video_risk_assessment`
- 前端 AI 分析卡片已增加“视频联动风险摘要”展示区

### 3.3 运维小程序第一阶段桥接接口

已在 `backend-cloudrun` 中落地：

- `POST /openapi/monitoring/summary`
- `POST /openapi/package/push`
- `GET /openapi/package/push/status`

用途分别是：

- 给运维简报拉取 `mnCode + 时间范围` 的监测摘要
- 接收小程序后端回传的执行包 ZIP
- 查询执行包回传状态、文档链接和受理时间

### 3.4 联调辅助

- 新增真实联调用脚本：`backend-cloudrun/scripts/pick_test_mn_code.py`
- 可直接从现网 `devices + monitoring_data` 中挑一条最近有数据的 `mnCode`
- 已补回归测试与 GitHub Actions 工作流

## 4. 仓库结构

```text
EcoMind-AI/
├── backend-cloudrun/               # 云托管后端
│   ├── app/
│   │   ├── api/
│   │   │   ├── v1/                 # JWT 业务 API
│   │   │   └── openapi/            # 小程序 / Agent / 外部桥接 API
│   │   ├── models/                 # ORM 模型
│   │   ├── services/               # 业务服务层
│   │   └── main.py
│   ├── alembic/
│   ├── scripts/
│   ├── tests/
│   ├── Dockerfile
│   ├── Dockerfile.cloudbase
│   ├── requirements.txt
│   └── requirements-cloudbase.txt
├── frontend/                       # Vue 3 前端
├── docs/                           # 当前仍保留的核心文档
├── deploy/                         # 传统部署相关资料
└── specs/                          # 早期规格设计资料
```

## 5. 核心业务边界

### 5.1 企业侧 AI 运维报告

报告不是单纯生成一段文本，而是由以下数据共同组成：

- 实时 / 历史数采数据
- 污染物统计与趋势
- 行业标准与阈值
- 视频联动风险摘要
- LLM 生成的企业可读运维建议

当前要求：

- 视频内容只用于佐证、预警、复核排序
- 不得把视频摘要写成法定监测结论
- 若有回退、缺失、替代数据，必须在返回字段或摘要中透明表达

### 5.2 视频联动的产品边界

当前平台做的是：

- 视频点位建设台账
- 风险事件登记
- 告警联动与证据留存
- 轻量风险判断

当前平台不做的是：

- 7x24 小时全量视觉监管
- 替代监管部门的视频联网平台
- 脱离数采与业务上下文的纯视觉炫技分析

## 6. OpenAPI 现状

基础前缀：`/openapi`  
鉴权方式：`X-API-Key: ecomind_xxx`

### 6.1 已开放能力

- `GET /openapi/device/status`
- `GET /openapi/data/latest`
- `GET /openapi/alarm/active`
- `POST /openapi/alarm/acknowledge`
- `GET /openapi/ai/predict`
- `GET /openapi/ai/report`
- `POST /openapi/monitoring/summary`
- `POST /openapi/package/push`
- `GET /openapi/package/push/status`

### 6.2 API Key 范围

- `single_org`：固定绑定一个企业
- `all_orgs`：可跨企业查询，但调用时必须显式指定企业条件

### 6.3 典型桥接场景

运维小程序后端：

- 拉取月度/周期监测摘要
- 导出执行包后回传平台
- 按 `pushJobId` 或 `sourceJobId` 回查回传状态

Agent / 外部系统：

- 查询设备状态
- 查询最新监测数据
- 查询当前告警
- 查询 AI 预测与 AI 报告

## 7. 关键环境变量

### 7.1 后端基础

- `APP_ENV`
- `DATA_PROVIDER`
- `MYSQL_HOST`
- `MYSQL_PORT`
- `MYSQL_DATABASE`
- `MYSQL_USER`
- `MYSQL_PASSWORD`

### 7.2 Spark 大模型

- `SPARK_APP_ID`
- `SPARK_API_KEY`
- `SPARK_API_SECRET`
- `SPARK_API_PASSWORD`
- `SPARK_API_URL`
- `SPARK_DOMAIN`

说明：

- 当前已支持讯飞 Spark HTTP OpenAPI
- 若使用 `https://spark-api-open.xf-yun.com/v1/chat/completions`，需正确配置 `SPARK_API_PASSWORD`

### 7.3 小程序 / 外部桥接

- `ECOMIND_API_KEY`
- `ECOMIND_MONITORING_SUMMARY_URL`
- `ECOMIND_PUSH_URL`
- 可选：`ECOMIND_PUSH_STATUS_URL`

## 8. 测试与 CI

当前保留且有效的回归测试：

- `backend-cloudrun/tests/test_ai_report_frequency_regression.py`
- `backend-cloudrun/tests/test_latest_data_status_regression.py`
- `backend-cloudrun/tests/test_openapi_integration_endpoints.py`

GitHub Actions：

- `.github/workflows/backend-frequency-regression.yml`

当前工作流应覆盖：

- Pandas 频率兼容回归
- 最新数据状态字段兼容
- OpenAPI 监测摘要 / 回传 / 状态回查接口回归

## 9. 当前建议保留的核心文档

- [docs/MINIPROGRAM_ECOMIND_OPENAPI.md](docs/MINIPROGRAM_ECOMIND_OPENAPI.md)
- [docs/ECOMIND_PLATFORM_ALIGNMENT.md](docs/ECOMIND_PLATFORM_ALIGNMENT.md)
- [docs/VIDEO_ENTERPRISE_ACCESS_CHECKLIST.md](docs/VIDEO_ENTERPRISE_ACCESS_CHECKLIST.md)
- [docs/openapi_agent_schema.json](docs/openapi_agent_schema.json)
- [docs/openclaw_agent_prompt.md](docs/openclaw_agent_prompt.md)
- [docs/sewage-processing-station README.md](docs/sewage-processing-station%20README.md)
- [docs/protocol_specs.md](docs/protocol_specs.md)
- [docs/用户使用手册.md](docs/%E7%94%A8%E6%88%B7%E4%BD%BF%E7%94%A8%E6%89%8B%E5%86%8C.md)

规范类参考资料也保留在 `docs/` 下，供后续视频联动、协议接入、环保标准适配时查阅。

## 10. 后续开发约束

1. 不破坏双 API 体系：`/api/v1` 给前端业务，`/openapi` 给外部桥接
2. 多租户隔离优先于便利性，所有查询都必须落到明确 `org_id`
3. AI 报告必须优先返回企业可执行结论，不要只返回技术指标
4. 视频联动默认遵循“证据闭环优先，轻量判断增强”的路线
5. 新增外部接口时，优先补测试和联调文档，再发版
