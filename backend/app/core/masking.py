"""Data masking helpers for demo/sales accounts.

Goal:
- Allow platform demo accounts to browse cross-tenant data without exposing customer identity.
- Mask organization/device identity fields at API layer for safe demos.
"""

from __future__ import annotations

import hashlib
from typing import Any
from typing import Optional


def is_demo_viewer(user: Any) -> bool:
    """Return True if the current user should see masked tenant identity."""
    if not user:
        return False
    if bool(getattr(user, "is_superadmin", False)):
        return False
    if getattr(user, "role", None) != "viewer":
        return False
    org = getattr(user, "organization", None)
    if org is None:
        return False
    return getattr(org, "code", None) == "PLATFORM_ADMIN"


def mask_device_name(*, device_id: str, mn: Optional[str] = None) -> str:
    seed = f"{device_id}|{mn or ''}".encode("utf-8")
    suffix = hashlib.sha256(seed).hexdigest()[:6].upper()
    return f"设备-{suffix}"


def mask_org_name(*, org_id: str, org_code: Optional[str] = None) -> str:
    seed = f"{org_id}|{org_code or ''}".encode("utf-8")
    suffix = hashlib.sha256(seed).hexdigest()[:6].upper()
    return f"企业-{suffix}"
