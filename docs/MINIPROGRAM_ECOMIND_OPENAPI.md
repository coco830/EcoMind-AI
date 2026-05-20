# 小程序后端对接 EcoMind 说明

> 适用场景：运维小程序后端服务多个企业，小程序端可按企业切换。
> 文档日期：2026-04-13

## 1. 重要更正

这份文档现在明确区分两类能力：

1. 现有污水站运维后端已经在使用的 EcoMind 集成链路
2. 后续可扩展的小程序只读 OpenAPI 查询链路

前者是当前现网业务必须保留的，后者是增强项，不能混为一谈。

尤其需要更正两点：

- `ECOMIND_PUSH_URL` 对当前运维后端不是可选项，而是现网必需项。
- `ECOMIND_MONITORING_SUMMARY_URL` 不能写成 `/openapi/device/status`。

原因很明确：

- 当前运维简报链路需要的是“按站点或设备、MN、时间范围返回污染物统计”的摘要接口。
- `/openapi/device/status` 只提供设备在线/离线/报警状态摘要，不是运维简报统计接口。
- 当前报告链路还需要“执行包导出后推回 EcoMind 并回查关联状态”，所以 `ECOMIND_PUSH_URL` 也必须保留。

## 2. 对接原则

如果你们复用的是当前污水站运维后端，那么应该按“拉取 + 推送”双链路设计：

- 拉取链路：把 EcoMind 数采仪数据拉进运维简报
- 推送链路：把执行包推回 EcoMind，形成“报告已导出 / 数据已关联”

这两条链路都要保留，不能因为小程序前端本身只做主动拉取，就把现有后端的推送链路删掉。

如果后续再做“小程序只读直连 OpenAPI”的增强能力，再额外接设备状态、最新数据、报警、AI 预测、AI 报告即可。

## 3. 当前现网部署必需环境变量

下面这组变量，适用于你们当前污水站运维后端继续跑“运维简报 + 执行包导出 + 数据关联”主流程。

```env
APP_ENV=production
DATA_PROVIDER=mysql

MYSQL_HOST=
MYSQL_PORT=
MYSQL_DATABASE=
MYSQL_USER=
MYSQL_PASSWORD=

CLOUDBASE_ENV_ID=
CLOUDBASE_SECRET_ID=
CLOUDBASE_SECRET_KEY=
CLOUDBASE_SESSION_TOKEN=
EXPORT_ARTIFACT_STORAGE=cloudbase

BAIDU_OCR_APP_ID=
BAIDU_OCR_API_KEY=
BAIDU_OCR_SECRET_KEY=
BAIDU_OCR_MAX_PAGES=10

ECOMIND_API_KEY=
ECOMIND_MONITORING_SUMMARY_URL=https://ecomind-ai-193380-4-1304218020.sh.run.tcloudbase.com/openapi/monitoring/summary
ECOMIND_PUSH_URL=https://ecomind-ai-193380-4-1304218020.sh.run.tcloudbase.com/openapi/package/push
```

说明：

- `ECOMIND_API_KEY`：EcoMind 侧访问凭证。
- `ECOMIND_MONITORING_SUMMARY_URL`：供运维简报拉取在线监测统计使用，当前正式路径为 `POST /openapi/monitoring/summary`。
- `ECOMIND_PUSH_URL`：供执行包推回 EcoMind 并形成关联状态使用，当前正式路径为 `POST /openapi/package/push`。
- 如需做回传状态回查，可额外配置 `ECOMIND_PUSH_STATUS_URL=https://ecomind-ai-193380-4-1304218020.sh.run.tcloudbase.com/openapi/package/push/status`。

## 3.1 这两个 EcoMind 地址的真实语义

### `ECOMIND_MONITORING_SUMMARY_URL`

这个变量当前应该指向“监测摘要聚合接口”，而不是设备状态接口。

它至少应满足这些特征：

- 支持按站点或设备查询
- 支持传 `mnCode` 或等价设备标识
- 支持时间范围
- 返回污染物统计结果，而不是单纯设备在线状态
- 当前运维后端按它的既有请求方式调用时能够成功返回

在你们现有业务里，它更接近：

- “报表统计接口”
- “监测摘要聚合接口”
- “月报/简报数据源接口”

当前正式实现地址为：

```text
https://ecomind-ai-193380-4-1304218020.sh.run.tcloudbase.com/openapi/monitoring/summary
```

### `ECOMIND_PUSH_URL`

