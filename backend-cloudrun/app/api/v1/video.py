from __future__ import annotations

"""Video linkage API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_org_membership, require_write_permission
from app.db.postgres import get_db
from app.models.user import User
from app.models.video import (
    VideoChannelCreate,
    VideoDemoSeedRequest,
    VideoDemoSeedResponse,
    VideoLifecycleStatus,
    VideoChannelResponse,
    VideoChannelStatus,
    VideoChannelUpdate,
    VideoEventCreate,
    VideoEventLevel,
    VideoEventResponse,
    VideoEventStatus,
    VideoPointType,
    VideoSummary,
)
from app.services.video_service import VideoService

router = APIRouter()


@router.get("/summary", response_model=VideoSummary)
async def get_video_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_org_membership)],
    org_id: UUID | None = None,
) -> VideoSummary:
    service = VideoService(db)
    return await service.get_summary(current_user=current_user, org_id=org_id)


@router.get("/channels", response_model=list[VideoChannelResponse])
async def list_video_channels(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_org_membership)],
    org_id: UUID | None = None,
    device_id: UUID | None = None,
    point_type: VideoPointType | None = None,
    lifecycle_status: VideoLifecycleStatus | None = None,
    channel_status: VideoChannelStatus | None = Query(None, alias="status"),
    ai_enabled: bool | None = None,
) -> list[VideoChannelResponse]:
    service = VideoService(db)
    return await service.list_channels(
        current_user=current_user,
        org_id=org_id,
        device_id=device_id,
        point_type=point_type.value if point_type else None,
        lifecycle_status=lifecycle_status.value if lifecycle_status else None,
        channel_status=channel_status.value if channel_status else None,
        ai_enabled=ai_enabled,
    )


@router.get("/channels/{channel_id}", response_model=VideoChannelResponse)
async def get_video_channel(
    channel_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_org_membership)],
) -> VideoChannelResponse:
    service = VideoService(db)
    return await service.get_channel(channel_id=channel_id, current_user=current_user)


@router.post("/channels", response_model=VideoChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_video_channel(
    payload: VideoChannelCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_write_permission)],
) -> VideoChannelResponse:
    service = VideoService(db)
    return await service.create_channel(payload=payload, current_user=current_user)


@router.post("/demo/inject", response_model=VideoDemoSeedResponse)
async def inject_video_demo_data(
    payload: VideoDemoSeedRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_write_permission)],
) -> VideoDemoSeedResponse:
    service = VideoService(db)
    return await service.inject_demo_data(payload=payload, current_user=current_user)


@router.put("/channels/{channel_id}", response_model=VideoChannelResponse)
async def update_video_channel(
    channel_id: UUID,
    payload: VideoChannelUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_write_permission)],
) -> VideoChannelResponse:
    service = VideoService(db)
    return await service.update_channel(
        channel_id=channel_id,
        payload=payload,
        current_user=current_user,
    )


@router.delete("/channels/{channel_id}")
async def delete_video_channel(
    channel_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_write_permission)],
) -> dict[str, str]:
    service = VideoService(db)
    await service.delete_channel(channel_id=channel_id, current_user=current_user)
    return {"message": "视频通道已删除"}


@router.get("/events", response_model=list[VideoEventResponse])
async def list_video_events(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_org_membership)],
    org_id: UUID | None = None,
    device_id: UUID | None = None,
    channel_id: UUID | None = None,
    related_alarm_id: UUID | None = None,
    event_status: VideoEventStatus | None = Query(None, alias="status"),
    level: VideoEventLevel | None = None,
    limit: int = Query(100, ge=1, le=500),
) -> list[VideoEventResponse]:
    service = VideoService(db)
    return await service.list_events(
        current_user=current_user,
        org_id=org_id,
        device_id=device_id,
        channel_id=channel_id,
        related_alarm_id=related_alarm_id,
        event_status=event_status.value if event_status else None,
        level=level.value if level else None,
        limit=limit,
    )


@router.post("/events", response_model=VideoEventResponse, status_code=status.HTTP_201_CREATED)
async def create_video_event(
    payload: VideoEventCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_write_permission)],
) -> VideoEventResponse:
    service = VideoService(db)
    return await service.create_event(payload=payload, current_user=current_user)


@router.post("/events/{event_id}/acknowledge", response_model=VideoEventResponse)
async def acknowledge_video_event(
    event_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_write_permission)],
) -> VideoEventResponse:
    service = VideoService(db)
    return await service.acknowledge_event(event_id=event_id, current_user=current_user)


@router.post("/events/{event_id}/resolve", response_model=VideoEventResponse)
async def resolve_video_event(
    event_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_write_permission)],
) -> VideoEventResponse:
    service = VideoService(db)
    return await service.resolve_event(event_id=event_id, current_user=current_user)
