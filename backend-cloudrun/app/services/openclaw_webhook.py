"""OpenClaw webhook push notifier for active alarm delivery."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import httpx
import structlog

from app.core.config import get_settings
from app.models.alarm import Alarm, AlarmLevel, AlarmType
from app.models.device import Device

logger = structlog.get_logger()


class OpenClawWebhookNotifier:
    """Push alarms to OpenClaw Gateway webhook with retry and in-memory dedup."""

    _LEVEL_ORDER = {
        AlarmLevel.INFO.value: 0,
        AlarmLevel.WARNING.value: 1,
        AlarmLevel.CRITICAL.value: 2,
    }

    def __init__(self) -> None:
        self.settings = get_settings()
        self._sent_dedup: dict[str, datetime] = {}
        self._lock = asyncio.Lock()
        self._misconfigured_warned = False

    @property
    def enabled(self) -> bool:
        if not self.settings.openclaw_webhook_enabled:
            return False
        if self.settings.openclaw_webhook_url and self.settings.openclaw_webhook_token:
            return True
        if not self._misconfigured_warned:
            logger.warning(
                "OpenClaw webhook enabled but missing url/token",
                url_set=bool(self.settings.openclaw_webhook_url),
                token_set=bool(self.settings.openclaw_webhook_token),
            )
            self._misconfigured_warned = True
        return False

    def _is_level_allowed(self, level: str) -> bool:
        min_level = (self.settings.openclaw_webhook_min_level or AlarmLevel.WARNING.value).lower()
        return self._LEVEL_ORDER.get(level, 0) >= self._LEVEL_ORDER.get(min_level, 1)

    def _build_dedup_key(self, alarm: Alarm, device: Device | None) -> str:
        org_id = str(getattr(device, "org_id", "") or "unknown-org")
        device_id = str(alarm.device_id)
        alarm_type = alarm.alarm_type or "unknown"
        pollutant_code = alarm.pollutant_code or "-"
        level = alarm.level or AlarmLevel.WARNING.value
        return f"{org_id}:{device_id}:{alarm_type}:{pollutant_code}:{level}"

    async def _should_skip_by_dedup(self, dedup_key: str) -> bool:
        window = timedelta(minutes=max(1, int(self.settings.openclaw_webhook_dedup_minutes)))
        now = datetime.utcnow()

        async with self._lock:
            for key, ts in list(self._sent_dedup.items()):
                if now - ts > window:
                    self._sent_dedup.pop(key, None)

            last = self._sent_dedup.get(dedup_key)
            return bool(last and now - last < window)

    async def _mark_sent(self, dedup_key: str) -> None:
        async with self._lock:
            self._sent_dedup[dedup_key] = datetime.utcnow()

    def _build_payload(self, alarm: Alarm, device: Device | None) -> dict:
        org_name = (
            getattr(getattr(device, "organization", None), "name", None)
            or "未知企业"
        )
        device_name = getattr(device, "name", None) or "未知设备"
        device_mn = getattr(device, "mn", None) or "-"
        alarm_type_label = {
            AlarmType.THRESHOLD.value: "阈值超标",
            AlarmType.ANOMALY.value: "AI 异常",
            AlarmType.OFFLINE.value: "设备离线",
            AlarmType.FLAG.value: "数据标记异常",
        }.get(alarm.alarm_type, alarm.alarm_type)
        level_label = {
            AlarmLevel.INFO.value: "信息",
            AlarmLevel.WARNING.value: "预警",
            AlarmLevel.CRITICAL.value: "严重",
        }.get(alarm.level, alarm.level)

        message_lines = [
            "EcoMind 实时报警",
            f"企业: {org_name}",
            f"设备: {device_name} ({device_mn})",
            f"类型: {alarm_type_label}",
            f"级别: {level_label}",
        ]
        if alarm.pollutant_code:
            message_lines.append(f"污染物: {alarm.pollutant_code}")
        if alarm.value:
            message_lines.append(f"当前值: {alarm.value}")
        if alarm.threshold:
            message_lines.append(f"阈值/参考: {alarm.threshold}")
        message_lines.extend(
            [
                f"时间: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}",
                f"报警ID: {alarm.id}",
            ]
        )

        text = "\n".join(message_lines)
        if len(text) > self.settings.openclaw_webhook_max_text_length:
            text = text[: self.settings.openclaw_webhook_max_text_length] + "..."

        payload = {
            "text": text,
            "mode": self.settings.openclaw_webhook_mode,
            "thinking": self.settings.openclaw_webhook_thinking,
        }
        if self.settings.openclaw_webhook_channel:
            payload["channel"] = self.settings.openclaw_webhook_channel
        if self.settings.openclaw_webhook_sender_name:
            payload["name"] = self.settings.openclaw_webhook_sender_name
        return payload

    async def notify_alarm(self, alarm: Alarm, device: Device | None = None) -> bool:
        """Push alarm to OpenClaw webhook.

        Returns True when webhook accepted the message.
        """
        if not self.enabled:
            return False

        if not self._is_level_allowed(alarm.level):
            return False

        dedup_key = self._build_dedup_key(alarm, device)
        if await self._should_skip_by_dedup(dedup_key):
            logger.info("OpenClaw webhook skipped by dedup", dedup_key=dedup_key)
            return False

        payload = self._build_payload(alarm, device)
        headers = {
            "Authorization": f"Bearer {self.settings.openclaw_webhook_token}",
            "Content-Type": "application/json",
        }

        retries = max(1, int(self.settings.openclaw_webhook_retry_times))
        timeout = max(1.0, float(self.settings.openclaw_webhook_timeout_seconds))
        base_delay = max(0.1, float(self.settings.openclaw_webhook_retry_base_delay_seconds))

        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        self.settings.openclaw_webhook_url,
                        json=payload,
                        headers=headers,
                    )
                if 200 <= response.status_code < 300:
                    await self._mark_sent(dedup_key)
                    logger.info(
                        "OpenClaw webhook push succeeded",
                        alarm_id=str(alarm.id),
                        status_code=response.status_code,
                        attempt=attempt + 1,
                    )
                    return True

                logger.warning(
                    "OpenClaw webhook push failed",
                    alarm_id=str(alarm.id),
                    status_code=response.status_code,
                    response=response.text[:300],
                    attempt=attempt + 1,
                )
            except httpx.HTTPError as exc:
                logger.warning(
                    "OpenClaw webhook request error",
                    alarm_id=str(alarm.id),
                    error=str(exc),
                    attempt=attempt + 1,
                )

            if attempt < retries - 1:
                await asyncio.sleep(base_delay * (2**attempt))

        logger.error("OpenClaw webhook push exhausted retries", alarm_id=str(alarm.id))
        return False


_openclaw_webhook_notifier: OpenClawWebhookNotifier | None = None


def get_openclaw_webhook_notifier() -> OpenClawWebhookNotifier:
    """Return singleton OpenClaw webhook notifier."""
    global _openclaw_webhook_notifier
    if _openclaw_webhook_notifier is None:
        _openclaw_webhook_notifier = OpenClawWebhookNotifier()
    return _openclaw_webhook_notifier

