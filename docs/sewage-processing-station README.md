# 污水站运维小程序

面向企业微信场景的污水站运维小程序。当前版本已经从“功能堆叠”调整为“低认知负担的向导式骨架”，主线围绕 4 个页面展开：

- 首页：先看企业整体工作状态
- 巡检：先选企业，再选站点，再按步骤执行巡检
- 报告：先看企业报告进度，再进入站点报告工作台
- 我的：只看当前运维工程师本人的个人工作卡

当前产品目标是把运维老师每天最常用的几件事收口为一条清晰主线：

`企业建档 -> 站点建档 / 首次盘点 -> 日常巡检 -> 自检报告 / OCR -> 执行包导出 -> 数据关联`

## 当前信息架构

### 首页

首页已经改成“企业工作状态总览”。

- 左上角展示品牌：`悦恩运维小管家`
- 右上角 `+`：新增企业档案
- 右上角放大镜：支持企业名 / 站点名模糊搜索
- 首页主体改为企业卡片，不再堆大量说明文字
- 企业卡片展示统一状态语言：
  - `待首次盘点`
  - `待建立基线`
  - `需重盘`
  - `待配模板`
  - `待巡检`
  - `已巡检`
  - `报告待导出`
  - `报告已导出`
  - `数据已关联`
  - `暂停运维`
- 点击企业卡片进入企业档案页
- 企业卡片支持直接给当前企业新增站点
- 首页顶部展示当前身份；`用户管理` 仅固定 `admin` 可见

### 巡检

巡检页已经改成“企业 -> 站点 -> 动作”的结构。

- 先展示“我的巡检企业”，管理员可看到“全部巡检企业”
- 展开企业后，按站点展示当前可执行状态
- 每个站点卡片只给一个明确下一步动作，例如：
  - `开始巡检`
  - `查看记录`
  - `去报告`
  - `去盘点`
- 巡检表单页已经改成向导式录入：
  - 基本信息
  - 巡检项逐项填写
  - 现场证据
  - 提交确认

### 报告

报告页已经拆成两层：

- `pages/reports/index`
  - 企业级报告首页
  - 先按时间范围展示企业与站点报告进度
  - 企业是交付单位，站点是材料单元
- `pages/reports/station/index`
  - 下沉后的站点报告工作台
  - 负责具体站点的自检报告上传、OCR、执行包导出、推送与关联

报告首页当前使用的状态语言为：

- `待上传报告`
- `待识别`
- `识别中`
- `识别失败`
- `待导出`
- `导出中`
- `导出失败`
- `报告已导出`
- `关联中`
- `关联失败`
- `数据已关联`
- `暂停运维`

### 我的

`我的` 页已经收口为单张“个人工作卡”，不再放联调入口和超管操作。

- 姓名
- 角色
- 负责企业数
- 负责站点数
- 当前待办：
  - `待巡检`
  - `待上传`
  - `待导出`
  - `待关联`
  - `异常`
- 一句“当前重点”提示，直接告诉运维工程师现在最该处理什么

## 当前已实现

### 小程序端

- 4 个一级 Tab：
  - `首页`
  - `巡检`
  - `报告`
  - `我的`
- 企业 / 站点档案管理
- 创建企业时整合首个站点建档
- 首页企业卡片总览、搜索、快捷新增
- 统一角色体系：
  - `admin`
  - `engineer`
  - `viewer`
- 用户管理页：
  - 添加运维工程师角色
  - 启用 / 禁用
  - 删除
  - 企业归属转移
  - 批量转移某工程师负责的全部企业
- 首页仅 `admin` 显示 `用户管理` 入口
- 站点生命周期与基线状态可视化
- 首次盘点 / 重新盘点 / 运维基线链路
- 多工艺日常巡检模板匹配
- 巡检记录列表与详情
- 现场证据上传、图片预览、视频展示
- 自检报告上传
- OCR 发起、OCR 结果查看、人工校正、差异对比
- 企业级报告首页
- 站点级报告工作台
- 执行包异步导出
- 摘要 / 清单打开
- ZIP 链接复制
- 数据推送与关联状态回查
- 任务中心轮询：
  - OCR
  - 导出
  - 推送 / 关联
