"""Bootstrap default users for the EcoMind-AI platform.

Why this exists:
- CloudBase 云托管的「在线终端」环境变量/工作目录可能与运行容器不一致，
  直接在终端执行初始化脚本经常失败。
- 为保证可用性，后端启动时（可配置）会确保 3 个默认账号存在，且不影响后续手动改密。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.organization import Organization
from app.models.user import User, UserRole


class DefaultUserPasswordError(RuntimeError):
    """Raised when production default user passwords are not explicitly configured."""


@dataclass(frozen=True)
class DefaultUserSpec:
    username: str
    email: str
    password: str
    full_name: str
    role: str
    is_superadmin: bool


DEV_ONLY_DEFAULT_PASSWORDS = {
    "superadmin": "yueenhb123..",
    "wenyuan": "huanbao-1983",
    "huanbao": "huanbao@123",
}

PASSWORD_ENV_VARS = {
    "superadmin": "DEFAULT_SUPERADMIN_PASSWORD",
    "wenyuan": "DEFAULT_WENYUAN_PASSWORD",
    "huanbao": "DEFAULT_HUANBAO_PASSWORD",
}


def _bool_env(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}


def _is_production_environment() -> bool:
    environment = os.getenv("ENVIRONMENT") or os.getenv("APP_ENV") or "development"
    return environment.strip().lower() == "production"


def _resolve_default_password(username: str) -> str:
    env_name = PASSWORD_ENV_VARS[username]
    password = os.getenv(env_name)
    if password:
        return password
    if _is_production_environment():
        raise DefaultUserPasswordError(
            f"{env_name} is required when bootstrapping default users in production"
        )
    return DEV_ONLY_DEFAULT_PASSWORDS[username]


def _looks_like_supported_hash(hashed_password: str | None) -> bool:
    if not hashed_password:
        return False
    # bcrypt variants ($2a$/$2b$/$2y$) or legacy sha256:
    return hashed_password.startswith("$2") or hashed_password.startswith("sha256:")


def get_default_user_specs() -> list[DefaultUserSpec]:
    # Development keeps local bootstrap convenience; production requires env passwords.
    return [
        DefaultUserSpec(
            username="superadmin",
            email="yueenrs@yueentech.cn",
            password=_resolve_default_password("superadmin"),
            full_name="超级管理员",
            role=UserRole.SUPERADMIN.value,
            is_superadmin=True,
        ),
        DefaultUserSpec(
            username="wenyuan",
            email="yueenxs@yueentech.cn",
            password=_resolve_default_password("wenyuan"),
            full_name="技术文员",
            role=UserRole.DOC_EDITOR.value,
            is_superadmin=False,
        ),
        DefaultUserSpec(
            username="huanbao",
            email="yueenhb@163.com",
            password=_resolve_default_password("huanbao"),
            full_name="销售演示",
            role=UserRole.VIEWER.value,
            is_superadmin=False,
        ),
    ]


async def _get_or_create_platform_org(db: AsyncSession) -> Organization:
    result = await db.execute(select(Organization).where(Organization.code == "PLATFORM_ADMIN"))
    org = result.scalar_one_or_none()
    if org is not None:
        return org

    org = Organization(
        name="平台管理",
        code="PLATFORM_ADMIN",
        address="",
        contact_name="Platform Admin",
        contact_phone="",
        status="active",
    )
    db.add(org)
    await db.flush()
    await db.refresh(org)
    return org


async def ensure_default_users(
    db: AsyncSession,
    *,
    reset_passwords: bool | None = None,
) -> dict[str, int]:
    """Ensure the platform default users exist.

    - Idempotent: safe to run on every startup.
    - Does NOT reset existing passwords unless:
        - `reset_passwords=True`, OR
        - existing hash looks invalid/unrecognized.
    """
    if reset_passwords is None:
        reset_passwords = _bool_env("BOOTSTRAP_DEFAULT_USERS_RESET_PASSWORDS", False)

    org = await _get_or_create_platform_org(db)

    created = 0
    updated = 0

    for spec in get_default_user_specs():
        result = await db.execute(select(User).where(User.username == spec.username))
        user = result.scalar_one_or_none()

        if user is None:
            result = await db.execute(select(User).where(User.email == spec.email))
            user = result.scalar_one_or_none()

        if user is None:
            db.add(
                User(
                    username=spec.username,
                    email=spec.email,
                    hashed_password=get_password_hash(spec.password),
                    full_name=spec.full_name,
                    role=spec.role,
                    is_active=True,
                    is_superadmin=spec.is_superadmin,
                    org_id=org.id,
                )
            )
            created += 1
            continue

        changed = False

        if user.username != spec.username:
            user.username = spec.username
            changed = True
        if user.email != spec.email:
            user.email = spec.email
            changed = True
        if user.full_name != spec.full_name:
            user.full_name = spec.full_name
            changed = True
        if user.role != spec.role:
            user.role = spec.role
            changed = True
        if bool(user.is_superadmin) != bool(spec.is_superadmin):
            user.is_superadmin = spec.is_superadmin
            changed = True
        if not user.is_active:
            user.is_active = True
            changed = True
        if user.org_id is None:
            user.org_id = org.id
            changed = True

        should_reset = reset_passwords or not _looks_like_supported_hash(user.hashed_password)
        if should_reset:
            user.hashed_password = get_password_hash(spec.password)
            changed = True

        if changed:
            updated += 1

    return {"created": created, "updated": updated}

