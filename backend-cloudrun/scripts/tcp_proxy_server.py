#!/usr/bin/env python3
import asyncio, os, sys, signal, logging, base64
from datetime import datetime
import aiohttp

TCP_HOST = "0.0.0.0"
TCP_PORT = int(os.getenv("TCP_PORT", "9999"))
CLOUDBASE_API_URL = os.getenv("CLOUDBASE_API_URL", "https://ecomind-ai-193380-4-1304218020.sh.run.tcloudbase.com")
GATEWAY_API_KEY = os.getenv("GATEWAY_API_KEY", "")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class TCPToHTTPProxy:
    def __init__(self):
        self.server = None
        self._running = False
        self._session = None
    async def start(self):
        self._running = True
        self._session = aiohttp.ClientSession()
        self.server = await asyncio.start_server(self._handle, TCP_HOST, TCP_PORT)
        logger.info(f"TCP Proxy 已启动 {TCP_HOST}:{TCP_PORT}")
        async with self.server: await self.server.serve_forever()
    async def _handle(self, reader, writer):
        addr = writer.get_extra_info("peername")
        logger.info(f"设备连接: {addr}")
        try:
            while self._running:
                data = await asyncio.wait_for(reader.read(4096), timeout=300)
                if not data: break
                raw = data.decode("utf-8", errors="ignore")
                logger.info(f"收到: {raw[:80]}...")
                url = f"{CLOUDBASE_API_URL}/api/v1/gateway/hj212"
                headers = {"Content-Type": "application/json", "X-Gateway-Key": GATEWAY_API_KEY}
                payload = {"raw_data": raw, "raw_data_base64": base64.b64encode(data).decode("ascii"), "source_ip": addr[0]}
                async with self._session.post(url, json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        device_mn = result.get("device_mn")
                        logger.info(f"转发成功: {device_mn}")
                        resp_pkt = result.get("response_packet")
                        if resp_pkt:
                            writer.write(resp_pkt.encode())
                            await writer.drain()
                    else: logger.error(f"转发失败: {resp.status}")
        except Exception as e: logger.error(f"错误: {e}")
        finally: writer.close()

if __name__ == "__main__":
    print("TCP Proxy 启动中... 端口:", TCP_PORT)
    asyncio.run(TCPToHTTPProxy().start())
