from __future__ import annotations

"""Centralized Alarm Service for creating and managing alarms.

This service provides a unified interface for:
1. Creating alarms from threshold violations
2. Creating alarms from AI anomaly detection
3. Creating alarms from device status changes
4. Deduplication to prevent alarm flooding
"""

import json
from datetime import datetime, timedelta
from uuid import UUID

import structlog
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.postgres import AsyncSessionLocal
from app.models.alarm import Alarm, AlarmType, AlarmLevel, AlarmStatus
from app.models.device import Device, ThresholdConfig, PollutantThreshold
from app.services.notification import TencentSMSNotifier
from app.services.openclaw_webhook import get_openclaw_webhook_notifier

logger = structlog.get_logger()
_sms_notifier = TencentSMSNotifier()
_openclaw_webhook_notifier = get_openclaw_webhook_notifier()

# Pollutant code to name mapping
POLLUTANT_NAMES = {
    "w01018": "COD",
    "w21003": "氨氮",
    "w01001": "pH值",
    "w01010": "总磷",
    "w21011": "总氮",
    "a34004": "PM2.5",
    "a34002": "PM10",
    "a21004": "NO2",
    "a21026": "SO2",
    "a05024": "O3",
}


def get_pollutant_name(code: str) -> str:
    """Get display name for pollutant code."""
    return POLLUTANT_NAMES.get(code, code)