这个变量当前必须保留。

它的作用不是给小程序前端做消息推送，而是给你们现有污水站运维后端完成：

- 执行包上传
- 数据关联
- 关联状态回查

当前正式实现地址为：

```text
https://ecomind-ai-193380-4-1304218020.sh.run.tcloudbase.com/openapi/package/push
```

## 3.2 当前已开放的调用方式

### 监测摘要接口

请求方式：

```http
POST /openapi/monitoring/summary
Content-Type: application/json
X-API-Key: ecomind_xxx
```

请求体示例：

```json
{
  "orgId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "mnCode": "MN123456789",
  "startDate": "2026-04-01",
  "endDate": "2026-04-30"
}
```

返回重点字段：

- `data.mnCode`
- `data.deviceName`
- `data.pollutantCount`
- `data.totalDataPoints`
- `data.items[]`

### 执行包回传接口

请求方式：

```http
POST /openapi/package/push
Content-Type: multipart/form-data
X-API-Key: ecomind_xxx
```

表单字段：

- `metadata`：JSON 字符串
- `package`：ZIP 文件

最小 `metadata` 示例：

```json
{
  "jobId": "export_job_xxx",
  "packageName": "企业A-站点B-执行包",
  "enterprise": {
    "id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "name": "企业A"
  },
  "station": {
    "id": "station_xxx",
    "name": "站点B"
  }
}
```

返回重点字段：

- `data.pushJobId`
- `data.documentLink`
- `data.status`
- `data.message`

### 执行包回传状态查询接口

请求方式：

```http
GET /openapi/package/push/status?pushJobId=<push_job_id>
X-API-Key: ecomind_xxx
```

推荐查询参数：

- `pushJobId`：优先推荐，精确查询
- `sourceJobId`：可选，按业务侧导出任务ID查询最近一次回传记录
- `org_id` 或 `enterprise_name`：当 `all_orgs` Key 按 `sourceJobId` 查询时必传其一

返回重点字段：

- `data.pushJobId`
- `data.sourceJobId`
- `data.documentLink`
- `data.status`
- `data.message`
- `data.receivedAt`
- `data.updatedAt`

说明：

- `single_org` Key 下，可直接按 `pushJobId` 或 `sourceJobId` 查询本企业记录。
- `all_orgs` Key 下，如果只按 `sourceJobId` 查询，必须带 `org_id` 或 `enterprise_name`，避免跨企业歧义。
- 当前返回里的 `documentLink` 仍为平台对象存储链接，供状态关联和审计留痕使用。

### 当前鉴权说明

这两条桥接接口当前复用现有 `X-API-Key` 验证和企业范围校验。

也就是说：

- 你们当前已经可用的 `ECOMIND_API_KEY` 可以直接用于联调
- 当前这两条桥接接口不额外依赖新的 tool permission 配置

## 4. 小程序只读 OpenAPI 增强变量

下面这组变量不属于当前现网主链路必需项，而是后续如果要让小程序直接展示 EcoMind 的设备状态、最新数据、报警、AI 预测、AI 报告时，才建议追加。

```env
ECOMIND_API_BASE_URL=https://ecomind-ai-193380-4-1304218020.sh.run.tcloudbase.com
ECOMIND_API_SCOPE=all_orgs
ECOMIND_ENTERPRISE_SELECTOR_MODE=org_id
ECOMIND_REQUEST_TIMEOUT_MS=10000

ECOMIND_DEVICE_STATUS_URL=https://ecomind-ai-193380-4-1304218020.sh.run.tcloudbase.com/openapi/device/status
ECOMIND_LATEST_DATA_URL=https://ecomind-ai-193380-4-1304218020.sh.run.tcloudbase.com/openapi/data/latest
ECOMIND_ACTIVE_ALARMS_URL=https://ecomind-ai-193380-4-1304218020.sh.run.tcloudbase.com/openapi/alarm/active
ECOMIND_AI_PREDICT_URL=https://ecomind-ai-193380-4-1304218020.sh.run.tcloudbase.com/openapi/ai/predict
ECOMIND_AI_REPORT_URL=https://ecomind-ai-193380-4-1304218020.sh.run.tcloudbase.com/openapi/ai/report

ECOMIND_DEFAULT_PREDICTION_HOURS=4
ECOMIND_DEFAULT_REPORT_DATE_MODE=today
ECOMIND_ORG_MAPPING_SOURCE=database
```

说明：

