# EcoMind-AI Backend - CloudBase Cloud Run Dockerfile
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件（使用云托管精简版依赖）
COPY requirements-cloudbase.txt requirements.txt

# 安装 Python 依赖（使用腾讯云镜像加速）
RUN pip install --no-cache-dir -i https://mirrors.cloud.tencent.com/pypi/simple/ -r requirements.txt

# 复制应用代码
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY scripts/ ./scripts/

# 暴露端口
EXPOSE 8000

# 启动命令
# 注意开启 --proxy-headers 以识别反向代理传递的 X-Forwarded-Proto，从而避免 HTTPS 环境下重定向到 HTTP
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
