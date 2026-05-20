from __future__ import annotations

"""
讯飞星火大模型客户端。

支持两种接入模式：
1. WebSocket（经典模式，wss://spark-api.xf-yun.com/...）
2. HTTP OpenAPI（兼容 OpenAI 风格，https://spark-api-open.xf-yun.com/v1/chat/completions）
"""

import base64
import hashlib
import hmac
import json
import ssl
from datetime import datetime
from time import mktime
from typing import AsyncGenerator
from urllib.parse import urlencode, urlparse
from wsgiref.handlers import format_date_time

import httpx
import structlog
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

logger = structlog.get_logger(__name__)


class SparkClientError(Exception):
    """星火客户端异常基类"""

    pass


class SparkAuthError(SparkClientError):
    """鉴权错误"""

    pass


class SparkConnectionError(SparkClientError):
    """连接错误"""

    pass


class SparkClient:
    """
    讯飞星火大模型 WebSocket 客户端

    使用 HMAC-SHA256 签名算法进行鉴权，支持流式生成。

    Example:
        ```python
        client = SparkClient(
            app_id="your_app_id",
            api_secret="your_api_secret",
            api_key="your_api_key"
        )

        async for chunk in client.chat_stream([
            {"role": "user", "content": "你好"}
        ]):
            print(chunk, end="", flush=True)
        ```
    """

    # 星火模型域名映射
    SPARK_DOMAINS = {
        "generalv3.5": "generalv3.5",  # Spark Max
        "pro-128k": "pro-128k",
        "max": "max",
        "ultra": "ultra",
        "lite": "lite",
    }

    def __init__(
        self,
        app_id: str,
        api_secret: str,
        api_key: str,
        api_password: str | None = None,
        spark_url: str = "wss://spark-api.xf-yun.com/v3.5/chat",
        domain: str = "generalv3.5",
        max_tokens: int = 8192,
        temperature: float = 0.5,
        top_k: int = 4,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        初始化星火客户端

        Args:
            app_id: 讯飞开放平台 APPID
            api_secret: API Secret
            api_key: API Key
            api_password: HTTP OpenAPI 的 APIPassword（可选）
            spark_url: WebSocket 服务地址
            domain: 模型域，如 pro-128k, max, ultra
            max_tokens: 最大生成 token 数
            temperature: 温度参数 (0-1)
            top_k: Top-K 采样参数
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
        """
        self.app_id = app_id
        self.api_secret = api_secret
        self.api_key = api_key
        # HTTP OpenAPI 推荐使用 APIPassword；为空时回退为 APIKey 以兼容旧配置
        self.api_password = api_password or api_key
        self.spark_url = spark_url
        self.domain = domain
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_k = top_k
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # 解析 URL 获取 host
        parsed = urlparse(spark_url)
        self.scheme = (parsed.scheme or "").lower()
        self.is_http_mode = self.scheme in {"http", "https"}
        self.is_ws_mode = self.scheme in {"ws", "wss"}
        self.host = parsed.netloc
        self.path = parsed.path

        if not self.is_http_mode and not self.is_ws_mode:
            raise SparkClientError(
                f"Unsupported Spark URL scheme: {self.scheme!r}. "
                "Expected ws/wss or http/https."
            )

    def _generate_auth_url(self) -> str:
        """
        生成带鉴权参数的 WebSocket URL

        使用 HMAC-SHA256 签名算法，按照讯飞 API 文档要求生成鉴权 URL。

        Returns:
            带鉴权参数的完整 WebSocket URL
        """
        # 生成 RFC1123 格式的时间戳
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        # 构造签名原文
        signature_origin = f"host: {self.host}\ndate: {date}\nGET {self.path} HTTP/1.1"

        # HMAC-SHA256 签名
        signature_sha = hmac.new(
            self.api_secret.encode("utf-8"),
            signature_origin.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        signature_sha_base64 = base64.b64encode(signature_sha).decode("utf-8")

        # 构造 authorization
        authorization_origin = (
            f'api_key="{self.api_key}", '
            f'algorithm="hmac-sha256", '
            f'headers="host date request-line", '
            f'signature="{signature_sha_base64}"'
        )
        authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode(
            "utf-8"
        )

        # 构造完整 URL
        params = {
            "authorization": authorization,
            "date": date,
            "host": self.host,
        }
        auth_url = f"{self.spark_url}?{urlencode(params)}"

        logger.debug("Generated auth URL", url=auth_url[:100] + "...")
        return auth_url

    def _format_messages(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
    ) -> list[dict]:
        """统一整理消息格式。"""
        formatted_messages: list[dict] = []

        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            formatted_messages.append(
                {"role": msg.get("role", "user"), "content": msg.get("content", "")}
            )

        return formatted_messages

    def _build_request_payload(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
    ) -> dict:
        """
        构建请求 JSON 数据

        Args:
            messages: 对话消息列表，格式为 [{"role": "user/assistant", "content": "..."}]
            system_prompt: 系统提示词（可选）

        Returns:
            符合星火 API 格式的请求字典
        """
        formatted_messages = self._format_messages(messages, system_prompt)

        payload = {
            "header": {"app_id": self.app_id, "uid": "ecomind_user"},
            "parameter": {
                "chat": {
                    "domain": self.domain,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                    "top_k": self.top_k,
                }
            },
            "payload": {"message": {"text": formatted_messages}},
        }

        return payload

    def _build_http_payload(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
        stream: bool = False,
    ) -> dict:
        """构建 HTTP OpenAPI 请求体。"""
        return {
            "model": self.domain,
            "messages": self._format_messages(messages, system_prompt),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": stream,
        }

    def _build_http_headers(self) -> dict[str, str]:
        """构建 HTTP OpenAPI 请求头。"""
        if not self.api_password:
            raise SparkAuthError(
                "HTTP OpenAPI requires APIPassword. "
                "Set SPARK_API_PASSWORD (or SPARK_API_KEY as fallback)."
            )
        return {
            "Authorization": f"Bearer {self.api_password}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _extract_http_content(payload: dict) -> str:
        """从 HTTP OpenAPI 响应中提取文本内容。"""
        choices = payload.get("choices") or []
        if not choices:
            return ""

        first = choices[0] if isinstance(choices, list) else {}
        if not isinstance(first, dict):
            return ""

        delta = first.get("delta")
        if isinstance(delta, dict):
            content = delta.get("content")
            if isinstance(content, str):
                return content

        message = first.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str):
                return content

        text = first.get("text")
        if isinstance(text, str):
            return text

        return ""

    async def chat_stream(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        流式生成对话响应

        Args:
            messages: 对话消息列表
            system_prompt: 系统提示词（可选）

        Yields:
            生成的文本片段

        Raises:
            SparkAuthError: 鉴权失败
            SparkConnectionError: 连接失败
            SparkClientError: 其他错误
        """
        if self.is_http_mode:
            async for chunk in self._http_chat_stream(messages, system_prompt):
                yield chunk
            return

        auth_url = self._generate_auth_url()
        request_payload = self._build_request_payload(messages, system_prompt)
        last_error = None
        for attempt in range(self.max_retries):
            yielded_in_attempt = False
            try:
                async for chunk in self._stream_response(auth_url, request_payload):
                    yielded_in_attempt = True
                    yield chunk
                return  # 成功完成，退出重试循环

            except ConnectionClosed as e:
                last_error = e
                if yielded_in_attempt:
                    logger.warning(
                        "WebSocket connection closed after partial output, returning partial response",
                        code=e.code,
                        reason=e.reason,
                    )
                    return
                logger.warning(
                    "WebSocket connection closed",
                    attempt=attempt + 1,
                    max_retries=self.max_retries,
                    code=e.code,
                    reason=e.reason,
                )
                if attempt < self.max_retries - 1:
                    import asyncio

                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    # 重新生成 auth URL（时间戳会变化）
                    auth_url = self._generate_auth_url()

            except WebSocketException as e:
                last_error = e
                if yielded_in_attempt:
                    logger.warning(
                        "WebSocket error after partial output, returning partial response",
                        error=str(e),
                    )
                    return
                logger.error(
                    "WebSocket error",
                    attempt=attempt + 1,
                    error=str(e),
                )
                if attempt < self.max_retries - 1:
                    import asyncio

                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    auth_url = self._generate_auth_url()

            except SparkAuthError:
                # 鉴权错误不重试
                raise

        # 所有重试都失败
        raise SparkConnectionError(
            f"Failed after {self.max_retries} attempts: {last_error}"
        )

    async def _http_chat_stream(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        HTTP OpenAPI 流式对话。
        """
        request_payload = self._build_http_payload(
            messages=messages,
            system_prompt=system_prompt,
            stream=True,
        )
        headers = self._build_http_headers()
        timeout = httpx.Timeout(connect=20.0, read=180.0, write=20.0, pool=20.0)

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    async with client.stream(
                        "POST",
                        self.spark_url,
                        headers=headers,
                        json=request_payload,
                    ) as response:
                        if response.status_code in (401, 403):
                            raise SparkAuthError(
                                f"Auth error [{response.status_code}]: {response.text}"
                            )
                        response.raise_for_status()

                        async for line in response.aiter_lines():
                            if not line:
                                continue

                            # SSE: data: {...}
                            if line.startswith("data:"):
                                data = line[5:].strip()
                            else:
                                data = line.strip()

                            if not data or data == "[DONE]":
                                continue

                            try:
                                payload = json.loads(data)
                            except json.JSONDecodeError:
                                logger.debug("Skip non-json stream line", line=data[:100])
                                continue

                            code = payload.get("code", 0)
                            if code and code != 0:
                                message_text = payload.get("message") or payload.get("msg") or ""
                                if code in [10003, 10004, 10005, 10907, 11200, 11201]:
                                    raise SparkAuthError(f"Auth error [{code}]: {message_text}")
                                raise SparkClientError(f"API error [{code}]: {message_text}")

                            content = self._extract_http_content(payload)
                            if content:
                                yield content
                return
            except SparkAuthError:
                raise
            except Exception as e:
                last_error = e
                logger.warning(
                    "HTTP Spark request failed",
                    attempt=attempt + 1,
                    max_retries=self.max_retries,
                    error=str(e),
                )
                if attempt < self.max_retries - 1:
                    import asyncio

                    await asyncio.sleep(self.retry_delay * (attempt + 1))

        raise SparkConnectionError(
            f"Failed after {self.max_retries} attempts: {last_error}"
        )

    async def _stream_response(
        self,
        auth_url: str,
        request_payload: dict,
    ) -> AsyncGenerator[str, None]:
        """
        内部方法：建立连接并流式接收响应

        Args:
            auth_url: 带鉴权的 WebSocket URL
            request_payload: 请求数据

        Yields:
            生成的文本片段
        """
        # SSL 配置
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        logger.info("Connecting to Spark API", url=self.spark_url)

        async with websockets.connect(
            auth_url,
            ssl=ssl_context,
            ping_interval=30,
            # Some upstream/proxy paths may delay pong frames; disable pong timeout
            # to avoid aborting long report generation mid-stream.
            ping_timeout=None,
            close_timeout=10,
        ) as ws:
            # 发送请求
            await ws.send(json.dumps(request_payload))
            logger.debug("Request sent", payload_keys=list(request_payload.keys()))

            # 接收响应
            async for message in ws:
                try:
                    response = json.loads(message)
                except json.JSONDecodeError as e:
                    logger.error("Failed to parse response", error=str(e))
                    continue

                # 检查响应头
                header = response.get("header", {})
                code = header.get("code", 0)
                message_text = header.get("message", "")

                if code != 0:
                    # 错误处理
                    if code in [10003, 10004, 10005, 10907, 11200, 11201]:
                        raise SparkAuthError(f"Auth error [{code}]: {message_text}")
                    else:
                        raise SparkClientError(f"API error [{code}]: {message_text}")

                # 提取内容
                payload = response.get("payload", {})
                choices = payload.get("choices", {})
                text_list = choices.get("text", [])

                for text_item in text_list:
                    content = text_item.get("content", "")
                    if content:
                        yield content

                # 检查是否结束
                status = choices.get("status", 0)
                if status == 2:
                    # 获取 token 使用统计
                    usage = payload.get("usage", {}).get("text", {})
                    if usage:
                        logger.info(
                            "Generation completed",
                            prompt_tokens=usage.get("prompt_tokens"),
                            completion_tokens=usage.get("completion_tokens"),
                            total_tokens=usage.get("total_tokens"),
                        )
                    break

    async def chat(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
    ) -> str:
        """
        非流式对话（收集所有输出后返回）

        Args:
            messages: 对话消息列表
            system_prompt: 系统提示词（可选）

        Returns:
            完整的生成文本
        """
        if self.is_http_mode:
            request_payload = self._build_http_payload(
                messages=messages,
                system_prompt=system_prompt,
                stream=False,
            )
            headers = self._build_http_headers()
            timeout = httpx.Timeout(connect=20.0, read=180.0, write=20.0, pool=20.0)

            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    self.spark_url,
                    headers=headers,
                    json=request_payload,
                )
                if response.status_code in (401, 403):
                    raise SparkAuthError(
                        f"Auth error [{response.status_code}]: {response.text}"
                    )
                response.raise_for_status()

                payload = response.json()
                code = payload.get("code", 0)
                if code and code != 0:
                    message_text = payload.get("message") or payload.get("msg") or ""
                    if code in [10003, 10004, 10005, 10907, 11200, 11201]:
                        raise SparkAuthError(f"Auth error [{code}]: {message_text}")
                    raise SparkClientError(f"API error [{code}]: {message_text}")

                return self._extract_http_content(payload)

        chunks = []
        async for chunk in self.chat_stream(messages, system_prompt):
            chunks.append(chunk)
        return "".join(chunks)

    async def test_connection(self) -> bool:
        """
        测试连接是否正常

        Returns:
            连接成功返回 True
        """
        try:
            response = await self.chat([{"role": "user", "content": "你好"}])
            logger.info("Connection test passed", response_length=len(response))
            return True
        except Exception as e:
            logger.error("Connection test failed", error=str(e))
            return False