- 这里把设备状态接口单独命名为 `ECOMIND_DEVICE_STATUS_URL`，避免再和 `ECOMIND_MONITORING_SUMMARY_URL` 混用。
- 这组变量是 OpenAPI 查询增强项，不替代现网 `ECOMIND_MONITORING_SUMMARY_URL` 和 `ECOMIND_PUSH_URL`。

## 3. API Key 方案

## 3.1 推荐方案

小程序后端使用一个 `all_orgs` 的平台只读 Key。

推荐权限：

- `get_device_status`
- `get_latest_data`
- `get_active_alarms`
- `get_ai_prediction`
- `get_ai_report`

不建议给小程序后端开放：

- `acknowledge_alarm`

因为小程序当前定位是运维查看和辅助决策，不是直接替企业执行报警处置动作。

## 3.2 推荐创建载荷

由 EcoMind 平台超管调用 `POST /api/v1/api-keys` 创建：

```json
{
  "name": "mp-platform-readonly-prod",
  "org_id": "你们平台管理组织的org_id",
  "access_scope": "all_orgs",
  "permissions": [
    "get_device_status",
    "get_latest_data",
    "get_active_alarms",
    "get_ai_prediction",
    "get_ai_report"
  ],
  "rate_limit": 120
}
```

说明：

- `org_id` 在 `all_orgs` 模式下主要用于审计归属，不做数据过滤。
- `rate_limit` 建议至少 `120` 次/分钟，适合一个小程序后端服务多个企业的读请求。

## 4. 企业切换的推荐实现

## 4.1 推荐做法

小程序前端切换企业时，只把你们自己系统里的企业标识传给小程序后端。

小程序后端内部维护一张映射表：

| 小程序企业ID | 企业名称 | EcoMind org_id | 状态 |
|---|---|---|---|
| mp_org_001 | 云南某某水务 | xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx | enabled |

小程序后端调用 EcoMind 时：

1. 先用小程序企业ID查出对应 `EcoMind org_id`
2. 再调用 EcoMind OpenAPI
3. 查询参数优先传 `org_id`

## 4.2 为什么不建议直接用企业名称

因为当前 EcoMind 的 `all_orgs` 查询逻辑对 `enterprise_name` 是模糊匹配：

- 匹配不到会返回 `ENTERPRISE_NOT_FOUND`
- 匹配到多个会返回 `ENTERPRISE_AMBIGUOUS`
- 完全不传会返回 `MISSING_ENTERPRISE_SELECTOR`

所以正式环境应把 `enterprise_name` 当兜底，不要当主链路。

## 5. 统一调用规范

## 5.1 请求头

所有请求统一使用：

```http
X-API-Key: ecomind_xxx
```

## 5.2 查询企业参数

推荐统一使用：

```text
org_id=<EcoMind组织ID>
```

仅在 `org_id` 暂时未建档时，才临时使用：

```text
enterprise_name=<企业名称>
```

## 5.3 设备参数

优先级建议如下：

1. `device_mn`
2. `device_name`

原因：

- `device_mn` 是精确匹配
- `device_name` 是模糊匹配

## 6. 小程序后端对接 EcoMind OpenAPI 的接口说明

注意：

- 本节说明的是后续“小程序只读 OpenAPI 增强能力”。
- 本节接口不能替代当前现网 `ECOMIND_MONITORING_SUMMARY_URL` 所代表的运维简报摘要接口。

## 6.1 查询设备状态摘要

用于首页或企业概况页展示“在线/离线/报警/维护中”设备统计。

**接口**

```http
GET /openapi/device/status
```

**推荐请求参数**

| 参数 | 必填 | 说明 |
|---|---|---|
| `org_id` | 是 | EcoMind 企业组织ID |
| `status_filter` | 否 | `online` / `offline` / `alarm` / `maintenance` |

**请求示例**

```bash
curl -X GET \
  "https://ecomind-ai-193380-4-1304218020.sh.run.tcloudbase.com/openapi/device/status?org_id=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" \
  -H "X-API-Key: ecomind_xxx"
```

**返回重点**

- `data.enterprise`：企业名称
- `data.devices`：设备列表
- `data.status_summary.total`：设备总数
- `data.status_summary.online`：在线数
- `data.status_summary.offline`：离线数
- `data.status_summary.alarm`：报警数
- `summary`：一句话摘要

**适合小程序展示的位置**

- 企业首页概况卡片
- 站点设备状态总览

## 6.2 查询最新监测数据

