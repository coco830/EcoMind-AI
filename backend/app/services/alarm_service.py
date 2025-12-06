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

logger = structlog.get_logger()
_sms_notifier = TencentSMSNotifier()

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
                await self._maybe_send_initial_sms(
                    session,
                    alarm,
                    device,
                    level,
                    current_value=value_str,
                )

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
                await self._maybe_send_initial_sms(
                    session,
                    alarm,
                    device,
                    level,
                    current_value=value_str,
                )

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
            active_alarm = await self._find_active_alarm(
                session, device_id, AlarmType.OFFLINE, None
            )
            if active_alarm:
                await self._update_active_alarm(session, active_alarm, message=message)
                return active_alarm

            if await self._has_recent_alarm(
                session, device_id, AlarmType.OFFLINE, None
            ):
                return None

            # Create alarm message
            message = f"设备 {device_mn} 已离线"
            if last_heartbeat:
                message += f"，最后心跳时间: {last_heartbeat.strftime('%Y-%m-%d %H:%M:%S')}"

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

            return alarm

        except Exception as e:
            logger.error("Failed to create offline alarm", error=str(e))
            await session.rollback()
            return None
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