class AlarmService:
    """Service for centralized alarm management."""

    # Deduplication window: don't create duplicate alarms within this period
    DEDUP_WINDOW_MINUTES = 30
    FOLLOWUP_HOURS = 12

    def __init__(self, db: AsyncSession | None = None):
        """Initialize alarm service.

        Args:
            db: Optional database session. If not provided, will create new session.
        """
        self._db = db
        self._owns_session = db is None

    async def _get_session(self) -> AsyncSession:
        """Get database session."""
        if self._db is not None:
            return self._db
        return AsyncSessionLocal()

    async def _close_session(self, session: AsyncSession) -> None:
        """Close session if we own it."""
        if self._owns_session and session is not None:
            await session.close()

    async def _find_active_alarm(
        self,
        session: AsyncSession,
        device_id: UUID,
        alarm_type: AlarmType,
        pollutant_code: str | None = None,
    ) -> Alarm | None:
        """Return most recent active alarm of given type."""
        conditions = [
            Alarm.device_id == device_id,
            Alarm.alarm_type == alarm_type.value,
            Alarm.status != AlarmStatus.RESOLVED.value,
        ]
        if pollutant_code:
            conditions.append(Alarm.pollutant_code == pollutant_code)

        result = await session.execute(
            select(Alarm)
            .where(and_(*conditions))
            .order_by(Alarm.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_device_with_org(self, session: AsyncSession, device_id: UUID) -> Device | None:
        """Fetch device with organization for notification."""
        result = await session.execute(
            select(Device)
            .options(selectinload(Device.organization))
            .where(Device.id == device_id)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _update_active_alarm(
        self,
        session: AsyncSession,
        alarm: Alarm,
        *,
        value: str | None = None,
        message: str | None = None,
    ) -> None:
        """Refresh alarm context when condition persists."""
        updated = False
        if value is not None:
            alarm.value = value
            updated = True
        if message:
            alarm.message = message
            updated = True
        if updated:
            alarm.updated_at = datetime.utcnow()
            await session.commit()

    def _describe_alarm(self, alarm: Alarm) -> str:
        """Build readable alarm type description."""
        type_labels = {
            AlarmType.THRESHOLD.value: "阈值异常",
            AlarmType.ANOMALY.value: "AI异常",
            AlarmType.OFFLINE.value: "离线",
            AlarmType.FLAG.value: "数据标记异常",
        }
        label = type_labels.get(alarm.alarm_type, alarm.alarm_type)
        if alarm.pollutant_code:
            pollutant = get_pollutant_name(alarm.pollutant_code)
            return f"{pollutant}{label}"
        return label

    async def _maybe_send_initial_sms(
        self,
        session: AsyncSession,
        alarm: Alarm,
        device: Device,
        level: AlarmLevel,
        *,
        current_value: str | None = None,
    ) -> None:
        """Send first SMS for new critical alarms."""
        if level != AlarmLevel.CRITICAL:
            return
        await self._dispatch_sms(session, alarm, device, "first", current_value)

    async def _maybe_send_followup_sms(
        self,
        session: AsyncSession,
        alarm: Alarm,
        device: Device,
        *,
        current_value: str | None = None,
    ) -> None:
        """Send second SMS when 12 hours have passed since first notification."""
        if alarm.sms_sent_count != 1 or not alarm.last_sms_time:
            return
        if datetime.utcnow() - alarm.last_sms_time < timedelta(hours=self.FOLLOWUP_HOURS):
            return
        await self._dispatch_sms(session, alarm, device, "followup", current_value)

    async def _dispatch_sms(
        self,
        session: AsyncSession,
        alarm: Alarm,
        device: Device,
        variant: str,
        current_value: str | None = None,
    ) -> None:
        """Send SMS through notifier and persist counters."""
        org = device.organization
        if org is None or not org.contact_phone:
            logger.info(
                "SMS skipped - organization contact missing",
                device_id=str(device.id),
            )
            return

        type_desc = self._describe_alarm(alarm)
        value_text = current_value or alarm.value or "未知"

        if variant == "first":
            content = f"设备{device.name}发生{type_desc}，当前值{value_text}，请立即处理。"
        else:
            content = f"设备{device.name}的{type_desc}已持续12小时，当前值{value_text}，请务必核实。"

        params = [device.name, content]
        success = await _sms_notifier.send_sms([org.contact_phone], params)
        if success:
            alarm.sms_sent_count = 1 if variant == "first" else 2
            alarm.last_sms_time = datetime.utcnow()
            await session.commit()

    async def _maybe_push_openclaw_webhook(
        self,
        alarm: Alarm,
        device: Device | None,
    ) -> None:
        """Push alarm to OpenClaw webhook. Errors are swallowed to avoid blocking alarm flow."""
        try:
            await _openclaw_webhook_notifier.notify_alarm(alarm=alarm, device=device)
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.error(
                "OpenClaw webhook push failed unexpectedly",
                alarm_id=str(alarm.id),
                error=str(exc),
            )

    def _map_alarm_status_to_video_status(self, alarm_status: str) -> str:
        """Map alarm workflow status to video-event workflow status."""
        from app.models.video import VideoEventStatus

        status_map = {
            AlarmStatus.PENDING.value: VideoEventStatus.PENDING.value,
            AlarmStatus.ACKNOWLEDGED.value: VideoEventStatus.ACKNOWLEDGED.value,
            AlarmStatus.RESOLVED.value: VideoEventStatus.RESOLVED.value,
        }
        return status_map.get(alarm_status, VideoEventStatus.PENDING.value)

    def _map_alarm_level_to_video_level(self, alarm_level: str) -> str:
        """Map alarm severity to video-event severity."""
        from app.models.video import VideoEventLevel

        level_map = {
            AlarmLevel.INFO.value: VideoEventLevel.INFO.value,
            AlarmLevel.WARNING.value: VideoEventLevel.WARNING.value,
            AlarmLevel.CRITICAL.value: VideoEventLevel.CRITICAL.value,
        }
        return level_map.get(alarm_level, VideoEventLevel.WARNING.value)

    async def _ensure_video_linkage_events(
        self,
        session: AsyncSession,
        alarm: Alarm,
        device: Device | None,
    ) -> int:
        """Ensure one linked video event exists per selected video channel.

        Strategy:
        - Prefer AI-enabled channels if present
        - Otherwise fall back to all channels bound to the same monitoring device
        - One alarm produces at most one linked video event per channel
        """
        from app.models.video import (
            VideoChannel,
            VideoEvent,
            VideoEventSource,
            VideoEventType,
        )

        if device is None:
            return 0

        channels_result = await session.execute(
            select(VideoChannel)
            .where(VideoChannel.device_id == alarm.device_id)
            .order_by(VideoChannel.ai_enabled.desc(), VideoChannel.created_at.asc())
        )
        channels = channels_result.scalars().all()
        if not channels:
            return 0

        target_channels = [channel for channel in channels if channel.ai_enabled] or channels

        existing_result = await session.execute(
            select(VideoEvent.channel_id).where(VideoEvent.related_alarm_id == alarm.id)
        )
        existing_channel_ids = {row[0] for row in existing_result.fetchall()}

        created_count = 0
        alarm_desc = self._describe_alarm(alarm)
        title = f"告警联动：{device.name or device.mn} {alarm_desc}"
        summary = f"由告警自动生成的视频联动事件。原始告警信息：{alarm.message}"

        extra_data = {
            "alarm_id": str(alarm.id),
            "alarm_type": alarm.alarm_type,
            "alarm_level": alarm.level,
            "alarm_status": alarm.status,
            "device_name": device.name,
            "device_mn": device.mn,
            "pollutant_code": alarm.pollutant_code,
            "alarm_value": alarm.value,
            "threshold": alarm.threshold,
        }

        for channel in target_channels:
            if channel.id in existing_channel_ids:
                continue

            event = VideoEvent(
                org_id=channel.org_id,
                channel_id=channel.id,
                device_id=channel.device_id,
                device_mn=channel.device_mn,
                related_alarm_id=alarm.id,
                event_type=VideoEventType.AI_LINKAGE.value,
                source=VideoEventSource.AI_LINKAGE.value,
                level=self._map_alarm_level_to_video_level(alarm.level),
                status=self._map_alarm_status_to_video_status(alarm.status),
                title=title,
                summary=summary,
                occurred_at=alarm.created_at or datetime.utcnow(),
                extra_data=json.dumps(extra_data, ensure_ascii=False),
            )
            session.add(event)
            created_count += 1

        if created_count:
            await session.commit()
            logger.info(
                "Video linkage events created for alarm",
                alarm_id=str(alarm.id),
                device_id=str(alarm.device_id),
                created_count=created_count,
            )
        return created_count

    async def sync_video_events_with_alarm(
        self,
        alarm: Alarm,
        *,
        device: Device | None = None,
    ) -> int:
        """Sync linked video events to current alarm status and create missing linkage events."""
        from app.models.video import VideoEvent, VideoEventStatus

        session = await self._get_session()
        try:
            current_device = device
            if current_device is None:
                current_device = await self._get_device_with_org(session, alarm.device_id)

            await self._ensure_video_linkage_events(session, alarm, current_device)

            result = await session.execute(
                select(VideoEvent).where(VideoEvent.related_alarm_id == alarm.id)
            )
            events = result.scalars().all()
            if not events:
                return 0

            target_status = self._map_alarm_status_to_video_status(alarm.status)
            updated_count = 0

            for event in events:
                if target_status == VideoEventStatus.ACKNOWLEDGED.value:
                    if event.status == VideoEventStatus.PENDING.value:
                        event.status = target_status
                        updated_count += 1
                elif target_status == VideoEventStatus.RESOLVED.value:
                    if event.status != VideoEventStatus.RESOLVED.value:
                        event.status = target_status
                        updated_count += 1

                if event.extra_data:
                    try:
                        payload = json.loads(event.extra_data)
                    except (TypeError, ValueError, json.JSONDecodeError):
                        payload = {}
                else:
                    payload = {}
                payload["alarm_status"] = alarm.status
                event.extra_data = json.dumps(payload, ensure_ascii=False)

            if updated_count:
                await session.commit()
                logger.info(
                    "Linked video events synced with alarm",
                    alarm_id=str(alarm.id),
                    target_status=target_status,
                    updated_count=updated_count,
                )

            return updated_count
        except Exception as exc:
            logger.error(
                "Failed to sync linked video events with alarm",
                alarm_id=str(alarm.id),
                error=str(exc),
            )
            await session.rollback()
            return 0
        finally:
            await self._close_session(session)

    async def create_threshold_alarm(
        self,
        device_id: UUID,
        device_mn: str,
        pollutant_code: str,
        value: float,
        threshold: PollutantThreshold,
        is_warning: bool = False,
    ) -> Alarm | None:
        """Create alarm for threshold violation.

        Args:
            device_id: Device UUID
            device_mn: Device MN identifier
            pollutant_code: Pollutant code (e.g., 'w01018')
            value: Current measured value
            threshold: Threshold configuration
            is_warning: True if warning level, False if alarm level

        Returns:
            Created Alarm or None if deduplicated
        """
        session = await self._get_session()
        try:
            value_str = f"{value:.2f}"

            # If an active alarm exists, update and evaluate follow-up SMS
            active_alarm = await self._find_active_alarm(
                session, device_id, AlarmType.THRESHOLD, pollutant_code
            )
            if active_alarm:
                await self._update_active_alarm(session, active_alarm, value=value_str)
                device = await self._get_device_with_org(session, device_id)
                if device:
                    await self._ensure_video_linkage_events(session, active_alarm, device)
                    await self._maybe_send_followup_sms(
                        session,
                        active_alarm,
                        device,
                        current_value=value_str,
                    )
                return active_alarm

            # Check for recent duplicate after alarm resolved
            if await self._has_recent_alarm(
                session, device_id, AlarmType.THRESHOLD, pollutant_code
            ):
                logger.debug(
                    "Skipping duplicate threshold alarm",
                    device_mn=device_mn,
                    pollutant_code=pollutant_code,
                )
                return None

            # Determine alarm level
            level = AlarmLevel.WARNING if is_warning else AlarmLevel.CRITICAL
            threshold_value = threshold.warning_value if is_warning else threshold.alarm_value

            # Create alarm message
            pollutant_name = threshold.pollutant_name or get_pollutant_name(pollutant_code)
            level_text = "预警" if is_warning else "超标"
            message = (
                f"设备 {device_mn} 检测到 {pollutant_name} {level_text}！"
                f"当前值: {value:.2f} {threshold.unit}, "
                f"阈值: {threshold_value:.2f} {threshold.unit}"
            )

            alarm = Alarm(
                device_id=device_id,
                alarm_type=AlarmType.THRESHOLD.value,
                level=level.value,
                status=AlarmStatus.PENDING.value,
                pollutant_code=pollutant_code,
                message=message,
                value=value_str,
                threshold=str(threshold_value),
            )
            session.add(alarm)
            await session.commit()
            await session.refresh(alarm)

            logger.info(
                "Threshold alarm created",
                alarm_id=str(alarm.id),
                device_mn=device_mn,
                pollutant_code=pollutant_code,
                value=value,
                threshold=threshold_value,
                level=level.value,
            )

            device = await self._get_device_with_org(session, device_id)
            if device:
                await self._ensure_video_linkage_events(session, alarm, device)
                await self._maybe_send_initial_sms(
                    session,
                    alarm,
                    device,
                    level,
                    current_value=value_str,
                )

            await self._maybe_push_openclaw_webhook(alarm=alarm, device=device)

            return alarm

        except Exception as e:
            logger.error("Failed to create threshold alarm", error=str(e))
            await session.rollback()
            return None
        finally:
            await self._close_session(session)

    async def create_ai_anomaly_alarm(
        self,
        device_id: UUID,
        device_mn: str,
        pollutant_code: str,
        value: float,
        anomaly_type: str,
        anomaly_score: float,
        reason: str | None = None,
    ) -> Alarm | None:
        """Create alarm from AI anomaly detection.

        Args:
            device_id: Device UUID
            device_mn: Device MN identifier
            pollutant_code: Pollutant code
            value: Current measured value
            anomaly_type: Type of anomaly detected (e.g., '数值异常', '突变异常')
            anomaly_score: Anomaly score from AI model
            reason: AI-generated reason for the anomaly

        Returns:
            Created Alarm or None if deduplicated
        """
        session = await self._get_session()
        try:
            value_str = f"{value:.2f}"
            pollutant_name = get_pollutant_name(pollutant_code)
            message = (
                f"AI妫€娴嬪埌璁惧 {device_mn} 鐨?{pollutant_name} 鏁版嵁寮傚父锛?"
                f"绫诲瀷: {anomaly_type}, 寮傚父鍒嗘暟: {anomaly_score:.2f}"
            )
            if reason:
                message += f"\n鍘熷洜: {reason}"

            active_alarm = await self._find_active_alarm(
                session, device_id, AlarmType.ANOMALY, pollutant_code
            )
            if active_alarm:
                await self._update_active_alarm(
                    session,
                    active_alarm,
                    value=value_str,
                    message=message,
                )
                device = await self._get_device_with_org(session, device_id)
                if device:
                    await self._ensure_video_linkage_events(session, active_alarm, device)
                    await self._maybe_send_followup_sms(
                        session,
                        active_alarm,
                        device,
                        current_value=value_str,
                    )
                return active_alarm

            if await self._has_recent_alarm(
                session, device_id, AlarmType.ANOMALY, pollutant_code
            ):
                logger.debug(
                    "Skipping duplicate AI anomaly alarm",
                    device_mn=device_mn,
                    pollutant_code=pollutant_code,
                )
                return None

            # Determine alarm level based on score
            if anomaly_score <= -0.9:
                level = AlarmLevel.CRITICAL
            elif anomaly_score <= -0.7:
                level = AlarmLevel.WARNING
            else:
                level = AlarmLevel.INFO

            # Create alarm message
            pollutant_name = get_pollutant_name(pollutant_code)
            message = (
                f"AI检测到设备 {device_mn} 的 {pollutant_name} 数据异常！"
                f"类型: {anomaly_type}, 异常分数: {anomaly_score:.2f}"
            )
            if reason:
                message += f"\n原因: {reason}"

            alarm = Alarm(
                device_id=device_id,
                alarm_type=AlarmType.ANOMALY.value,
                level=level.value,
                status=AlarmStatus.PENDING.value,
                pollutant_code=pollutant_code,
                message=message,
                value=value_str,
                threshold=f"AI Score: {anomaly_score:.2f}",
            )
            session.add(alarm)
            await session.commit()
            await session.refresh(alarm)

            logger.info(
                "AI anomaly alarm created",
                alarm_id=str(alarm.id),
                device_mn=device_mn,
                pollutant_code=pollutant_code,
                anomaly_type=anomaly_type,
                anomaly_score=anomaly_score,
            )

            device = await self._get_device_with_org(session, device_id)
            if device:
                await self._ensure_video_linkage_events(session, alarm, device)
                await self._maybe_send_initial_sms(
                    session,
                    alarm,
                    device,
                    level,
                    current_value=value_str,
                )

            await self._maybe_push_openclaw_webhook(alarm=alarm, device=device)

            return alarm

        except Exception as e:
            logger.error("Failed to create AI anomaly alarm", error=str(e))
            await session.rollback()
            return None
        finally:
            await self._close_session(session)

    async def create_device_offline_alarm(
        self,
        device_id: UUID,
        device_mn: str,
        last_heartbeat: datetime | None = None,
    ) -> Alarm | None:
        """Create alarm for device going offline.

        Args:
            device_id: Device UUID
            device_mn: Device MN identifier
            last_heartbeat: Last known heartbeat time

        Returns:
            Created Alarm or None if deduplicated
        """
        session = await self._get_session()
        try:
            # Create alarm message (used for both create and update)
            message = f"设备 {device_mn} 已离线"
            if last_heartbeat:
                message += f"，最后心跳时间: {last_heartbeat.strftime('%Y-%m-%d %H:%M:%S')}"

            active_alarm = await self._find_active_alarm(
                session, device_id, AlarmType.OFFLINE, None
            )
            if active_alarm:
                await self._update_active_alarm(session, active_alarm, message=message)
                device = await self._get_device_with_org(session, device_id)
                if device:
                    await self._ensure_video_linkage_events(session, active_alarm, device)
                return active_alarm

            if await self._has_recent_alarm(
                session, device_id, AlarmType.OFFLINE, None
            ):
                return None

            alarm = Alarm(
                device_id=device_id,
                alarm_type=AlarmType.OFFLINE.value,
                level=AlarmLevel.WARNING.value,
                status=AlarmStatus.PENDING.value,
                pollutant_code=None,
                message=message,
                value=None,
                threshold=None,
            )
            session.add(alarm)
            await session.commit()
            await session.refresh(alarm)

            logger.info(
                "Device offline alarm created",
                alarm_id=str(alarm.id),
                device_mn=device_mn,
            )

            device = await self._get_device_with_org(session, device_id)
            if device:
                await self._ensure_video_linkage_events(session, alarm, device)
            await self._maybe_push_openclaw_webhook(alarm=alarm, device=device)

            return alarm

        except Exception as e:
            logger.error("Failed to create offline alarm", error=str(e))
            await session.rollback()
            return None
        finally:
            await self._close_session(session)

    async def resolve_device_offline_alarms(
        self,
        device_id: UUID,
        *,
        resolved_at: datetime | None = None,
    ) -> int:
        """Resolve all active offline alarms for a device."""
        from sqlalchemy import update
        from app.models.video import VideoEvent, VideoEventStatus

        session = await self._get_session()
        try:
            ts = resolved_at or datetime.utcnow()
            alarms_result = await session.execute(
                select(Alarm.id).where(
                    Alarm.device_id == device_id,
                    Alarm.alarm_type == AlarmType.OFFLINE.value,
                    Alarm.status != AlarmStatus.RESOLVED.value,
                )
            )
            alarm_ids = [row[0] for row in alarms_result.fetchall()]

            result = await session.execute(
                update(Alarm)
                .where(
                    Alarm.device_id == device_id,
                    Alarm.alarm_type == AlarmType.OFFLINE.value,
                    Alarm.status != AlarmStatus.RESOLVED.value,
                )
                .values(status=AlarmStatus.RESOLVED.value, resolved_at=ts, updated_at=ts)
            )

            if alarm_ids:
                await session.execute(
                    update(VideoEvent)
                    .where(
                        VideoEvent.related_alarm_id.in_(alarm_ids),
                        VideoEvent.status != VideoEventStatus.RESOLVED.value,
                    )
                    .values(status=VideoEventStatus.RESOLVED.value, updated_at=ts)
                )

            await session.commit()
            return int(getattr(result, "rowcount", 0) or 0)
        except Exception as e:
            logger.error("Failed to resolve offline alarms", error=str(e))
            await session.rollback()
            return 0
        finally:
            await self._close_session(session)

    async def create_flag_alarm(
        self,
        device_id: UUID,
        device_mn: str,
        pollutant_code: str,
        flag: str,
        value: float,
    ) -> Alarm | None:
        """Create alarm for abnormal data flag.

        Args:
            device_id: Device UUID
            device_mn: Device MN identifier
            pollutant_code: Pollutant code
            flag: Flag value (e.g., 'D' for device fault)
            value: Current measured value

        Returns:
            Created Alarm or None if deduplicated
        """
        session = await self._get_session()
        try:
            value_str = f"{value:.2f}"
            message = (
                f"Flag anomaly detected on device {device_mn}, pollutant {pollutant_code}, "
                f"flag={flag}, value={value:.2f}"
            )
            active_alarm = await self._find_active_alarm(
                session, device_id, AlarmType.FLAG, pollutant_code
            )
            if active_alarm:
                await self._update_active_alarm(
                    session,
                    active_alarm,
                    value=value_str,
                    message=message,
                )
                device = await self._get_device_with_org(session, device_id)
                if device:
                    await self._ensure_video_linkage_events(session, active_alarm, device)
                return active_alarm

            if await self._has_recent_alarm(
                session, device_id, AlarmType.FLAG, pollutant_code
            ):
                return None

            # Map flag to description
            flag_descriptions = {
                "D": "设备故障",
                "T": "超测量上限",
                "B": "低于检测限",
                "M": "维护",
                "C": "校准",
                "F": "断流",
            }
            flag_desc = flag_descriptions.get(flag.upper(), f"异常标记({flag})")

            pollutant_name = get_pollutant_name(pollutant_code)
            message = (
                f"设备 {device_mn} 的 {pollutant_name} 数据标记异常！"
                f"标记: {flag} ({flag_desc}), 当前值: {value:.2f}"
            )

            alarm = Alarm(
                device_id=device_id,
                alarm_type=AlarmType.FLAG.value,
                level=AlarmLevel.WARNING.value,
                status=AlarmStatus.PENDING.value,
                pollutant_code=pollutant_code,
                message=message,
                value=value_str,
                threshold=f"Flag: {flag}",
            )
            session.add(alarm)
            await session.commit()
            await session.refresh(alarm)

            logger.info(
                "Flag alarm created",
                alarm_id=str(alarm.id),
                device_mn=device_mn,
                pollutant_code=pollutant_code,
                flag=flag,
            )

            device = await self._get_device_with_org(session, device_id)
            if device:
                await self._ensure_video_linkage_events(session, alarm, device)
            await self._maybe_push_openclaw_webhook(alarm=alarm, device=device)

            return alarm

        except Exception as e:
            logger.error("Failed to create flag alarm", error=str(e))
            await session.rollback()
            return None
        finally:
            await self._close_session(session)

    async def _has_recent_alarm(
        self,
        session: AsyncSession,
        device_id: UUID,
        alarm_type: AlarmType,
        pollutant_code: str | None,
    ) -> bool:
        """Check if there's a recent alarm of the same type to prevent duplicates.

        Args:
            session: Database session
            device_id: Device UUID
            alarm_type: Type of alarm
            pollutant_code: Pollutant code (optional)

        Returns:
            True if recent alarm exists
        """
        cutoff_time = datetime.utcnow() - timedelta(minutes=self.DEDUP_WINDOW_MINUTES)

        conditions = [
            Alarm.device_id == device_id,
            Alarm.alarm_type == alarm_type.value,
            Alarm.created_at >= cutoff_time,
            Alarm.status != AlarmStatus.RESOLVED.value,
        ]

        if pollutant_code:
            conditions.append(Alarm.pollutant_code == pollutant_code)

        result = await session.execute(
            select(Alarm).where(and_(*conditions)).limit(1)
        )
        return result.scalar_one_or_none() is not None


async def check_thresholds_and_create_alarms(
    device: Device,
    pollutant_code: str,
    value: float,
    flag: str = "N",
) -> list[Alarm]:
    """Check thresholds for a data point and create alarms if necessary.

    This is the main entry point for threshold checking from TCP Gateway.

    Args:
        device: Device ORM object
        pollutant_code: Pollutant code
        value: Measured value
        flag: Data flag

    Returns:
        List of created alarms
    """
    alarms: list[Alarm] = []
    alarm_service = AlarmService()

    # Check for flag anomalies first
    if flag and flag.upper() in ("D", "T", "B", "F"):
        alarm = await alarm_service.create_flag_alarm(
            device_id=device.id,
            device_mn=device.mn,
            pollutant_code=pollutant_code,
            flag=flag,
            value=value,
        )
        if alarm:
            alarms.append(alarm)

    # Parse threshold config
    if not device.thresholds:
        return alarms

    try:
        config_data = json.loads(device.thresholds)
        config = ThresholdConfig.model_validate(config_data)
    except (json.JSONDecodeError, ValueError):
        return alarms

    if not config.enabled:
        return alarms

    # Find threshold for this pollutant
    threshold = config.get_threshold(pollutant_code)
    if not threshold:
        return alarms

    # Skip disabled or zero thresholds
    if getattr(threshold, "enabled", True) is False:
        return alarms
    if threshold.warning_value <= 0 and threshold.alarm_value <= 0:
        return alarms

    # Check alarm level (higher threshold)
    if value >= threshold.alarm_value:
        alarm = await alarm_service.create_threshold_alarm(
            device_id=device.id,
            device_mn=device.mn,
            pollutant_code=pollutant_code,
            value=value,
            threshold=threshold,
            is_warning=False,
        )
        if alarm:
            alarms.append(alarm)
    # Check warning level (lower threshold)
    elif value >= threshold.warning_value:
        alarm = await alarm_service.create_threshold_alarm(
            device_id=device.id,
            device_mn=device.mn,
            pollutant_code=pollutant_code,
            value=value,
            threshold=threshold,
            is_warning=True,
        )
        if alarm:
            alarms.append(alarm)

    return alarms


# Singleton service instance
_alarm_service: AlarmService | None = None


def get_alarm_service() -> AlarmService:
    """Get singleton alarm service instance."""
    global _alarm_service
    if _alarm_service is None:
        _alarm_service = AlarmService()
    return _alarm_service
