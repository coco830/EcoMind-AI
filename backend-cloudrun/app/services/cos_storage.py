from __future__ import annotations

"""Tencent Cloud COS storage helpers.

This module is intentionally lightweight and only provides the subset we need:
- Upload self-inspection report source files to COS (CloudBase storage bucket)
- Return a stable object key/URI for DB persistence

We store objects as PRIVATE by default and avoid generating public URLs.
"""

import os
import re
from dataclasses import dataclass
from typing import Optional
from uuid import uuid4

import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)


def _sanitize_filename(filename: str) -> str:
    name = os.path.basename(filename or "").strip()
    if not name:
        return "report"
    # Replace unsafe characters
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    # Avoid extremely long keys
    return name[:120] or "report"


def _normalize_prefix(prefix: str) -> str:
    p = (prefix or "").strip()
    if not p:
        return ""
    p = p.lstrip("/")
    if not p.endswith("/"):
        p += "/"
    return p


@dataclass(frozen=True)
class CosObject:
    bucket: str
    key: str

    @property
    def uri(self) -> str:
        return f"cos://{self.bucket}/{self.key}"


class CosStorage:
    """Minimal COS client wrapper for uploading objects."""

    def __init__(
        self,
        *,
        secret_id: str,
        secret_key: str,
        region: str,
        bucket: str,
        prefix: str,
        session_token: str = "",
    ) -> None:
        from qcloud_cos import CosConfig, CosS3Client  # lazy import

        self.bucket = bucket
        self.prefix = _normalize_prefix(prefix)

        config = CosConfig(
            Region=region,
            SecretId=secret_id,
            SecretKey=secret_key,
            Token=session_token or None,
            Scheme="https",
        )
        self._client = CosS3Client(config)

    def build_key(self, *, org_id: str, filename: str) -> str:
        safe_name = _sanitize_filename(filename)
        return f"{self.prefix}{org_id}/{uuid4()}-{safe_name}"

    def put_bytes(
        self,
        *,
        key: str,
        body: bytes,
        content_type: str = "application/octet-stream",
        content_disposition_filename: Optional[str] = None,
    ) -> CosObject:
        params = {
            "Bucket": self.bucket,
            "Key": key,
            "Body": body,
            "ContentType": content_type,
            "ACL": "private",
        }
        if content_disposition_filename:
            safe_name = _sanitize_filename(content_disposition_filename)
            params["ContentDisposition"] = f'attachment; filename="{safe_name}"'

        self._client.put_object(**params)
        return CosObject(bucket=self.bucket, key=key)


def get_cos_storage() -> Optional[CosStorage]:
    """Return a configured COS storage client, or None if not configured."""
    settings = get_settings()

    if not (
        settings.cos_secret_id
        and settings.cos_secret_key
        and settings.cos_region
        and settings.cos_bucket
        and settings.cos_prefix
    ):
        logger.warning("COS config missing; file archival disabled")
        return None

    return CosStorage(
        secret_id=settings.cos_secret_id,
        secret_key=settings.cos_secret_key,
        region=settings.cos_region,
        bucket=settings.cos_bucket,
        prefix=settings.cos_prefix,
        session_token=getattr(settings, "cos_session_token", "") or "",
    )
