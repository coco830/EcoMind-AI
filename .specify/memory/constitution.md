<!--
  ===========================================================================
  SYNC IMPACT REPORT
  ===========================================================================
  Version Change: N/A → 1.0.0 (Initial creation)

  Added Principles:
  - I. 协议严格化 (Protocol Strictness)
  - II. 后端代码规范 (Backend Style)
  - III. 前端生成约束 (Frontend Constraints)
  - IV. 工程化结构 (Project Structure)
  - V. 测试与质量 (Testing & Quality)
  - VI. 简洁性原则 (Simplicity)

  Added Sections:
  - 技术栈约束 (Technology Stack Constraints)
  - 开发工作流 (Development Workflow)
  - 治理规则 (Governance)

  Templates Status:
  ✅ plan-template.md - Constitution Check section aligned
  ✅ spec-template.md - Requirements section aligned
  ✅ tasks-template.md - Phase structure aligned

  Follow-up TODOs: None
  ===========================================================================
-->

# EcoMind-AI Constitution

## Core Principles

### I. 协议严格化 (Protocol Strictness)

HJ 212 协议解析是系统核心，MUST 严格遵循国标规范：

- **禁止**使用正则表达式解析复杂嵌套报文，MUST 编写专用 `Parser` 类
- **MUST** 实现 CRC16 校验，校验失败直接丢弃或记录错误日志
- **MUST** 在解析逻辑中预留 SM4 解密钩子，即使当前无密钥，代码结构也要支持 `if encryption_enabled: decrypt()`
- **MUST** 将所有参数编码（如 `w01001`, `d20101`）定义在独立的 `enums.py` 或 `mappings.py` 中
- **禁止**在逻辑代码中硬编码（Hardcode）字符串
- **MUST** 兼容 HJ 212-2017 和 HJ 212-2025 双标准

**原理**: 环保数据采集的准确性直接影响监管合规性，协议解析错误可能导致法律风险。

### II. 后端代码规范 (Backend Style)

Python 后端代码 MUST 遵循以下规范：

- **Type Hinting**: 所有函数 MUST 包含类型注解，通过 `mypy` 检查
- **Pydantic**: 所有数据交互（API 请求/响应、数据库模型）MUST 使用 Pydantic Model 定义
- **Async First**: 所有 I/O 操作 MUST 使用 `async/await`
- **禁止**引入重型框架（Django、Java/C# 依赖）
- **MUST** 保持 `requirements.txt` 精简

**原理**: FastAPI + asyncio 架构确保高性能和低资源占用，适合处理大量数采仪并发连接。

### III. 前端生成约束 (Frontend Constraints)

Vue 3 前端代码 MUST 遵循以下规范：

- **组件一致性**: **严禁**混用 UI 库，所有组件**只能**使用 `Element Plus`
- **响应式布局**: 页面 MUST 适配 PC 端浏览器（1920x1080 及 1366x768）
- **Mock Data**: 在后端 API 未通之前，前端代码 MUST 包含 mock 数据生成逻辑
- **ECharts 封装**: **禁止**将庞大的 ECharts 配置项写在 Vue 组件里，MUST 封装成独立的 Hook 或 Component

**原理**: 统一的 UI 规范确保商业交付质量，mock 数据保证前后端可并行开发。

### IV. 工程化结构 (Project Structure)

项目文件组织 MUST 严格遵循以下结构：

```text
EcoMind/
├── backend/                  # Python 后端
│   ├── app/
│   │   ├── core/             # 配置、安全、SM4算法
│   │   ├── protocols/        # HJ212 解析器核心 (Parser, Enums)
│   │   ├── gateway/          # TCP Server
│   │   ├── models/           # Pydantic Models
│   │   ├── api/              # FastAPI Routers
│   │   └── services/         # 业务逻辑 (AI调用, DB操作)
│   ├── main.py
│   └── requirements.txt
├── frontend/                 # Vue 3 前端
│   ├── src/
│   │   ├── api/              # Axios 封装
│   │   ├── components/       # 公共组件 (Chart, Table)
│   │   ├── views/            # 页面 (Dashboard, Report)
│   │   └── stores/           # Pinia 状态
│   └── package.json
└── docker-compose.yml        # 一键启动
```

