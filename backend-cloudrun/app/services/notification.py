"""Notification utilities (Tencent Cloud SMS)."""

from __future__ import annotations

import asyncio
from typing import Sequence

import structlog

from app.core.config import get_settings

logger = structlog.get_logger()


class TencentSMSNotifier:
    """Simple wrapper around Tencent Cloud SMS SDK with mock fallback."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = None
        self._lock = asyncio.Lock()

    @property
    def is_configured(self) -> bool:
        """Whether SMS capability is fully configured."""
        return all(
            (
                self.settings.tencent_secret_id,
                self.settings.tencent_secret_key,
                self.settings.tencent_sms_sdk_app_id,
                self.settings.tencent_sms_sign_name,
                self.settings.tencent_sms_template_id,
            )
        )

    async def send_sms(self, phones: Sequence[str], params: Sequence[str]) -> bool:
        """Send SMS using Tencent Cloud; logs only when not configured."""
        filtered = [self._format_phone(p) for p in phones if p]
        if not filtered:
            logger.warning("SMS skipped - no phone numbers provided")
            return False

        if not self.is_configured:
            logger.info(
                "SMS mock send (Tencent config missing)",
                phones=filtered,
                params=list(params),
            )
            return True

        try:
            response = await asyncio.to_thread(self._send_sms_sync, filtered, list(params))
            logger.info(
                "Tencent SMS sent",
                phones=filtered,
                response=response,
            )
            return True
        except Exception as exc:  # pragma: no cover - network errors
            logger.error("Tencent SMS failed", error=str(exc))
            return False

    def _send_sms_sync(self, phones: list[str], params: list[str]) -> dict:
        """Blocking send; executed in thread pool."""
        from tencentcloud.common import credential
        from tencentcloud.common.profile.client_profile import ClientProfile
        from tencentcloud.common.profile.http_profile import HttpProfile
        from tencentcloud.sms.v20210111 import sms_client, models

        if self._client is None:
            cred = credential.Credential(
                self.settings.tencent_secret_id,
                self.settings.tencent_secret_key,
            )
            http_profile = HttpProfile()
            http_profile.endpoint = "sms.tencentcloudapi.com"
            client_profile = ClientProfile()
            client_profile.httpProfile = http_profile
            self._client = sms_client.SmsClient(
                cred,
                "ap-guangzhou",
                client_profile,
            )

        req = models.SendSmsRequest()
        req.SmsSdkAppId = self.settings.tencent_sms_sdk_app_id
        req.SignName = self.settings.tencent_sms_sign_name
        req.TemplateId = self.settings.tencent_sms_template_id
        req.PhoneNumberSet = phones
        req.TemplateParamSet = params

        resp = self._client.SendSms(req)
        return resp.to_json_string()

    @staticmethod
    def _format_phone(phone: str) -> str:
        """Ensure phone number is in +86XXXXXXXX format."""
        phone = phone.strip()
        if phone.startswith("+"):
            return phone
        if phone.startswith("86"):
            return f"+{phone}"
        return f"+86{phone}"
