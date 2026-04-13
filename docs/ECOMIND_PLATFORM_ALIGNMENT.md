# 运维小程序后端与 EcoMind-AI 平台能力需求对齐及联调文档

> 用途：作为项目内部跨系统联调文档，用于对齐“运维小程序后端”与“EcoMind-AI 平台能力”之间的接口、责任边界和联调顺序。  
> 文档日期：2026-04-13  
> 当前版本：V1

## 1. 文档目的

这份文档只解决一件事：

把“运维小程序后端”与“EcoMind-AI 平台能力”之间，当前必须协同的链路说清楚，避免同一项目内部不同系统之间理解不一致，导致接口地址、字段语义、联调顺序和交付目标错位。

当前我们需要在项目内部对齐以下内容：

1. 第一阶段到底先打通哪条主链路
2. 现阶段哪些事情由我方可以独立完成
3. 哪些事情必须由 EcoMind-AI 平台提供接口或确认
4. 双方联调时需要以什么请求和返回为准
5. 当前应如何分阶段协同开发

## 2. 当前业务目标

我们这个小程序服务的是污水站运维团队，当前主业务流程已经基本成型，核心链路如下：

`企业建档 -> 站点建档 / 首次盘点 -> 日常巡检 -> 自检报告上传 -> OCR 识别 -> 运维简报生成 -> 执行包导出 -> EcoMind 回传`

在这条链路里，和 EcoMind-AI 平台有关的部分，当前分为两类：

### 2.1 第一类：当前必须跑通的主链路

- 从 EcoMind-AI 拉取在线监测摘要数据
- 把这部分数采摘要整合进运维简报和执行包

这部分直接影响我们后端是否能真正投入联调和部署。

### 2.2 第二类：当前保留但可后置的链路

- 执行包导出后回传到 EcoMind-AI
- 在我方系统中保留回传状态、文档链接、失败原因

这部分也重要，但根据我们当前部署策略，允许放在第二阶段联调。

## 3. 当前双方建议采用的协同策略

结合我们目前代码实现和部署安排，建议按“两阶段协同”推进，而不是一次性把所有 OpenAPI 能力全部压上来。

### 第一阶段：先打通主链路

目标：

- 让我们后端先能稳定部署
- 让运维简报能真实整合 EcoMind 数采摘要
- 先把“巡检 + OCR + 简报 + 数采摘要整合”跑通

这一阶段，平台能力侧必须优先提供并确认：

1. `ECOMIND_MONITORING_SUMMARY_URL` 的正式接口地址
2. 该接口的真实请求方式
3. 该接口的真实请求字段
4. 该接口的真实返回字段
5. 该接口的鉴权方式
6. 至少 1 组真实联调样例

### 第二阶段：补齐回传链路

目标：

- 执行包导出后，可以真实回传到 EcoMind-AI
- 双方共同确认回传成功标准、返回标识、失败原因和后续追踪方式

这一阶段，平台能力侧再补充：

1. `ECOMIND_PUSH_URL` 的正式接口地址
2. 回传接口的真实请求合同
3. 成功返回的字段约定
4. 错误码和失败语义
5. 是否有幂等要求
6. 是否有异步处理 / 回查 / 回调机制

## 4. 当前我方后端实现现状

为避免双方理解偏差，这里明确说明当前我方系统已经做好的部分。

### 4.1 我方已经具备的能力

- 已完成巡检、附件上传、自检报告上传、OCR 识别、人工校正、执行包导出
- 已实现运维简报预览和草稿生成
- 已预留 EcoMind 在线摘要整合能力
- 已预留执行包回传到 EcoMind 的能力
- 已实现任务状态记录、失败原因保留、重试机制和健康检查

### 4.2 我方当前部署策略

截至 2026 年 4 月 13 日，当前后端部署策略已经调整为：

- `ECOMIND_MONITORING_SUMMARY_URL`：生产环境必填
- `ECOMIND_PUSH_URL`：可缺省，但缺少时只告警，不阻塞服务启动

也就是说：

- 没有监测摘要接口地址，我们当前不做生产部署
- 没有回传地址，我们可以先部署，但“发起 EcoMind 回传”会被禁用

