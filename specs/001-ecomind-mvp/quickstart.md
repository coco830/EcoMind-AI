# Quickstart: EcoMind-AI 智慧环保 SaaS 平台

本指南帮助你快速启动 EcoMind-AI 开发环境。

## 前置要求

- **Python**: 3.11+
- **Node.js**: 18+
- **Docker**: 20.10+ (含 Docker Compose)
- **Git**: 2.30+

## 1. 克隆项目

```bash
git clone <repository-url>
cd EcoMind-AI
```

## 2. 启动基础服务

使用 Docker Compose 启动 TDengine 和 PostgreSQL：

```bash
docker-compose up -d tdengine postgres
```

验证服务状态：

```bash
docker-compose ps
# 应该看到 tdengine 和 postgres 状态为 "Up"
```

## 3. 后端设置

### 3.1 创建虚拟环境

```bash
cd backend
python -m venv venv

# Linux/macOS
source venv/bin/activate

# Windows
.\venv\Scripts\activate
```

### 3.2 安装依赖

```bash
pip install -r requirements.txt
```

### 3.3 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
# 数据库配置
TDENGINE_HOST=localhost
TDENGINE_PORT=6030
TDENGINE_USER=root
TDENGINE_PASSWORD=taosdata

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=ecomind
POSTGRES_USER=ecomind
POSTGRES_PASSWORD=your_password

# TCP Gateway
GATEWAY_HOST=0.0.0.0
GATEWAY_PORT=9999

# JWT 配置
JWT_SECRET=your-secret-key-change-in-production
JWT_EXPIRE_HOURS=24

# SM4 默认密钥 (可选)
SM4_DEFAULT_KEY=
```

### 3.4 初始化数据库

```bash
# 运行数据库迁移
python -m app.db.init

# 创建默认管理员账户
python -m app.db.seed
```

### 3.5 启动后端服务

```bash
# 启动 API 服务 (默认端口 8000)
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 在另一个终端启动 TCP Gateway (默认端口 9999)
python -m app.gateway.server
```

验证 API 服务：

```bash
curl http://localhost:8000/docs
# 应该返回 OpenAPI 文档页面
```

## 4. 前端设置

### 4.1 安装依赖

```bash
cd frontend
npm install
```

### 4.2 配置环境变量

```bash
cp .env.example .env.local
```

编辑 `.env.local`：

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
```

### 4.3 启动开发服务器

```bash
npm run dev
```

访问 http://localhost:3000，使用默认账户登录：
- 用户名: `admin`
- 密码: `admin123`

## 5. 一键启动 (Docker)

如果不想单独配置，可以使用 Docker Compose 一键启动全部服务：

```bash
docker-compose up -d
```

服务访问地址：
- **前端**: http://localhost:3000
- **后端 API**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs
- **TCP Gateway**: localhost:9999

## 6. 验证安装

### 6.1 测试 TCP Gateway

使用测试脚本发送模拟 HJ212 报文：

```bash
cd backend
python -m tests.tools.send_test_packet
```

预期输出：

```
[INFO] Connected to gateway at localhost:9999
[INFO] Sent HJ212 packet: QN=20251124120000001;ST=32;CN=2011;...
[INFO] Received response: ##0051QN=20251124120000001;ST=32;CN=9011;...
```

### 6.2 检查数据写入

```bash
# 连接 TDengine
docker exec -it tdengine taos

# 查询最新数据
taos> use ecomind;
taos> select * from monitoring_data limit 10;
```

### 6.3 运行测试

```bash
# 后端测试
cd backend
pytest

# 前端测试
cd frontend
npm run test
```

## 7. 常见问题

### Q: TDengine 连接失败

检查 Docker 容器状态和端口映射：

```bash
docker-compose logs tdengine
netstat -tlnp | grep 6030
```

### Q: 前端无法连接后端 API

1. 确认后端服务正在运行
2. 检查 CORS 配置（`backend/app/core/config.py`）
3. 确认 `.env.local` 中的 API 地址正确

### Q: TCP Gateway 无法接收数据

1. 检查端口 9999 是否被占用
2. 确认防火墙规则允许入站连接
3. 查看 Gateway 日志输出

## 8. 开发工作流

### 后端开发

```bash
cd backend

# 代码格式化
black .

# 类型检查
mypy app/

# 运行特定测试
pytest tests/unit/test_parser.py -v
```

### 前端开发

```bash
cd frontend

# 代码格式化
npm run format

# 代码检查
npm run lint

# 构建生产版本
npm run build
```

## 9. 项目结构参考

```
EcoMind-AI/
├── backend/
│   ├── app/
│   │   ├── core/          # 配置、安全
│   │   ├── protocols/     # HJ212 解析器
│   │   ├── gateway/       # TCP Server
│   │   ├── models/        # Pydantic Models
│   │   ├── api/           # FastAPI Routers
│   │   └── services/      # 业务逻辑
│   ├── tests/
│   ├── main.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/           # API 封装
│   │   ├── components/    # 组件
│   │   ├── views/         # 页面
│   │   └── stores/        # 状态管理
│   └── package.json
├── docker-compose.yml
└── specs/                 # 规格文档
```

## 下一步

1. 阅读 [spec.md](./spec.md) 了解功能需求
2. 阅读 [data-model.md](./data-model.md) 了解数据结构
3. 查看 [contracts/](./contracts/) 了解 API 接口定义
4. 开始实现 Phase 1 任务（参考 tasks.md）