用于企业详情、站点详情、设备详情查看当前污染物最新值和达标状态。

**接口**

```http
GET /openapi/data/latest
```

**推荐请求参数**

| 参数 | 必填 | 说明 |
|---|---|---|
| `org_id` | 是 | EcoMind 企业组织ID |
| `device_mn` | 否 | 设备 MN，优先推荐 |
| `device_name` | 否 | 设备名称，模糊匹配 |

说明：

- 如果不传 `device_mn` 和 `device_name`，接口会返回该企业命中的第一台设备数据。
- 正式环境不建议省略设备条件，避免取错设备。

**返回重点**

- `data.device_name`
- `data.device_mn`
- `data.readings[]`
- `data.exceed_count`
- `data.warning_count`
- `summary`

`readings[]` 里对小程序最有用的字段：

- `pollutant`
- `current_value`
- `unit`
- `threshold`
- `compliance_status`
- `risk_level`
- `measurement_time`

**适合小程序展示的位置**

- 站点实时数据卡片
- 企业风险总览中的“接近超标/超标”提醒

## 6.3 查询当前活跃报警

用于企业当前报警列表、待处理风险列表。

**接口**

```http
GET /openapi/alarm/active
```

**推荐请求参数**

| 参数 | 必填 | 说明 |
|---|---|---|
| `org_id` | 是 | EcoMind 企业组织ID |
| `level` | 否 | `info` / `warning` / `critical` |
| `limit` | 否 | 默认 20，最大 100 |

**返回重点**

- `data.alarms[]`
- `data.summary.total_pending`
- `data.summary.critical`
- `data.summary.warning`
- `summary`

`alarms[]` 里建议重点使用：

- `device_name`
- `alarm_type`
- `severity`
- `pollutant`
- `message`
- `current_value`
- `threshold`
- `created_at`
- `duration`

**适合小程序展示的位置**

- 企业待处理风险页
- 首页红黄预警聚合卡

## 6.4 查询 AI 趋势预测

用于给企业看“现在还没超，但未来几小时可能有风险”。

**接口**

```http
GET /openapi/ai/predict
```

**推荐请求参数**

| 参数 | 必填 | 说明 |
|---|---|---|
| `org_id` | 是 | EcoMind 企业组织ID |
| `device_mn` | 否 | 推荐精确传 |
| `device_name` | 否 | 模糊匹配 |
| `pollutant_code` | 否 | 默认 `w01018`，即 COD |
| `prediction_hours` | 否 | 1-24，建议默认 4 |

**返回重点**

- `data.pollutant`
- `data.current_value`
- `data.predictions[]`
- `data.risk_assessment.exceed_risk`
- `data.risk_assessment.risk_description`
- `data.risk_assessment.exceed_risk_time`
- `data.used_fallback_pollutant`
- `summary`

说明：

- 当请求的污染物历史数据不足时，EcoMind 会自动回退到最近有数据的污染物。
- 小程序后端应关注 `used_fallback_pollutant`，避免前端误以为当前展示的一定是原请求污染物。

**适合小程序展示的位置**

- 风险预判页
- 企业运维建议页
- “未来 4 小时风险”卡片

## 6.5 查询 AI 运维报告

用于展示该企业/站点当天或最近一次 AI 运维诊断结果。

**接口**

```http
GET /openapi/ai/report
```

**推荐请求参数**

| 参数 | 必填 | 说明 |
|---|---|---|
| `org_id` | 是 | EcoMind 企业组织ID |
| `device_mn` | 否 | 推荐精确传 |
| `device_name` | 否 | 模糊匹配 |
| `report_date` | 否 | `YYYY-MM-DD`，默认当天 |

**返回重点**

- `data.report_content`
- `data.requested_report_date`
- `data.actual_report_date`
- `data.used_fallback_report`
- `data.fallback_reason`
- `data.generated_at`
- `data.stats_snapshot`
- `summary`

说明：

- 如果目标日期没有报告，EcoMind 会自动回退到最近可用日报。
- 小程序后端要把 `actual_report_date` 和 `used_fallback_report` 一起返回给前端，避免用户误以为看到的是当天新报告。

**适合小程序展示的位置**

- 企业运维建议页
- 站点 AI 报告页
- 日常巡检后的辅助判断页

## 7. 小程序后端封装建议

建议小程序后端不要把 EcoMind OpenAPI 直接透传给前端，而是在你们自己的后端收口成以下内部接口：

