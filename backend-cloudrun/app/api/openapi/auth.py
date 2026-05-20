"""API Key authentication middleware for OpenAPI agent integrations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.postgres import get_db
from app.models.api_client import ApiClient, ApiClientScope
from app.models.organization import Organization

logger = structlog.get_logger()

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class ApiClientContext:
    """Authenticated API client context injected into endpoints."""

    def __init__(self, client: ApiClient, org_id: UUID, org_name: str):
        self.client = client
        self.org_id = org_id
        self.org_name = org_name
        self.client_name = client.name
        self.access_scope = client.access_scope or ApiClientScope.SINGLE_ORG.value
        self._permissions: list[str] | None = None

    @property
    def permissions(self) -> list[str] | None:
        if self._permissions is not None:
            return self._permissions
        if self.client.permissions:
            try:
                self._permissions = json.loads(self.client.permissions)
            except (json.JSONDecodeError, TypeError):
                self._permissions = None
        return self._permissions

    def has_permission(self, tool_name: str) -> bool:
        """Check if client has permission to call a specific tool."""
        perms = self.permissions
        if perms is None:
            return True  # No restrictions = all tools allowed
        return tool_name in perms

    @property
    def is_all_orgs(self) -> bool:
        """Whether current API key can access all organizations."""
        return self.access_scope == ApiClientScope.ALL_ORGS.value


async def get_api_client(
    api_key: Annotated[str | None, Security(api_key_header)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiClientContext:
    """Validate API key and return client context."""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "error_code": "MISSING_API_KEY",
                "message": "请在请求头中提供 X-API-Key",
                "suggestion": "在 HTTP Header 中添加 X-API-Key: ecomind_your_api_key",
            },
        )

    result = await db.execute(
        select(ApiClient)
        .options(selectinload(ApiClient.organization))
        .where(ApiClient.api_key == api_key)
    )
    client = result.scalar_one_or_none()

    if client is None:
        logger.warning("Invalid API key attempt", key_prefix=api_key[:12] + "...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "error_code": "INVALID_API_KEY",
                "message": "API Key 无效或不存在",
                "suggestion": "请检查 API Key 是否正确，或联系管理员获取有效的 Key",
            },
        )

    if not client.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "success": False,
                "error_code": "API_KEY_DISABLED",
                "message": "该 API Key 已被禁用",
                "suggestion": "请联系管理员重新启用或获取新的 API Key",
            },
        )

    if client.expires_at and client.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "success": False,
                "error_code": "API_KEY_EXPIRED",
                "message": f"该 API Key 已于 {client.expires_at.strftime('%Y-%m-%d')} 过期",
                "suggestion": "请联系管理员续期或获取新的 API Key",
            },
        )

    org = client.organization
    org_name = org.name if org else "未知组织"

    logger.info(
        "OpenAPI request authenticated",
        client_name=client.name,
        org_id=str(client.org_id),
        access_scope=client.access_scope,
    )

    return ApiClientContext(client=client, org_id=client.org_id, org_name=org_name)


async def resolve_target_org(
    ctx: ApiClientContext,
    db: AsyncSession,
    enterprise_name: str | None = None,
    org_id: UUID | None = None,
) -> tuple[UUID, str]:
    """Resolve target organization for query scope.

    - single_org key: always uses key-bound organization.
    - all_orgs key: requires enterprise_name or org_id selector.
    """
    if not ctx.is_all_orgs:
        return ctx.org_id, ctx.org_name

    if org_id is not None:
        result = await db.execute(select(Organization).where(Organization.id == org_id))
        org = result.scalars().first()
        if org is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "error_code": "ORG_NOT_FOUND",
                    "message": f"未找到组织ID为 {org_id} 的企业",
                    "suggestion": "请检查 org_id 是否正确，或改用 enterprise_name 查询",
                },
            )
        return org.id, org.name

    keyword = (enterprise_name or "").strip()
    if not keyword:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error_code": "MISSING_ENTERPRISE_SELECTOR",
                "message": "当前 API Key 为 all_orgs 模式，请提供 enterprise_name 或 org_id",
                "suggestion": "例如：enterprise_name=昆明安琪儿妇产医院",
            },
        )

    result = await db.execute(
        select(Organization)
        .where(Organization.name.contains(keyword))
        .order_by(Organization.name.asc())
        .limit(6)
    )
    organizations = result.scalars().all()

    if not organizations:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "error_code": "ENTERPRISE_NOT_FOUND",
                "message": f"未找到名称包含“{keyword}”的企业",
                "suggestion": "请检查企业名称，或改用 org_id 精确查询",
            },
        )

    if len(organizations) > 1:
        candidates = [org.name for org in organizations[:5]]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error_code": "ENTERPRISE_AMBIGUOUS",
                "message": f"企业名称“{keyword}”匹配到多个结果，请提供更精确的 enterprise_name 或直接使用 org_id",
                "possible_reasons": candidates,
                "suggestion": "建议使用 org_id 精确查询，或补充企业全称",
            },
        )

    org = organizations[0]
    return org.id, org.name


def require_tool_permission(tool_name: str):
    """Dependency factory that checks if the client has permission for a specific tool."""

    async def _check(ctx: Annotated[ApiClientContext, Depends(get_api_client)]) -> ApiClientContext:
        if not ctx.has_permission(tool_name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "success": False,
                    "error_code": "PERMISSION_DENIED",
                    "message": f"当前 API Key 没有调用 {tool_name} 工具的权限",
                    "suggestion": "请联系管理员为该 API Key 添加相应权限",
                },
            )
        return ctx

    return _check
