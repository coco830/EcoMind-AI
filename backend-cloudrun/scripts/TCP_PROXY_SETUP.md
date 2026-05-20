# TCP 转发代理部署指南

## 架构说明

```
设备 (HJ212/TCP)
      │
      │ TCP:9999
      ▼
┌─────────────────────┐
│  腾讯云服务器        │
│  TCP to HTTP Proxy  │
│  (tcp_to_http_proxy.py) │
└─────────────────────┘
      │
      │ HTTPS
      ▼
┌─────────────────────┐
│  CloudBase 云托管    │
│  /api/v1/gateway/hj212 │
└─────────────────────┘
```

## 部署步骤

### 1. 安装依赖

```bash
# 确保 Python 3.8+
python3 --version

# 安装 aiohttp
pip3 install aiohttp
```

### 2. 上传脚本

将 `tcp_to_http_proxy.py` 上传到服务器：

```bash
# 创建目录
mkdir -p /opt/ecomind

# 上传脚本（从本地）
scp tcp_to_http_proxy.py root@your-server:/opt/ecomind/
```

### 3. 配置环境变量

编辑脚本或设置环境变量：

```bash
# 云托管地址（替换为实际地址）
export CLOUDBASE_API_URL="https://your-cloudbase-url.run.tcloudbase.com"

# Gateway API Key（与后端配置保持一致）
export GATEWAY_API_KEY="your_gateway_api_key_here"

# TCP 监听端口
export TCP_PORT=9999
```

### 4. 测试运行

```bash
cd /opt/ecomind
python3 tcp_to_http_proxy.py
```

### 5. 配置 Systemd 服务

```bash
# 复制服务文件
sudo cp ecomind-tcp-proxy.service /etc/systemd/system/

# 编辑配置（修改 CLOUDBASE_API_URL）
sudo nano /etc/systemd/system/ecomind-tcp-proxy.service

# 重载配置
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start ecomind-tcp-proxy

# 设置开机自启
sudo systemctl enable ecomind-tcp-proxy

# 查看状态
sudo systemctl status ecomind-tcp-proxy

# 查看日志
sudo journalctl -u ecomind-tcp-proxy -f
```

### 6. 防火墙配置

```bash
# 开放 9999 端口
sudo ufw allow 9999/tcp

# 或使用 firewalld
sudo firewall-cmd --zone=public --add-port=9999/tcp --permanent
sudo firewall-cmd --reload
```

## 环境变量说明

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| TCP_PORT | 9999 | TCP 监听端口 |
| CLOUDBASE_API_URL | - | 云托管 API 地址 |
| GATEWAY_API_KEY | - | 网关认证密钥（必须设置） |

## 日志查看

```bash
# 查看日志文件
tail -f /opt/ecomind/tcp_proxy.log

# 或使用 journalctl
sudo journalctl -u ecomind-tcp-proxy -f
```

## 故障排查

### 连接超时
- 检查防火墙是否开放 9999 端口
- 检查云托管服务是否正常运行

### 转发失败
- 检查 CLOUDBASE_API_URL 是否正确
- 检查 GATEWAY_API_KEY 是否与后端配置一致
- 查看云托管日志确认请求是否到达

### 设备无法连接
- 确认服务器公网 IP 配置正确
- 检查设备网络连通性