- `GET /miniapp/orgs/:id/monitoring-summary`
- `GET /miniapp/orgs/:id/latest-data`
- `GET /miniapp/orgs/:id/active-alarms`
- `GET /miniapp/orgs/:id/ai-prediction`
- `GET /miniapp/orgs/:id/ai-report`

这样做的好处：

- 前端不需要感知 `org_id`、`device_mn`、`X-API-Key`
- 后端可以统一做企业映射、缓存、超时处理和错误翻译
- 后面 EcoMind 接口升级时，小程序前端无需跟着改

## 8. 错误处理建议

小程序后端应重点识别这些错误码：

| 错误码 | 含义 | 建议处理 |
|---|---|---|
| `MISSING_API_KEY` | 未传 API Key | 检查服务端环境变量 |
| `INVALID_API_KEY` | API Key 无效 | 更换新 Key |
| `API_KEY_DISABLED` | API Key 被禁用 | 联系 EcoMind 管理员启用 |
| `API_KEY_EXPIRED` | API Key 过期 | 更换或续期 |
| `MISSING_ENTERPRISE_SELECTOR` | `all_orgs` 模式未传企业条件 | 检查小程序后端是否传了 `org_id` |
| `ORG_NOT_FOUND` | `org_id` 不存在 | 检查企业映射表 |
| `ENTERPRISE_NOT_FOUND` | 企业名未匹配到 | 检查企业名称或改用 `org_id` |
| `ENTERPRISE_AMBIGUOUS` | 企业名匹配多个结果 | 不要继续用模糊企业名，改用 `org_id` |
| `PERMISSION_DENIED` | Key 没有该接口权限 | 重新创建权限完整的只读 Key |

## 9. 缓存与频控建议

建议小程序后端增加轻量缓存：

- 设备状态摘要：缓存 30-60 秒
- 最新监测数据：缓存 15-30 秒
- 活跃报警：缓存 15-30 秒
- AI 预测：缓存 5 分钟
- AI 报告：缓存 10-30 分钟

原因：

- 小程序页面经常会反复进入、下拉刷新
- 同一个企业多个用户会看同一批数据
- 这样可以显著减少 EcoMind OpenAPI 压力

## 10. 联调 mnCode 获取方式

为了让小程序侧尽快拿到一条真实可用的联调设备，平台侧已经补了一个现成脚本：

```bash
python backend-cloudrun/scripts/pick_test_mn_code.py --json
```

如果只想在某个企业范围内挑设备，可加条件：

```bash
python backend-cloudrun/scripts/pick_test_mn_code.py --days 14 --org-id xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx --json
```

脚本返回重点字段：

- `orgId`
- `enterprise`
- `deviceName`
- `mnCode`
- `recentPoints`
- `latestDataTime`

如果你们更习惯直接跑 SQL，也可以使用下面这条：

```sql
SELECT
  d.org_id,
  o.name AS enterprise_name,
  d.name AS device_name,
  d.mn AS mn_code,
  d.status AS device_status,
  COUNT(md.id) AS recent_points,
  MAX(md.ts) AS latest_data_time
FROM devices d
JOIN organizations o ON o.id = d.org_id
LEFT JOIN monitoring_data md
  ON md.device_id = d.mn
 AND md.org_id = d.org_id
 AND md.ts >= NOW() - INTERVAL 7 DAY
WHERE d.mn IS NOT NULL
  AND d.mn <> ''
GROUP BY d.org_id, o.name, d.name, d.mn, d.status
HAVING COUNT(md.id) > 0
ORDER BY recent_points DESC, latest_data_time DESC
LIMIT 1;
```

## 11. 最终结论

对你们当前这个运维小程序和污水站运维后端，最终应按“两层接法”理解：

1. 现网主链路必须保留 `ECOMIND_MONITORING_SUMMARY_URL` 和 `ECOMIND_PUSH_URL`
2. `ECOMIND_MONITORING_SUMMARY_URL` 代表运维简报统计接口，不能写成 `/openapi/device/status`
3. `ECOMIND_PUSH_URL` 代表执行包推回 EcoMind 的接口，当前仍然是必需项
4. 小程序如果还要增加设备状态、实时数据、报警、AI 预测、AI 报告，再额外接 OpenAPI 只读接口
5. OpenAPI 只读接口是增强层，不替代现有“简报拉取 + 执行包推送”主流程

这样处理后，既能保住现网业务闭环，也能给小程序后续能力扩展留好接口位。
