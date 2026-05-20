#!/usr/bin/env python3
"""TCP to HTTP Proxy for HJ212 Protocol.

这个脚本运行在你的腾讯云服务器上，作为设备连接的入口。
它接收设备的 TCP 连接，将 HJ212 数据转发到云托管的 HTTP 接口。

使用方法:
    1. 将此脚本放到你的服务器上
    2. 配置环境变量或修改下面的配置
    3. 运行: python3 tcp_to_http_proxy.py

环境变量:
    TCP_PORT: 监听的 TCP 端口 (默认 9999)
    CLOUDBASE_API_URL: 云托管 API 地址
    GATEWAY_API_KEY: Gateway API 密钥

作者: EcoMind-AI
"""

import asyncio
import base64
import os
import sys
import signal
import logging
from datetime import datetime
from typing import Optional

# 第三方依赖，需要安装: pip install aiohttp
try:
    import aiohttp
except ImportError:
    print("请安装 aiohttp: pip3 install aiohttp")
    sys.exit(1)

# ============ 配置部分 - 请根据实际情况修改 ============

# TCP 服务器配置
TCP_HOST = "0.0.0.0"
TCP_PORT = int(os.getenv("TCP_PORT", "9999"))

# 云托管 API 配置
CLOUDBASE_API_URL = os.getenv(
    "CLOUDBASE_API_URL",
    "https://ecomind-backend-xxxxxx.ap-shanghai.run.tcloudbase.com"  # 替换为实际地址
)
GATEWAY_API_KEY = os.getenv("GATEWAY_API_KEY", "ecomind-gateway-key-2024")

# 超时配置
CONNECTION_TIMEOUT = 300  # 连接超时 5 分钟
HTTP_TIMEOUT = 30  # HTTP 请求超时

# ============ 配置部分结束 ============

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("tcp_proxy.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger(__name__)


class TCPToHTTPProxy:
    """TCP to HTTP 转发代理"""

    def __init__(self):
        self.server: Optional[asyncio.Server] = None
        self.connections: dict[str, asyncio.StreamWriter] = {}
        self._running = False
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self):
        """启动 TCP 服务器"""
        self._running = True
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
        )

        self.server = await asyncio.start_server(
            self._handle_connection,
            TCP_HOST,
            TCP_PORT,
        )

        logger.info(f"TCP Proxy 已启动，监听 {TCP_HOST}:{TCP_PORT}")
        logger.info(f"转发目标: {CLOUDBASE_API_URL}/api/v1/gateway/hj212")

        async with self.server:
            await self.server.serve_forever()

    async def stop(self):
        """停止服务器"""
        self._running = False
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        if self._session:
            await self._session.close()
        logger.info("TCP Proxy 已停止")

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        """处理设备 TCP 连接"""
        addr = writer.get_extra_info("peername")
        conn_id = f"{addr[0]}:{addr[1]}"
        logger.info(f"设备连接: {conn_id}")

        self.connections[conn_id] = writer

        try:
            while self._running:
                # 读取数据
                try:
                    data = await asyncio.wait_for(
                        reader.read(4096),
                        timeout=CONNECTION_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"连接超时: {conn_id}")
                    break

                if not data:
                    logger.info(f"设备断开连接: {conn_id}")
                    break

                # 转发到云托管
                raw_data = data.decode("utf-8", errors="ignore")
                logger.debug(f"收到数据 ({conn_id}): {raw_data[:100]}...")

                response = await self._forward_to_cloudbase(raw_data, data, addr[0])

                # 如果有响应包，回传给设备
                if response and response.get("response_packet"):
                    response_data = response["response_packet"].encode("utf-8")
                    writer.write(response_data)
                    await writer.drain()
                    logger.debug(f"已回传响应 ({conn_id})")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"连接处理错误 ({conn_id}): {e}")
        finally:
            # 清理连接
            if conn_id in self.connections:
                del self.connections[conn_id]
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            logger.info(f"连接已关闭: {conn_id}")

    async def _forward_to_cloudbase(
        self,
        raw_data: str,
        raw_bytes: bytes,
        source_ip: str,
    ) -> Optional[dict]:
        """将数据转发到云托管 HTTP 接口"""
        if not self._session:
            return None

        url = f"{CLOUDBASE_API_URL}/api/v1/gateway/hj212"
        headers = {
            "Content-Type": "application/json",
            "X-Gateway-Key": GATEWAY_API_KEY,
        }
        payload = {
            "raw_data": raw_data,
            "raw_data_base64": base64.b64encode(raw_bytes).decode("ascii"),
            "source_ip": source_ip,
            "received_at": datetime.utcnow().isoformat(),
        }

        try:
            async with self._session.post(url, json=payload, headers=headers) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    logger.info(
                        f"数据转发成功: device={result.get('device_mn')}, "
                        f"pollutants={result.get('pollutant_count')}"
                    )
                    return result
                else:
                    error_text = await resp.text()
                    logger.error(f"转发失败 (HTTP {resp.status}): {error_text[:200]}")
                    return None

        except aiohttp.ClientError as e:
            logger.error(f"HTTP 请求失败: {e}")
            return None
        except Exception as e:
            logger.error(f"转发异常: {e}")
            return None


async def main():
    """主函数"""
    proxy = TCPToHTTPProxy()

    # 处理信号
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(proxy.stop()))

    try:
        await proxy.start()
    except asyncio.CancelledError:
        pass
    finally:
        await proxy.stop()


if __name__ == "__main__":
    print("=" * 60)
    print("EcoMind-AI TCP to HTTP Proxy")
    print("=" * 60)
    print(f"TCP 端口: {TCP_PORT}")
    print(f"云托管 URL: {CLOUDBASE_API_URL}")
    print("=" * 60)

    # 检查配置
    if "xxxxxx" in CLOUDBASE_API_URL:
        print("\n[警告] 请配置正确的 CLOUDBASE_API_URL!")
        print("设置环境变量: export CLOUDBASE_API_URL=https://your-actual-url")
        print()

    asyncio.run(main())