- `我的` 页个人工作卡
- `issues` 相关页面保留，用于历史兼容回查，不再作为当前主流程主入口

### 云托管后端

- Fastify API 服务
- 内存 / MySQL 双持久化模式
- 自动数据库迁移
- 企业 / 站点 / 巡检模板 / 巡检记录接口
- 运维角色管理与企业归属转移接口
- 月度工作报表导出接口
- 企业微信 `userId` 审计字段入模
- 首次盘点、重新盘点、运维基线接口
- 附件上传接口
- CloudBase 对象存储集成
- 月报预览 / 草稿生成接口
- 自检报告 OCR 异步任务流
- OCR 原始结果、人工校正结果、校正人、校正时间留痕
- 执行包真实 ZIP 导出与制品下载接口
- `manifest` 包含 `sha256`、文件大小、生成时间、生成人
- `EcoMind-AI` 推送异步任务流
- 启动恢复、超时判定、失败重试
- 结构化日志与 webhook 告警钩子
- 在线监测摘要聚合骨架接口

## 当前角色说明

### 管理员 `admin`

- 查看全部企业
- 新增企业
- 新增站点
- 进入用户管理
- 管理运维工程师角色
- 转移企业归属
- 导出月度工作报表

### 运维工程师 `engineer`

- 查看自己负责企业
- 新增企业
- 给自己负责企业新增站点
- 执行巡检
- 推进报告链路
- 查看个人工作卡

### 只读查看 `viewer`

- 只读查看分配范围内数据
- 不能发起巡检、导出或推送

## 当前目录结构

- `miniprogram/`：企业微信 / 微信小程序前端
- `cloudrun/`：云托管后端服务
- `database-schemas/`：数据模型草案
- `specs/`：MVP 拆解与需求草稿

## 页面路由

当前小程序主页面如下：

- `pages/home/index`：首页
- `pages/inspection/index`：巡检首页
- `pages/inspection/form/index`：巡检表单向导
- `pages/inspection/records/index`：巡检记录
- `pages/reports/index`：报告中心企业首页
- `pages/reports/station/index`：站点报告工作台
- `pages/reports/detail/index`：单份自检报告详情
- `pages/reports/ocr-edit/index`：OCR 校正页
- `pages/inventory/index`：盘点 / 基线
- `pages/profile/index`：我的
- `pages/admin/operators/index`：用户管理
- `pages/enterprise/index`：企业 / 站点档案
- `pages/enterprise/form/index`：企业 / 站点建档页

## 本地开发

### 小程序端

1. 用微信开发者工具或企业微信开发工具打开 `miniprogram/`
2. 安装依赖

```bash
cd miniprogram
npm install
```

3. 类型检查

```bash
npm run typecheck
```

开发态当前通过请求头 `x-wecom-user-id` 模拟企业微信身份，默认 userId 为：

```text
YaoXiao
```

### 云托管后端

```bash
cd cloudrun
npm install
npm run dev
```

测试命令：

```bash
npm test
```

## 持久化模式

### 内存模式

```env
DATA_PROVIDER=memory
```

适合本地原型和接口联调。

### MySQL 模式

```env
DATA_PROVIDER=mysql
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=station_ops
MYSQL_USER=root
MYSQL_PASSWORD=replace_me
```

说明：

- 服务启动时会自动执行迁移
- 生产环境必须使用 `mysql`

## 自动迁移

迁移入口：`cloudrun/src/data/migrations.ts`

手动执行：

```bash
cd cloudrun
npm run db:migrate
```

## CloudBase 对象存储

如果要正式存储附件和执行包制品，请配置：

