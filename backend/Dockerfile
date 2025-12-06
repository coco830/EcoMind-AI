FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for TDengine client and Prophet/CmdStan
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libffi-dev \
    curl \
    wget \
    build-essential \
    make \
    && rm -rf /var/lib/apt/lists/*

# Install TDengine client library
# This is required for taospy to work properly
RUN wget -q https://www.tdengine.com/assets-download/3.0/TDengine-client-3.0.7.1-Linux-x64.tar.gz \
    && tar -xzf TDengine-client-3.0.7.1-Linux-x64.tar.gz \
    && cd TDengine-client-3.0.7.1 \
    && ./install_client.sh \
    && cd .. \
    && rm -rf TDengine-client-3.0.7.1 TDengine-client-3.0.7.1-Linux-x64.tar.gz

# Set library path for TDengine
ENV LD_LIBRARY_PATH=/usr/local/taos/driver:$LD_LIBRARY_PATH

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install CmdStan for Prophet (required for time-series forecasting)
RUN python -c "import cmdstanpy; cmdstanpy.install_cmdstan()" || echo "CmdStan install failed, fallback prediction will be used"

# Copy application code
COPY . .

# Expose ports (API and TCP Gateway)
EXPOSE 8000 9880

# Run application
# Enable --proxy-headers so FastAPI/Starlette respects X-Forwarded-Proto from the HTTPS ingress
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