### 4.3 我方当前对用户侧的状态表达

为了避免业务口径失真，我们已经把状态语言统一成：

- `报告已导出`
- `回传中`
- `回传失败`
- `已回传`

也就是说，在 EcoMind-AI 平台没有真实确认“已接收 / 已处理 / 已入库”之前，我们不会再对外展示“数据已关联”这种容易误导的状态。

## 5. 当前需要 EcoMind-AI 平台确认的事项

下面这些事项，单靠运维小程序后端这一侧无法最终确认，必须由平台能力实现侧明确给出。

## 5.1 关于监测摘要接口

请平台能力实现侧明确提供：

1. 正式接口地址
2. 请求方法，是 `GET` 还是 `POST`
3. 鉴权方式，是 `X-API-Key`、`Authorization`，还是其他方式
4. 请求字段名
5. 时间范围字段格式
6. `mnCode` 是否就是平台能力侧的真实字段名
7. 返回字段结构
8. 错误码和错误信息说明
9. 至少 1 份真实请求示例
10. 至少 1 份真实返回示例

补充说明：

- 如果平台能力侧建议复用现有开放接口，请明确该接口是否真的支持“按 `mnCode` + 时间范围返回污染物统计”。
- 如果某个接口只能返回设备在线/离线/报警状态摘要，而不能返回污染物统计结果，则该接口不能替代本次主链路需要的监测摘要接口。
- 我方当前第一阶段需要的是“报表统计接口”或“监测摘要聚合接口”，不是单纯设备状态接口。

## 5.2 关于执行包回传接口

请平台能力实现侧明确提供：

1. 正式接口地址
2. 请求方法
3. 是否接受 `multipart/form-data`
4. 文件字段名
5. 元数据字段名
6. 成功返回的唯一标识字段
7. 是否回填文档链接或结果地址
8. 是否要求幂等键
9. 是否是同步成功，还是异步受理
10. 失败时的错误码和错误语义

## 6. 我方建议的最小接口合同

下面不是替平台能力侧拍板，而是我方当前最小消费要求。  
如果平台能力侧已有现成合同，只要能覆盖这些最小要求，我们可以按平台实际合同适配。

### 6.1 监测摘要接口最小合同

#### 我方用途

- 生成月度运维简报
- 生成执行包中的 `online-summary.json`
- 在简报中展示站点本周期在线监测摘要

#### 我方当前建议请求

请求方式建议：

```http
POST /xxx
```

请求头建议：

```http
X-API-Key: {api_key}
Content-Type: application/json
```

请求体建议：

```json
{
  "mnCode": "MN123456789",
  "startDate": "2026-04-01",
  "endDate": "2026-04-30"
}
```

#### 我方最小返回要求

返回中至少应能映射出以下字段：

```json
{
  "items": [
    {
      "pollutantCode": "w01018",
      "pollutantName": "COD",
      "unit": "mg/L",
      "averageValue": 25.3,
      "minValue": 18.2,
      "maxValue": 31.7,
      "completenessRate": 98.5
    }
  ]
}
```

如果平台能力侧字段名不同，也可以，但最终至少要能映射到：

- `pollutantCode`
- `pollutantName`
- `unit`
- `averageValue`
- `minValue`
- `maxValue`
- `completenessRate`

#### 我方失败处理预期

当接口失败时，希望平台能力侧返回明确失败原因，例如：

- 鉴权失败
- `mnCode` 不存在
- 时间范围非法
- 数据为空
- 平台内部错误

### 6.2 执行包回传接口最小合同

#### 我方用途

- 把导出的执行包 ZIP 回传到 EcoMind-AI
- 记录回传任务号、文档链接、失败原因

#### 我方当前建议请求

请求方式建议：

```http
POST /xxx
Content-Type: multipart/form-data
```

表单字段建议：

1. `metadata`
2. `package`

其中 `metadata` 预计为 JSON，内容类似：