- **禁止**随意创建新的顶层目录
- **MUST** 将协议相关代码放在 `protocols/` 目录
- **MUST** 将业务逻辑放在 `services/` 目录

**原理**: 清晰的目录结构便于 AI 辅助开发和团队协作，降低代码混乱风险。

### V. 测试与质量 (Testing & Quality)

代码质量 MUST 通过以下检查：

- **MUST** 为协议解析器编写单元测试，覆盖正常报文和异常报文
- **MUST** 为 API 端点编写集成测试
- **SHOULD** 使用 `pytest` 作为测试框架
- **MUST** 在 CI/CD 中运行测试，测试失败则阻止合并

**原理**: 环保数据关系到监管合规，测试确保系统可靠性。

### VI. 简洁性原则 (Simplicity)

开发过程 MUST 遵循简洁性：

- **YAGNI**: 不要实现当前不需要的功能
- **MUST** 从最简单的实现开始，按需迭代
- **禁止**过度设计（over-engineering）
- **SHOULD** 优先使用标准库，减少第三方依赖

**原理**: 简洁的代码更易维护，减少 bug 引入风险。

## 技术栈约束 (Technology Stack Constraints)

本项目技术选型已确定，MUST 严格遵守：

### 后端技术栈
| 组件 | 选型 | 备注 |
|------|------|------|
| Web 框架 | FastAPI | 禁止使用 Django/Flask |
| 异步运行时 | asyncio + uvloop | TCP Gateway 必备 |
| 时序数据库 | TDengine | 存储监测数据 |
| 业务数据库 | PostgreSQL/SQLite | 用户/权限管理 |
| 国密加密 | gmssl | SM4 解密 |
| AI 引擎 | Scikit-learn/XGBoost + LangChain | 预测与 RAG |

### 前端技术栈
| 组件 | 选型 | 备注 |
|------|------|------|
| 框架 | Vue 3 (Composition API) | 禁止使用 Options API |
| 构建工具 | Vite | 禁止使用 Webpack |
| UI 组件库 | Element Plus | 禁止混用其他 UI 库 |
| 图表库 | ECharts 5 | 环保曲线/地图 |
| 状态管理 | Pinia | 禁止使用 Vuex |

## 开发工作流 (Development Workflow)

### 阶段式开发

项目 MUST 按以下阶段推进：

1. **第一阶段：协议核心** - 完成 HJ212 解析器，支持 SM4 解密
2. **第二阶段：数据流转** - TCP Server + TDengine 存储
3. **第三阶段：可视化 MVP** - Vue 3 驾驶舱框架
4. **第四阶段：AI 注入** - 异常检测算法上线

### 代码审查要求

- **MUST** 通过 PR 方式提交代码
- **MUST** 确保 CI 检查通过后才能合并
- **SHOULD** 进行代码审查（如有团队成员）

### 文档要求

- **MUST** 为 API 端点提供 OpenAPI 文档（FastAPI 自动生成）
- **SHOULD** 为复杂业务逻辑添加注释
- **禁止**编写过度冗长的文档

## Governance

### 宪法优先级

本宪法是项目的最高指导原则：

- 本宪法 **优先于** 所有其他开发实践和惯例
- 任何与宪法冲突的代码 MUST 被拒绝
- 复杂性偏离 MUST 在 PR 中明确说明理由

### 修订流程

修订本宪法 MUST 遵循以下流程：

1. 提出修订提案，说明变更内容和理由
2. 更新宪法文档
3. 更新所有受影响的模板文件
4. 记录修订历史

### 版本管理

- **MAJOR**: 原则删除或重新定义（不兼容变更）
- **MINOR**: 新增原则或章节（功能扩展）
- **PATCH**: 措辞修正、错别字修复（文档修正）

### 合规检查

所有 PR/代码审查 MUST 验证：

- [ ] 代码符合协议严格化原则
- [ ] 后端代码通过 mypy 类型检查
- [ ] 前端代码仅使用 Element Plus
- [ ] 文件位于正确的目录结构中
- [ ] 复杂性偏离有合理说明

**Version**: 1.0.0 | **Ratified**: 2025-11-24 | **Last Amended**: 2025-11-24
