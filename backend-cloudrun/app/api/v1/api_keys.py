"""API Key management endpoints (superadmin only)."""

from __future__ import annotations

import json
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import require_superadmin
from app.db.postgres import get_db
from app.models.api_client import (
    ApiClient,
    ApiClientCreate,
    ApiClientResponse,
    ApiClientScope,
    generate_api_key,
)
from app.models.user import User

router = APIRouter()
logger = structlog.get_logger()


@router.post("", response_model=ApiClientResponse, summary="创建 API Key")
async def create_api_key(
    body: ApiClientCreate,
    current_user: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiClientResponse:
    """Create a new API key bound to an organization. Superadmin only."""
    client = ApiClient(
        api_key=generate_api_key(),
        name=body.name,
        org_id=body.org_id,
        access_scope=body.access_scope.value,
        permissions=json.dumps(body.permissions) if body.permissions else None,
        rate_limit=body.rate_limit,
        expires_at=body.expires_at,
    )
    db.add(client)
    await db.flush()
    await db.refresh(client)

    logger.info("API key created", client_name=body.name, org_id=str(body.org_id))
    return ApiClientResponse.model_validate(client)


@router.get("", response_model=list[ApiClientResponse], summary="列出所有 API Key")
async def list_api_keys(
    current_user: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: UUID | None = Query(None, description="按组织筛选"),
    access_scope: ApiClientScope | None = Query(None, description="按访问范围筛选：single_org/all_orgs"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> list[ApiClientResponse]:
    """List all API keys. Superadmin only."""
    query = select(ApiClient).order_by(ApiClient.created_at.desc())
    if org_id:
        query = query.where(ApiClient.org_id == org_id)
    if access_scope:
        query = query.where(ApiClient.access_scope == access_scope.value)
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    clients = result.scalars().all()
    return [ApiClientResponse.model_validate(c) for c in clients]


@router.delete("/{client_id}", summary="删除/吊销 API Key")
async def revoke_api_key(
    client_id: UUID,
    current_user: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Revoke (delete) an API key. Superadmin only."""
    result = await db.execute(select(ApiClient).where(ApiClient.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API Key 不存在")

    client_name = client.name
    await db.delete(client)

    logger.info("API key revoked", client_name=client_name, client_id=str(client_id))
    return {"success": True, "message": f"API Key '{client_name}' 已吊销"}


@router.patch("/{client_id}/toggle", response_model=ApiClientResponse, summary="启用/禁用 API Key")
async def toggle_api_key(
    client_id: UUID,
    current_user: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiClientResponse:
    """Toggle an API key's active status. Superadmin only."""
    result = await db.execute(select(ApiClient).where(ApiClient.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API Key 不存在")

    client.is_active = not client.is_active
    await db.flush()
    await db.refresh(client)

    status_text = "启用" if client.is_active else "禁用"
    logger.info("API key toggled", client_name=client.name, is_active=client.is_active)
    return ApiClientResponse.model_validate(client)
