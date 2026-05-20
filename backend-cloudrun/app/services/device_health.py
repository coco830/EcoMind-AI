"""Device health monitoring utilities (offline detection + alarm syncing)."""

from __future__ import annotations

from datetime import datetime, timedelta

import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.device import Device, DeviceStatus
from app.services.alarm_service import AlarmService

logger = structlog.get_logger(__name__)
settings = get_settings()


async def sync_device_health(db: AsyncSession) -> dict[str, int]:
    """Sync device offline status and ensure offline alarms exist.

    Rules (MVP pragmatic):
    - If `last_heartbeat` is missing and the device has existed longer than grace window,
      treat as offline.
    - If `last_heartbeat` is older than offline threshold, treat as offline.
    - For offline devices, ensure a single active OFFLINE alarm exists (deduplicated).
    """

    now = datetime.utcnow()
    offline_cutoff = now - timedelta(minutes=int(settings.device_offline_threshold_minutes))
    grace_cutoff = now - timedelta(minutes=int(settings.device_offline_grace_minutes))

    # Candidates that should be offline
    candidates_stmt = (
        select(Device)
        .where(
            or_(
                (Device.last_heartbeat.is_(None) & (Device.created_at <= grace_cutoff)),
                (Device.last_heartbeat.is_not(None) & (Device.last_heartbeat < offline_cutoff)),
            )
        )
    )

    result = await db.execute(candidates_stmt)
    devices = result.scalars().all()

    alarm_service = AlarmService(db)
    status_updates = 0
    alarms_created_or_updated = 0

    for device in devices:
        if device.status != DeviceStatus.OFFLINE.value:
            device.status = DeviceStatus.OFFLINE.value
            status_updates += 1

        alarm = await alarm_service.create_device_offline_alarm(
            device_id=device.id,
            device_mn=device.mn,
            last_heartbeat=device.last_heartbeat,
        )
        if alarm is not None:
            alarms_created_or_updated += 1

    return {
        "offline_status_updated": status_updates,
        "offline_alarms_upserted": alarms_created_or_updated,
    }

