# EcoMind-AI 生产部署指南

## 部署架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户浏览器                                │
└─────────────────────────────────────────────────────────────────┘
                    │                           │
                    │ HTTPS                     │ HTTPS
                    ▼                           ▼
┌─────────────────────────────┐   ┌─────────────────────────────┐
│   腾讯云 CloudBase          │   │   腾讯云 CVM                │
│   (静态托管)                │   │                             │
│                             │   │   ┌─────────────────────┐   │
│   ┌─────────────────────┐   │   │   │  Nginx (443/80)     │   │
│   │  Vue 3 前端         │   │   │   │  SSL 终结          │   │
│   │  (dist/)            │   │   │   └──────────┬──────────┘   │
│   └─────────────────────┘   │   │              │              │
│                             │   │              ▼              │
│   域名:                     │   │   ┌─────────────────────┐   │
│   xxx.tcloudbaseapp.com     │   │   │  FastAPI (8000)     │   │
│   或 your-domain.com        │   │   │  Backend API        │   │
└─────────────────────────────┘   │   └──────────┬──────────┘   │
                                  │              │              │
        API 请求                  │              ▼              │
        ──────────────────────────┤   ┌─────────────────────┐   │
                                  │   │  PostgreSQL (5432)  │   │
                                  │   │  TDengine (6030)    │   │
                                  │   └─────────────────────┘   │
                                  └─────────────────────────────┘
```

## 一、准备工作

### 1.1 目录结构

```
deploy/
├── nginx/
│   └── nginx.conf        # Nginx 配置文件
├── certs/
│   ├── api.crt          # SSL 证书
│   └── api.key          # SSL 私钥
├── certbot/
│   └── www/             # Let's Encrypt 验证目录
└── README.md            # 本文档
```

### 1.2 SSL 证书准备

**方式一：腾讯云免费证书**
1. 登录腾讯云控制台 → SSL 证书 → 申请免费证书
2. 下载 Nginx 格式证书
3. 上传到服务器 `deploy/certs/` 目录

```bash
# 上传证书
scp api.crt api.key user@your-server:/path/to/EcoMind-AI/deploy/certs/
```

**方式二：Let's Encrypt (免费自动续期)**
```bash
# 安装 certbot
apt-get update && apt-get install certbot

# 获取证书 (需要先停止 Nginx)
certbot certonly --standalone -d api.yourdomain.com

# 证书路径
# /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem
# /etc/letsencrypt/live/api.yourdomain.com/privkey.pem

# 创建软链接
ln -s /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem /path/to/deploy/certs/api.crt
ln -s /etc/letsencrypt/live/api.yourdomain.com/privkey.pem /path/to/deploy/certs/api.key
```

## 二、环境配置

### 2.1 配置环境变量

```bash
# 复制环境变量模板
cp .env.production.example .env

# 编辑配置
nano .env
```

**必须配置的变量：**

| 变量 | 说明 | 生成命令 |
|------|------|----------|
| `POSTGRES_PASSWORD` | PostgreSQL 密码 | `openssl rand -base64 24` |
| `JWT_SECRET` | JWT 签名密钥 | `openssl rand -base64 48` |
| `SM4_KEY` | SM4 加密密钥 | `openssl rand -hex 16` |
| `ALLOWED_ORIGINS` | **前端域名 (CORS)** | 手动填写 |

### 2.2 CORS 配置 (重要!)

在 `.env` 文件中配置 `ALLOWED_ORIGINS`：

```bash
# 单个域名
ALLOWED_ORIGINS=https://your-site.tcloudbaseapp.com

# 多个域名 (逗号分隔)
ALLOWED_ORIGINS=https://xxx.tcloudbaseapp.com,https://your-custom-domain.com
```

**注意事项：**
- 必须使用 HTTPS 协议
- 不要加末尾斜杠
- CloudBase 分配的域名格式: `https://xxx-xxxxxxx.tcloudbaseapp.com`

## 三、部署步骤

### 3.1 上传代码

```bash
# 克隆代码到服务器
git clone https://github.com/your-repo/EcoMind-AI.git
cd EcoMind-AI

# 或使用 rsync 同步
rsync -avz --exclude 'node_modules' --exclude '.venv' --exclude '__pycache__' \
    ./ user@your-server:/path/to/EcoMind-AI/
```

### 3.2 启动服务

```bash
# 构建并启动
docker-compose -f docker-compose.prod.yml up -d --build

# 查看状态
docker-compose -f docker-compose.prod.yml ps

# 查看日志
docker-compose -f docker-compose.prod.yml logs -f backend
docker-compose -f docker-compose.prod.yml logs -f nginx
```

### 3.3 验证部署

```bash
# 检查 HTTPS
curl -v https://api.yourdomain.com/health

# 检查 API
curl https://api.yourdomain.com/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username": "admin", "password": "admin123"}'
```

## 四、常用运维命令

```bash
# 重启服务
docker-compose -f docker-compose.prod.yml restart backend

# 查看日志
docker-compose -f docker-compose.prod.yml logs -f --tail=100 backend

# 进入容器
docker exec -it ecomind-backend bash

# 更新代码后重新部署
git pull
docker-compose -f docker-compose.prod.yml up -d --build backend

# 查看资源使用
docker stats
```

## 五、SSL 证书续期

### Let's Encrypt 自动续期

```bash
# 添加 crontab
crontab -e

# 每月 1 日凌晨 3 点续期
0 3 1 * * certbot renew --quiet && docker-compose -f /path/to/docker-compose.prod.yml restart nginx
```

## 六、故障排查

### 问题：CORS 错误

浏览器控制台显示：
```
Access to XMLHttpRequest has been blocked by CORS policy
```

**解决方案：**
1. 检查 `.env` 中的 `ALLOWED_ORIGINS` 是否包含前端域名
2. 确保域名格式正确（包含 `https://`，不含末尾 `/`）
3. 重启后端服务：`docker-compose -f docker-compose.prod.yml restart backend`

### 问题：502 Bad Gateway

**解决方案：**
```bash
# 检查后端服务状态
docker-compose -f docker-compose.prod.yml ps
docker-compose -f docker-compose.prod.yml logs backend

# 检查网络
docker network ls
docker network inspect ecomind-ai_ecomind-network
```

### 问题：SSL 证书错误

**解决方案：**
```bash
# 检查证书文件
ls -la deploy/certs/

# 验证证书
openssl x509 -in deploy/certs/api.crt -text -noout

# 检查 Nginx 配置
docker exec ecomind-nginx nginx -t
```