```json
{
  "jobId": "export_job_xxx",
  "packageName": "企业A-站点B-2026-04-01_2026-04-30-执行包",
  "enterprise": {
    "id": "ent_xxx",
    "name": "企业A"
  },
  "station": {
    "id": "station_xxx",
    "name": "站点B"
  },
  "period": {
    "startDate": "2026-04-01",
    "endDate": "2026-04-30"
  },
  "manifest": {
    "inspectionRecordCount": 4,
    "selfMonitoringReportCount": 2,
    "onlineMetricCount": 6
  },
  "summaryText": "本周期完成巡检 4 次，已整合在线摘要 6 项指标。"
}
```

`package` 为 ZIP 文件本体。

#### 我方最小返回要求

如果回传成功，建议平台至少返回：

```json
{
  "pushJobId": "push_job_xxx",
  "documentLink": "https://example.com/doc/123",
  "message": "accepted"
}
```

其中最关键的是：

- `pushJobId`
- `documentLink` 或等价链接字段

如果平台能力侧字段名是 `jobId`、`url`、`link`、`documentUrl`，我方也可以兼容，但需要提前确认。

## 7. 双方责任划分建议

为了联调顺畅，建议责任边界明确如下。

### 7.1 我方负责

- 我方后端发起接口调用
- 我方后端保证不把平台密钥暴露到小程序前端
- 我方后端组织执行包 ZIP 和 metadata
- 我方系统保留调用日志、失败原因和操作留痕
- 我方在联调环境配合提供请求日志和报错截图
- 我方按平台真实合同完成字段适配

### 7.2 平台能力实现侧负责

- 提供正式或测试接口地址
- 提供真实接口合同
- 提供鉴权方式
- 提供请求示例和返回示例
- 提供错误码说明
- 提供联调用的测试数据或测试 `mnCode`
- 明确成功标准和失败标准

## 8. 建议联调顺序

建议按下面顺序推进。

### 第一步：先确认监测摘要接口

目标：

- 先让我们后端具备生产部署条件
- 先让运维简报能真实出数

双方要做的事：

- 平台能力实现侧提供正式或测试摘要接口
- 平台能力实现侧提供 1 组真实 `mnCode`
- 我方接入并验证简报是否能生成
- 双方确认字段映射和异常语义

### 第二步：再确认回传接口

目标：

- 让执行包能从我方系统真实回传到 EcoMind-AI

双方要做的事：

- 平台能力实现侧提供回传接口地址
- 平台能力实现侧确认是否使用 `multipart/form-data`
- 我方发送 1 个最小执行包样例
- 双方确认成功返回、失败返回和文档链接字段

### 第三步：做一次端到端联调

联调目标：

1. 在我方系统创建一条完整业务链路
2. 生成简报
3. 导出执行包
4. 发起回传
5. 双方确认平台能力侧已收到或已记录

## 9. 联调检查清单

建议双方对照下面清单逐项确认。

### 9.1 监测摘要接口检查项

- 是否有正式 URL
- 是否有测试 URL
- 是否有 API Key
- 是否已确认请求方法
- 是否已确认请求字段名
- 是否已确认时间格式
- 是否已提供真实返回样例
- 是否已提供错误码说明
- 是否已用真实 `mnCode` 验证成功

### 9.2 回传接口检查项

- 是否有正式 URL
- 是否有测试 URL
- 是否确认接受 `multipart/form-data`
- 是否确认文件字段名
- 是否确认 metadata 字段名
- 是否确认成功返回字段
- 是否确认错误码说明
- 是否确认是否需要幂等
- 是否已用真实 ZIP 样例验证成功

## 10. 当前希望 EcoMind-AI 平台先回复的内容

为了让联调尽快进入可执行状态，建议平台能力实现侧先优先明确下面 6 项：

1. `ECOMIND_MONITORING_SUMMARY_URL` 的正式或测试地址
2. 监测摘要接口的请求方法、鉴权方式、请求样例、返回样例
3. 是否可提供 1 个联调用 `mnCode`
4. `ECOMIND_PUSH_URL` 的正式或测试地址
5. 回传接口的请求样例、返回样例、错误码说明
6. 平台能力侧建议我们采用的一阶段 / 二阶段联调安排

### 10.1 建议平台能力侧直接按此模板回复

为提高联调效率，建议平台能力实现侧直接按下面模板回复：