```env
CLOUDBASE_ENV_ID=
CLOUDBASE_SECRET_ID=
CLOUDBASE_SECRET_KEY=
CLOUDBASE_SESSION_TOKEN=
EXPORT_ARTIFACT_STORAGE=cloudbase
ECOMIND_MONITORING_SUMMARY_URL=
```

说明：

- 附件可上传到 CloudBase
- 执行包 ZIP、摘要、manifest 可存入 CloudBase
- `ECOMIND_MONITORING_SUMMARY_URL` 用于把 EcoMind 数采仪统计拉入运维简报
- 该变量应指向“按站点或设备、MN、时间范围返回污染物统计”的摘要接口，不是 `/openapi/device/status`
- 未配置时，仅允许本地 / 测试环境使用回退方案

## 百度 OCR 配置

如果要启用真实 OCR，请配置：

```env
BAIDU_OCR_APP_ID=
BAIDU_OCR_API_KEY=
BAIDU_OCR_SECRET_KEY=
BAIDU_OCR_MAX_PAGES=10
```

说明：

- 未配置百度 OCR 时，开发 / 测试环境会使用本地占位 OCR
- 生产环境缺少 OCR 配置会拒绝启动

## 生产环境关键变量

```env
NODE_ENV=production
DATA_PROVIDER=mysql
CLOUDBASE_ENV_ID=
BAIDU_OCR_API_KEY=
BAIDU_OCR_SECRET_KEY=
ECOMIND_API_KEY=
ECOMIND_MONITORING_SUMMARY_URL=
ECOMIND_PUSH_URL=
OPS_ALERT_WEBHOOK_URL=
ASYNC_TASK_SUPERVISOR_INTERVAL_MS=60000
OCR_TASK_TIMEOUT_MINUTES=10
EXPORT_TASK_TIMEOUT_MINUTES=15
PUSH_TASK_TIMEOUT_MINUTES=10
```

说明：

- `ECOMIND_MONITORING_SUMMARY_URL`：运维简报拉取在线监测统计的正式接口地址
- `ECOMIND_PUSH_URL`：执行包推回 EcoMind 并形成“数据已关联”状态的正式接口地址
- 当前现网业务中，这两个变量都属于必需项

## 真机调试提示

### `Invalid SiteMap`

真机调试如果报：

```text
Invalid SiteMap, sitemap错误，缺少rules字段
```

请确认 `miniprogram/sitemap.json` 至少包含：

```json
{
  "desc": "污水站运维小程序页面索引配置",
  "rules": [
    {
      "action": "allow",
      "page": "*"
    }
  ]
}
```

### 真机空白页

如果开发者工具正常，但 iOS 真机空白，优先检查：

- `sitemap.json` 是否合法
- 是否已经清缓存并重新编译
- 后端接口地址是否可被真机访问
- 当前账号权限是否导致页面请求失败后无可见数据

## 当前主流程

1. 创建企业档案，并在建档时补入首个站点
2. 为企业分配运维负责人
3. 完成首次盘点，建立运维基线
4. 从巡检页按企业和站点推进日常巡检
5. 上传自检报告并发起 OCR，必要时人工校正
6. 从报告中心查看企业级进度
7. 进入站点报告工作台导出执行包
8. 推送并完成数据关联
9. 在“我的”页回看当前运维工程师的待办与重点事项

## 当前说明

- 当前小程序骨架已经基本搭建完成
- 前端主信息架构已经从“说明书式页面”调整为“步骤式和状态式页面”
- 历史 `issues` 相关能力保留兼容，但不再作为当前产品主线
- 小程序后端如需接入 `EcoMind OpenAPI`，请直接参考 `docs/MINIPROGRAM_ECOMIND_OPENAPI.md`
- 后续更适合继续做：
  - 页面细节收口
  - 真机交互打磨
  - 接入正式企业微信身份
  - 正式部署与生产环境联调