```md
## 一、监测摘要接口

- 正式地址：
- 测试地址：
- 请求方法：
- 鉴权方式：
- 请求头要求：
- 请求字段：
- 时间范围字段格式：
- mnCode 是否为真实字段名：
- 是否支持按 mnCode + 时间范围返回污染物统计：
- 成功返回字段：
- 错误码说明：
- 真实请求示例：
- 真实返回示例：

## 二、执行包回传接口

- 正式地址：
- 测试地址：
- 请求方法：
- 鉴权方式：
- 是否接受 multipart/form-data：
- 文件字段名：
- metadata 字段名：
- 成功返回字段：
- 是否返回文档链接：
- 是否异步受理：
- 是否要求幂等：
- 错误码说明：
- 真实请求示例：
- 真实返回示例：

## 三、联调安排建议

- 是否认可先“监测摘要”，后“执行包回传”的两阶段联调：
- 可提供的联调时间：
- 可提供的测试 mnCode：
- 可提供的测试 API Key 或鉴权方式：
```

## 11. 我方当前结论

我方当前的明确结论如下：

1. 我们已经可以先进入后端部署和联调阶段
2. 当前第一优先级不是回传，而是监测摘要主链路
3. 只要监测摘要接口明确，我们就可以先把主链路跑起来
4. 回传接口可以紧接着进入第二阶段联调
5. 双方如果按“两阶段协同”推进，效率会比一次性全量对接口更高

如果项目内部认可以上思路，建议下一步直接进入：

- 监测摘要接口合同确认
- 测试地址与样例下发
- 第一轮联调

## 12. 当前平台侧已落地的接口地址

截至 2026-04-13，`backend-cloudrun` 已落地以下两个接口，可作为第一轮联调起点：

### 12.1 监测摘要接口

```text
POST /openapi/monitoring/summary
```

完整生产地址：

```text
https://ecomind-ai-193380-4-1304218020.sh.run.tcloudbase.com/openapi/monitoring/summary
```

当前实现能力：

- 支持 `X-API-Key`
- 支持 `mnCode + startDate + endDate`
- 支持按 `orgId` 或企业范围解析
- 返回污染物统计摘要、数据点数、完整率、时间窗信息

### 12.2 执行包回传接口

```text
POST /openapi/package/push
```

完整生产地址：

```text
https://ecomind-ai-193380-4-1304218020.sh.run.tcloudbase.com/openapi/package/push
```

当前实现能力：

- 支持 `X-API-Key`
- 支持 `multipart/form-data`
- 字段为 `metadata` + `package`
- 成功返回 `pushJobId`、`documentLink`、`status`、`message`

### 12.3 执行包回传状态查询接口

```text
GET /openapi/package/push/status
```

完整生产地址：

```text
https://ecomind-ai-193380-4-1304218020.sh.run.tcloudbase.com/openapi/package/push/status
```

当前实现能力：

- 支持 `X-API-Key`
- 支持按 `pushJobId` 精确查询
- 支持按 `sourceJobId` 查询最近一次回传记录
- `all_orgs` Key 按 `sourceJobId` 查询时，要求同时传 `org_id` 或 `enterprise_name`
- 成功返回 `pushJobId`、`sourceJobId`、`documentLink`、`status`、`message`、`receivedAt`、`updatedAt`

### 12.4 联调用 mnCode 获取方式

当前平台侧已补一个直接可跑的脚本：

```bash
python backend-cloudrun/scripts/pick_test_mn_code.py --json
```

脚本用途：

- 从 `devices + monitoring_data` 中自动挑一条最近有真实监测数据的设备
- 输出 `orgId`、企业名、设备名、`mnCode`、最近数据时间、近窗数据点数
- 可以直接给小程序侧作为第一轮联调样例

如果需要直接查库，也可以用这条 SQL：

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

### 12.5 当前联调建议

建议直接按下面顺序开始：

1. 小程序侧先接 `POST /openapi/monitoring/summary`
2. 用真实 `mnCode` 跑通月度简报整合
3. 再接 `POST /openapi/package/push`
4. 用一个最小 ZIP 执行包验证回传成功
5. 成功后按 `GET /openapi/package/push/status` 回查状态
