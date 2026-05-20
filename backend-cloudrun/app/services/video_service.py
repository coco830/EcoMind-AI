from __future__ import annotations

"""Video linkage service."""

from datetime import datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import can_cross_tenant_read
from app.models.alarm import Alarm, AlarmLevel, AlarmStatus, AlarmType
from app.models.device import Device, DeviceStatus, DeviceType
from app.models.user import User
from app.models.video import (
    VideoAccessMethod,
    VideoChannel,
    VideoChannelCreate,
    VideoDemoSeedRequest,
    VideoDemoSeedResponse,
    VideoLifecycleStatus,
    VideoPointType,
    VideoProtocol,
    VideoChannelResponse,
    VideoChannelStatus,
    VideoChannelUpdate,
    VideoEvent,
    VideoEventCreate,
    VideoEventLevel,
    VideoEventResponse,
    VideoEventSource,
    VideoEventStatus,
    VideoEventType,
    VideoSummary,
    deserialize_video_extra_data,
    serialize_video_extra_data,
)
from app.services.alarm_service import AlarmService


class VideoService:
    """Service layer for video channel/event management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _resolve_device(self, *, device_id: UUID, current_user: User) -> Device:
        query = select(Device).where(Device.id == device_id)
        if not can_cross_tenant_read(current_user):
            if current_user.org_id is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User must belong to an organization",
                )
            query = query.where(Device.org_id == current_user.org_id)

        result = await self.db.execute(query)
        device = result.scalar_one_or_none()
        if device is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="关联监测设备不存在或无权访问",
            )
        return device

    async def _resolve_channel(self, *, channel_id: UUID, current_user: User) -> VideoChannel:
        query = (
            select(VideoChannel)
            .options(selectinload(VideoChannel.device))
            .where(VideoChannel.id == channel_id)
        )
        if not can_cross_tenant_read(current_user):
            if current_user.org_id is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User must belong to an organization",
                )
            query = query.where(VideoChannel.org_id == current_user.org_id)

        result = await self.db.execute(query)
        channel = result.scalar_one_or_none()
        if channel is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="视频通道不存在")
        return channel

    async def _resolve_event(self, *, event_id: UUID, current_user: User) -> VideoEvent:
        query = (
            select(VideoEvent)
            .options(selectinload(VideoEvent.channel), selectinload(VideoEvent.device))
            .where(VideoEvent.id == event_id)
        )
        if not can_cross_tenant_read(current_user):
            if current_user.org_id is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User must belong to an organization",
                )
            query = query.where(VideoEvent.org_id == current_user.org_id)

        result = await self.db.execute(query)
        event = result.scalar_one_or_none()
        if event is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="视频事件不存在")
        return event

    async def _list_demo_scope_devices(
        self,
        *,
        org_id: UUID | None,
        device_id: UUID | None,
        current_user: User,
    ) -> tuple[UUID, list[Device], int]:
        if device_id is not None:
            device = await self._resolve_device(device_id=device_id, current_user=current_user)
            if org_id and org_id != device.org_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="所选设备与企业不匹配",
                )
            return device.org_id, [device], 0

        target_org_id = org_id or current_user.org_id
        if target_org_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请先选择企业或设备后再导入演示数据",
            )

        result = await self.db.execute(
            select(Device)
            .where(Device.org_id == target_org_id)
            .order_by(Device.created_at.asc())
            .limit(3)
        )
        devices = result.scalars().all()
        return target_org_id, devices, 0

    async def _ensure_demo_devices(self, *, org_id: UUID) -> tuple[list[Device], int]:
        org_suffix = str(org_id).replace("-", "")[:8].upper()
        specs = [
            {
                "mn": f"VIDEODEMO{org_suffix}01"[:24],
                "name": "[DEMO] 废水总排口数采仪",
                "address": "演示厂区废水总排口旁",
            },
            {
                "mn": f"VIDEODEMO{org_suffix}02"[:24],
                "name": "[DEMO] 站房辅助数采仪",
                "address": "演示厂区在线监测站房",
            },
        ]
        existing_result = await self.db.execute(
            select(Device).where(Device.org_id == org_id, Device.mn.in_([item["mn"] for item in specs]))
        )
        existing_by_mn = {device.mn: device for device in existing_result.scalars().all()}

        devices: list[Device] = []
        created_devices = 0
        for index, spec in enumerate(specs, start=1):
            device = existing_by_mn.get(spec["mn"])
            if device is None:
                device = Device(
                    org_id=org_id,
                    mn=spec["mn"],
                    name=spec["name"],
                    device_type=DeviceType.WATER.value,
                    status=DeviceStatus.ONLINE.value if index == 1 else DeviceStatus.MAINTENANCE.value,
                    industry_type=None,
                    national_standard="GB 18918-2002",
                    address=spec["address"],
                    pollutant_codes="w01018,w21003,w01001",
                    last_heartbeat=datetime.utcnow(),
                )
                self.db.add(device)
                await self.db.flush()
                created_devices += 1
            devices.append(device)
        return devices, created_devices

    async def _clear_existing_demo_records(self, *, device_ids: list[UUID]) -> None:
        if not device_ids:
            return

        alarm_result = await self.db.execute(
            select(Alarm.id).where(
                Alarm.device_id.in_(device_ids),
                Alarm.message.like("[DEMO]%"),
            )
        )
        demo_alarm_ids = [row[0] for row in alarm_result.fetchall()]

        event_conditions = [VideoEvent.title.like("[DEMO]%"), VideoEvent.device_id.in_(device_ids)]
        if demo_alarm_ids:
            await self.db.execute(
                delete(VideoEvent).where(
                    or_(
                        VideoEvent.related_alarm_id.in_(demo_alarm_ids),
                        VideoEvent.title.like("[DEMO]%"),
                    )
                )
            )
            await self.db.execute(delete(Alarm).where(Alarm.id.in_(demo_alarm_ids)))
        else:
            await self.db.execute(delete(VideoEvent).where(*event_conditions))

        await self.db.execute(
            delete(VideoChannel).where(
                VideoChannel.device_id.in_(device_ids),
                VideoChannel.name.like("[DEMO]%"),
            )
        )

    async def inject_demo_data(
        self,
        *,
        payload: VideoDemoSeedRequest,
        current_user: User,
    ) -> VideoDemoSeedResponse:
        target_org_id, devices, created_devices = await self._list_demo_scope_devices(
            org_id=payload.org_id,
            device_id=payload.device_id,
            current_user=current_user,
        )

        if not devices:
            if not payload.create_demo_devices_if_missing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="当前企业下没有监测设备，请先建设备或启用自动创建演示设备",
                )
            devices, auto_created = await self._ensure_demo_devices(org_id=target_org_id)
            created_devices += auto_created

        device_ids = [device.id for device in devices]
        if payload.replace_existing:
            await self._clear_existing_demo_records(device_ids=device_ids)
        else:
            existing_demo_result = await self.db.execute(
                select(func.count(VideoChannel.id)).where(
                    VideoChannel.device_id.in_(device_ids),
                    VideoChannel.name.like("[DEMO]%"),
                )
            )
            if int(existing_demo_result.scalar() or 0) > 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="当前范围内已存在演示视频数据，请先启用替换模式",
                )

        channel_templates = [
            {
                "name": "[DEMO] 废水总排口主视角",
                "point_type": VideoPointType.WASTEWATER_OUTLET.value,
                "protocol": VideoProtocol.GB28181.value,
                "access_method": VideoAccessMethod.OPERATOR_PLATFORM.value,
                "lifecycle_status": VideoLifecycleStatus.ACTIVE.value,
                "status": VideoChannelStatus.ONLINE.value,
                "vendor": "演示海康平台",
                "network_provider": "电信专线",
                "fixed_ip": "10.20.30.11",
                "install_location": "总排口采样槽正前方，覆盖出水口和采样平台",
                "surveyor_name": "环保管家A",
                "installer_name": "实施工程师A",
                "accepted_by": "业主环保负责人",
                "accepted_at": datetime.utcnow() - timedelta(days=2),
                "acceptance_notes": "机位角度满足取证要求，夜间补光正常",
                "ai_enabled": True,
                "channel_code": "DEMO-CH-001",
                "preview_url": "mock://preview/outlet-main",
                "playback_url": "mock://playback/outlet-main",
                "last_seen_at": datetime.utcnow() - timedelta(minutes=3),
                "notes": "[DEMO] 用于联调演示，无真实视频流",
            },
            {
                "name": "[DEMO] 站房门禁视角",
                "point_type": VideoPointType.STATION_ROOM.value,
                "protocol": VideoProtocol.ONVIF.value,
                "access_method": VideoAccessMethod.DIRECT.value,
                "lifecycle_status": VideoLifecycleStatus.COMMISSIONING.value,
                "status": VideoChannelStatus.ONLINE.value,
                "vendor": "演示大华设备",
                "network_provider": "企业专网",
                "fixed_ip": "10.20.30.21",
                "install_location": "在线站房入口上方，覆盖门禁和分析仪机柜",
                "surveyor_name": "环保管家B",
                "installer_name": "实施工程师B",
                "accepted_by": "",
                "accepted_at": None,
                "acceptance_notes": "企业侧尚未放通预览接口，正在联调",
                "ai_enabled": False,
                "channel_code": "DEMO-CH-002",
                "preview_url": "mock://preview/station-door",
                "playback_url": "mock://playback/station-door",
                "last_seen_at": datetime.utcnow() - timedelta(minutes=18),
                "notes": "[DEMO] 联调阶段示例",
            },
            {
                "name": "[DEMO] 手工采样近景",
                "point_type": VideoPointType.MANUAL_SAMPLING.value,
                "protocol": VideoProtocol.HTTP_LINK.value,
                "access_method": VideoAccessMethod.EXTERNAL_LINK.value,
                "lifecycle_status": VideoLifecycleStatus.PENDING_NETWORKING.value,
                "status": VideoChannelStatus.UNKNOWN.value,
                "vendor": "企业现有监控",
                "network_provider": "待定",
                "fixed_ip": "",
                "install_location": "人工采样平台护栏内侧",
                "surveyor_name": "环保管家C",
                "installer_name": "",
                "accepted_by": "",
                "accepted_at": None,
                "acceptance_notes": "机位已确认，等待企业网络开通",
                "ai_enabled": False,
                "channel_code": "DEMO-CH-003",
                "preview_url": "mock://preview/manual-sampling",
                "playback_url": "mock://playback/manual-sampling",
                "last_seen_at": None,
                "notes": "[DEMO] 待联网示例",
            },
            {
                "name": "[DEMO] 排口远景全貌",
                "point_type": VideoPointType.CUSTOM.value,
                "protocol": VideoProtocol.RTSP.value,
                "access_method": VideoAccessMethod.CITY_PLATFORM.value,
                "lifecycle_status": VideoLifecycleStatus.PENDING_INSTALLATION.value,
                "status": VideoChannelStatus.UNKNOWN.value,
                "vendor": "州市视频平台",
                "network_provider": "移动4G",
                "fixed_ip": "",
                "install_location": "排口下游河道边立杆",
                "surveyor_name": "环保管家D",
                "installer_name": "",
                "accepted_by": "",
                "accepted_at": None,
                "acceptance_notes": "杆件与供电点位已确认，等待安装",
                "ai_enabled": False,
                "channel_code": "DEMO-CH-004",
                "preview_url": "mock://preview/outlet-panorama",
                "playback_url": "mock://playback/outlet-panorama",
                "last_seen_at": None,
                "notes": "[DEMO] 待安装示例",
            },
            {
                "name": "[DEMO] 预留扩展机位",
                "point_type": VideoPointType.CUSTOM.value,
                "protocol": VideoProtocol.OTHER.value,
                "access_method": VideoAccessMethod.OPERATOR_PLATFORM.value,
                "lifecycle_status": VideoLifecycleStatus.PENDING_SURVEY.value,
                "status": VideoChannelStatus.UNKNOWN.value,
                "vendor": "",
                "network_provider": "",
                "fixed_ip": "",
                "install_location": "待现场勘点确认",
                "surveyor_name": "",
                "installer_name": "",
                "accepted_by": "",
                "accepted_at": None,
                "acceptance_notes": "用于补盲区域，暂未完成勘点",
                "ai_enabled": False,
                "channel_code": "DEMO-CH-005",
                "preview_url": "",
                "playback_url": "",
                "last_seen_at": None,
                "notes": "[DEMO] 待勘点示例",
            },
            {
                "name": "[DEMO] 站房侧面补盲视角",
                "point_type": VideoPointType.STATION_ROOM.value,
                "protocol": VideoProtocol.GB28181.value,
                "access_method": VideoAccessMethod.OPERATOR_PLATFORM.value,
                "lifecycle_status": VideoLifecycleStatus.ACCEPTED.value,
                "status": VideoChannelStatus.OFFLINE.value,
                "vendor": "演示海康平台",
                "network_provider": "联通专网",
                "fixed_ip": "10.20.30.22",
                "install_location": "站房侧门外墙，覆盖药剂间和辅机区域",
                "surveyor_name": "环保管家A",
                "installer_name": "实施工程师B",
                "accepted_by": "运维主管",
                "accepted_at": datetime.utcnow() - timedelta(days=1),
                "acceptance_notes": "已验收，正在等待企业侧恢复视频服务",
                "ai_enabled": False,
                "channel_code": "DEMO-CH-006",
                "preview_url": "mock://preview/station-side",
                "playback_url": "mock://playback/station-side",
                "last_seen_at": datetime.utcnow() - timedelta(hours=8),
                "notes": "[DEMO] 已验收待恢复示例",
            },
        ]

        channels: list[VideoChannel] = []
        created_channels = 0
        for index, spec in enumerate(channel_templates):
            device = devices[index % len(devices)]
            channel = VideoChannel(
                org_id=device.org_id,
                device_id=device.id,
                device_mn=device.mn,
                name=spec["name"],
                point_type=spec["point_type"],
                protocol=spec["protocol"],
                access_method=spec["access_method"],
                lifecycle_status=spec["lifecycle_status"],
                status=spec["status"],
                vendor=spec["vendor"] or None,
                channel_code=spec["channel_code"],
                network_provider=spec["network_provider"] or None,
                fixed_ip=spec["fixed_ip"] or None,
                install_location=spec["install_location"],
                surveyor_name=spec["surveyor_name"] or None,
                installer_name=spec["installer_name"] or None,
                accepted_by=spec["accepted_by"] or None,
                accepted_at=spec["accepted_at"],
                acceptance_notes=spec["acceptance_notes"],
                preview_url=spec["preview_url"] or None,
                playback_url=spec["playback_url"] or None,
                ai_enabled=spec["ai_enabled"],
                notes=spec["notes"],
                last_seen_at=spec["last_seen_at"],
            )
            channel.device = device
            self.db.add(channel)
            channels.append(channel)
            created_channels += 1

        await self.db.flush()

        created_events = 0
        manual_event_specs = [
            {
                "channel": channels[0],
                "event_type": VideoEventType.MANUAL_SAMPLING.value,
                "source": VideoEventSource.INSPECTION.value,
                "level": VideoEventLevel.INFO.value,
                "status": VideoEventStatus.RESOLVED.value,
                "title": "[DEMO] 机位验收通过",
                "summary": "现场确认总排口、采样平台和周边作业面均已覆盖。",
                "snapshot_uri": "mock://snapshot/acceptance-pass.jpg",
                "clip_uri": "mock://clip/acceptance-pass.mp4",
                "occurred_at": datetime.utcnow() - timedelta(days=1, hours=2),
                "extra_data": {"demo": True, "scenario": "acceptance"},
            },
            {
                "channel": channels[1],
                "event_type": VideoEventType.CUSTOM.value,
                "source": VideoEventSource.INSPECTION.value,
                "level": VideoEventLevel.WARNING.value,
                "status": VideoEventStatus.PENDING.value,
                "title": "[DEMO] 预览地址待企业开放",
                "summary": "站房门禁视角已出图，等待企业侧开放预览/回放接口。",
                "snapshot_uri": "mock://snapshot/wait-preview.jpg",
                "clip_uri": "mock://clip/wait-preview.mp4",
                "occurred_at": datetime.utcnow() - timedelta(hours=6),
                "extra_data": {"demo": True, "scenario": "commissioning"},
            },
            {
                "channel": channels[4],
                "event_type": VideoEventType.CUSTOM.value,
                "source": VideoEventSource.MANUAL.value,
                "level": VideoEventLevel.INFO.value,
                "status": VideoEventStatus.ACKNOWLEDGED.value,
                "title": "[DEMO] 待勘点需求已登记",
                "summary": "已记录补盲需求，等待环保管家下一次到场确认机位和供电。",
                "snapshot_uri": "mock://snapshot/survey-plan.jpg",
                "clip_uri": None,
                "occurred_at": datetime.utcnow() - timedelta(hours=20),
                "extra_data": {"demo": True, "scenario": "survey"},
            },
        ]

        for spec in manual_event_specs:
            channel = spec["channel"]
            event = VideoEvent(
                org_id=channel.org_id,
                channel_id=channel.id,
                device_id=channel.device_id,
                device_mn=channel.device_mn,
                related_alarm_id=None,
                event_type=spec["event_type"],
                source=spec["source"],
                level=spec["level"],
                status=spec["status"],
                title=spec["title"],
                summary=spec["summary"],
                snapshot_uri=spec["snapshot_uri"],
                clip_uri=spec["clip_uri"],
                extra_data=serialize_video_extra_data(spec["extra_data"]),
                occurred_at=spec["occurred_at"],
            )
            event.channel = channel
            event.device = channel.device
            self.db.add(event)
            created_events += 1

        await self.db.flush()

        created_alarms = 0
        demo_alarm_ids: list[UUID] = []
        demo_alarms = [
            {
                "device": devices[0],
                "alarm_type": AlarmType.THRESHOLD.value,
                "level": AlarmLevel.CRITICAL.value,
                "status": AlarmStatus.PENDING.value,
                "pollutant_code": "w01018",
                "message": "[DEMO] COD 超标联动测试",
                "value": "86.50",
                "threshold": "60.00",
                "acknowledged_at": None,
                "resolved_at": None,
                "created_at": datetime.utcnow() - timedelta(minutes=40),
            },
            {
                "device": devices[min(1, len(devices) - 1)],
                "alarm_type": AlarmType.OFFLINE.value,
                "level": AlarmLevel.WARNING.value,
                "status": AlarmStatus.ACKNOWLEDGED.value,
                "pollutant_code": None,
                "message": "[DEMO] 视频联网链路离线联动测试",
                "value": None,
                "threshold": None,
                "acknowledged_at": datetime.utcnow() - timedelta(hours=2),
                "resolved_at": None,
                "created_at": datetime.utcnow() - timedelta(hours=3),
            },
            {
                "device": devices[0],
                "alarm_type": AlarmType.FLAG.value,
                "level": AlarmLevel.WARNING.value,
                "status": AlarmStatus.RESOLVED.value,
                "pollutant_code": "w21003",
                "message": "[DEMO] 数据标记异常联动测试",
                "value": "12.40",
                "threshold": "Flag: F",
                "acknowledged_at": datetime.utcnow() - timedelta(hours=9),
                "resolved_at": datetime.utcnow() - timedelta(hours=8),
                "created_at": datetime.utcnow() - timedelta(hours=10),
            },
        ]

        alarm_service = AlarmService(self.db)
        for spec in demo_alarms:
            alarm = Alarm(
                device_id=spec["device"].id,
                alarm_type=spec["alarm_type"],
                level=spec["level"],
                status=spec["status"],
                pollutant_code=spec["pollutant_code"],
                message=spec["message"],
                value=spec["value"],
                threshold=spec["threshold"],
                acknowledged_at=spec["acknowledged_at"],
                resolved_at=spec["resolved_at"],
                created_at=spec["created_at"],
            )
            self.db.add(alarm)
            await self.db.flush()
            await alarm_service.sync_video_events_with_alarm(alarm, device=spec["device"])
            demo_alarm_ids.append(alarm.id)
            created_alarms += 1

        final_event_result = await self.db.execute(
            select(func.count(VideoEvent.id)).where(
                VideoEvent.device_id.in_(device_ids),
                or_(
                    VideoEvent.title.like("[DEMO]%"),
                    VideoEvent.related_alarm_id.in_(demo_alarm_ids),
                ),
            )
        )
        total_demo_events = int(final_event_result.scalar() or created_events)

        return VideoDemoSeedResponse(
            success=True,
            message="演示视频台账与联动事件已生成，可直接用于页面和接口联调",
            org_id=target_org_id,
            device_count=len(devices),
            created_devices=created_devices,
            created_channels=created_channels,
            created_events=total_demo_events,
            created_alarms=created_alarms,
        )

    async def _verify_alarm_relation(self, *, related_alarm_id: UUID | None, device_id: UUID) -> None:
        if related_alarm_id is None:
            return

        result = await self.db.execute(select(Alarm).where(Alarm.id == related_alarm_id))
        alarm = result.scalar_one_or_none()
        if alarm is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="关联告警不存在")
        if alarm.device_id != device_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="关联告警与视频通道绑定的设备不一致",
            )

    def _channel_to_response(self, channel: VideoChannel) -> VideoChannelResponse:
        return VideoChannelResponse(
            id=channel.id,
            org_id=channel.org_id,
            device_id=channel.device_id,
            device_mn=channel.device_mn,
            device_name=channel.device.name if channel.device else None,
            name=channel.name,
            point_type=channel.point_type,
            protocol=channel.protocol,
            access_method=channel.access_method,
            lifecycle_status=channel.lifecycle_status,
            status=channel.status,
            vendor=channel.vendor,
            channel_code=channel.channel_code,
            network_provider=channel.network_provider,
            fixed_ip=channel.fixed_ip,
            install_location=channel.install_location,
            surveyor_name=channel.surveyor_name,
            installer_name=channel.installer_name,
            accepted_by=channel.accepted_by,
            accepted_at=channel.accepted_at,
            acceptance_notes=channel.acceptance_notes,
            preview_url=channel.preview_url,
            playback_url=channel.playback_url,
            ai_enabled=channel.ai_enabled,
            notes=channel.notes,
            last_seen_at=channel.last_seen_at,
            created_at=channel.created_at,
            updated_at=channel.updated_at,
        )

    def _event_to_response(self, event: VideoEvent) -> VideoEventResponse:
        return VideoEventResponse(
            id=event.id,
            org_id=event.org_id,
            channel_id=event.channel_id,
            channel_name=event.channel.name if event.channel else None,
            device_id=event.device_id,
            device_mn=event.device_mn,
            device_name=event.device.name if event.device else None,
            related_alarm_id=event.related_alarm_id,
            event_type=event.event_type,
            source=event.source,
            level=event.level,
            status=event.status,
            title=event.title,
            summary=event.summary,
            snapshot_uri=event.snapshot_uri,
            clip_uri=event.clip_uri,
            extra_data=deserialize_video_extra_data(event.extra_data),
            occurred_at=event.occurred_at,
            created_at=event.created_at,
            updated_at=event.updated_at,
        )

    async def list_channels(
        self,
        *,
        current_user: User,
        org_id: UUID | None = None,
        device_id: UUID | None = None,
        point_type: str | None = None,
        lifecycle_status: str | None = None,
        channel_status: str | None = None,
        ai_enabled: bool | None = None,
    ) -> list[VideoChannelResponse]:
        query = select(VideoChannel).options(selectinload(VideoChannel.device))

        if can_cross_tenant_read(current_user):
            if org_id:
                query = query.where(VideoChannel.org_id == org_id)
        else:
            if current_user.org_id is None:
                return []
            query = query.where(VideoChannel.org_id == current_user.org_id)

        if device_id:
            query = query.where(VideoChannel.device_id == device_id)
        if point_type:
            query = query.where(VideoChannel.point_type == point_type)
        if lifecycle_status:
            query = query.where(VideoChannel.lifecycle_status == lifecycle_status)
        if channel_status:
            query = query.where(VideoChannel.status == channel_status)
        if ai_enabled is not None:
            query = query.where(VideoChannel.ai_enabled == ai_enabled)

        query = query.order_by(VideoChannel.updated_at.desc(), VideoChannel.created_at.desc())
        result = await self.db.execute(query)
        channels = result.scalars().all()
        return [self._channel_to_response(channel) for channel in channels]

    async def get_channel(self, *, channel_id: UUID, current_user: User) -> VideoChannelResponse:
        channel = await self._resolve_channel(channel_id=channel_id, current_user=current_user)
        return self._channel_to_response(channel)

    async def create_channel(
        self,
        *,
        payload: VideoChannelCreate,
        current_user: User,
    ) -> VideoChannelResponse:
        device = await self._resolve_device(device_id=payload.device_id, current_user=current_user)

        channel = VideoChannel(
            org_id=device.org_id,
            device_id=device.id,
            device_mn=device.mn,
            name=payload.name,
            point_type=payload.point_type.value,
            protocol=payload.protocol.value,
            access_method=payload.access_method.value,
            lifecycle_status=payload.lifecycle_status.value,
            status=payload.status.value,
            vendor=payload.vendor,
            channel_code=payload.channel_code,
            network_provider=payload.network_provider,
            fixed_ip=payload.fixed_ip,
            install_location=payload.install_location,
            surveyor_name=payload.surveyor_name,
            installer_name=payload.installer_name,
            accepted_by=payload.accepted_by,
            accepted_at=payload.accepted_at,
            acceptance_notes=payload.acceptance_notes,
            preview_url=payload.preview_url,
            playback_url=payload.playback_url,
            ai_enabled=payload.ai_enabled,
            notes=payload.notes,
            last_seen_at=payload.last_seen_at,
        )
        channel.device = device
        self.db.add(channel)
        await self.db.flush()
        return self._channel_to_response(channel)

    async def update_channel(
        self,
        *,
        channel_id: UUID,
        payload: VideoChannelUpdate,
        current_user: User,
    ) -> VideoChannelResponse:
        channel = await self._resolve_channel(channel_id=channel_id, current_user=current_user)
        device = await self._resolve_device(device_id=payload.device_id, current_user=current_user)

        channel.org_id = device.org_id
        channel.device_id = device.id
        channel.device_mn = device.mn
        channel.name = payload.name
        channel.point_type = payload.point_type.value
        channel.protocol = payload.protocol.value
        channel.access_method = payload.access_method.value
        channel.lifecycle_status = payload.lifecycle_status.value
        channel.status = payload.status.value
        channel.vendor = payload.vendor
        channel.channel_code = payload.channel_code
        channel.network_provider = payload.network_provider
        channel.fixed_ip = payload.fixed_ip
        channel.install_location = payload.install_location
        channel.surveyor_name = payload.surveyor_name
        channel.installer_name = payload.installer_name
        channel.accepted_by = payload.accepted_by
        channel.accepted_at = payload.accepted_at
        channel.acceptance_notes = payload.acceptance_notes
        channel.preview_url = payload.preview_url
        channel.playback_url = payload.playback_url
        channel.ai_enabled = payload.ai_enabled
        channel.notes = payload.notes
        channel.last_seen_at = payload.last_seen_at
        channel.device = device
        await self.db.flush()
        return self._channel_to_response(channel)

    async def delete_channel(self, *, channel_id: UUID, current_user: User) -> None:
        channel = await self._resolve_channel(channel_id=channel_id, current_user=current_user)
        await self.db.delete(channel)

    async def list_events(
        self,
        *,
        current_user: User,
        org_id: UUID | None = None,
        device_id: UUID | None = None,
        channel_id: UUID | None = None,
        related_alarm_id: UUID | None = None,
        event_status: str | None = None,
        level: str | None = None,
        limit: int = 100,
    ) -> list[VideoEventResponse]:
        query = select(VideoEvent).options(
            selectinload(VideoEvent.channel),
            selectinload(VideoEvent.device),
        )

        if can_cross_tenant_read(current_user):
            if org_id:
                query = query.where(VideoEvent.org_id == org_id)
        else:
            if current_user.org_id is None:
                return []
            query = query.where(VideoEvent.org_id == current_user.org_id)

        if device_id:
            query = query.where(VideoEvent.device_id == device_id)
        if channel_id:
            query = query.where(VideoEvent.channel_id == channel_id)
        if related_alarm_id:
            query = query.where(VideoEvent.related_alarm_id == related_alarm_id)
        if event_status:
            query = query.where(VideoEvent.status == event_status)
        if level:
            query = query.where(VideoEvent.level == level)

        query = query.order_by(VideoEvent.occurred_at.desc(), VideoEvent.created_at.desc()).limit(limit)
        result = await self.db.execute(query)
        events = result.scalars().all()
        return [self._event_to_response(event) for event in events]

    async def create_event(
        self,
        *,
        payload: VideoEventCreate,
        current_user: User,
    ) -> VideoEventResponse:
        channel = await self._resolve_channel(channel_id=payload.channel_id, current_user=current_user)
        await self._verify_alarm_relation(related_alarm_id=payload.related_alarm_id, device_id=channel.device_id)

        event = VideoEvent(
            org_id=channel.org_id,
            channel_id=channel.id,
            device_id=channel.device_id,
            device_mn=channel.device_mn,
            related_alarm_id=payload.related_alarm_id,
            event_type=payload.event_type.value,
            source=payload.source.value,
            level=payload.level.value,
            status=VideoEventStatus.PENDING.value,
            title=payload.title,
            summary=payload.summary,
            snapshot_uri=payload.snapshot_uri,
            clip_uri=payload.clip_uri,
            extra_data=serialize_video_extra_data(payload.extra_data),
            occurred_at=payload.occurred_at or datetime.utcnow(),
        )
        event.channel = channel
        event.device = channel.device
        self.db.add(event)
        await self.db.flush()
        return self._event_to_response(event)

    async def acknowledge_event(self, *, event_id: UUID, current_user: User) -> VideoEventResponse:
        event = await self._resolve_event(event_id=event_id, current_user=current_user)
        event.status = VideoEventStatus.ACKNOWLEDGED.value
        await self.db.flush()
        return self._event_to_response(event)

    async def resolve_event(self, *, event_id: UUID, current_user: User) -> VideoEventResponse:
        event = await self._resolve_event(event_id=event_id, current_user=current_user)
        event.status = VideoEventStatus.RESOLVED.value
        await self.db.flush()
        return self._event_to_response(event)

    async def get_summary(self, *, current_user: User, org_id: UUID | None = None) -> VideoSummary:
        day_start = datetime.utcnow() - timedelta(hours=24)
        channel_query = select(
            func.count(VideoChannel.id).label("total_channels"),
            func.count()
            .filter(VideoChannel.lifecycle_status == VideoLifecycleStatus.PENDING_SURVEY.value)
            .label("pending_survey_channels"),
            func.count()
            .filter(VideoChannel.lifecycle_status == VideoLifecycleStatus.PENDING_INSTALLATION.value)
            .label("pending_installation_channels"),
            func.count()
            .filter(VideoChannel.lifecycle_status == VideoLifecycleStatus.PENDING_NETWORKING.value)
            .label("pending_networking_channels"),
            func.count()
            .filter(VideoChannel.lifecycle_status == VideoLifecycleStatus.COMMISSIONING.value)
            .label("commissioning_channels"),
            func.count()
            .filter(
                VideoChannel.lifecycle_status.in_(
                    [VideoLifecycleStatus.ACCEPTED.value, VideoLifecycleStatus.ACTIVE.value]
                )
            )
            .label("accepted_channels"),
            func.count().filter(VideoChannel.status == VideoChannelStatus.ONLINE.value).label("online_channels"),
            func.count().filter(VideoChannel.status == VideoChannelStatus.FAULT.value).label("fault_channels"),
            func.count().filter(VideoChannel.ai_enabled.is_(True)).label("ai_enabled_channels"),
        ).select_from(VideoChannel)

        event_query = select(
            func.count(VideoEvent.id).filter(VideoEvent.occurred_at >= day_start).label("today_events"),
            func.count().filter(VideoEvent.status != VideoEventStatus.RESOLVED.value).label("pending_events"),
            func.count().filter(VideoEvent.related_alarm_id.is_not(None)).label("linked_alarm_events"),
        ).select_from(VideoEvent)

        if can_cross_tenant_read(current_user):
            if org_id:
                channel_query = channel_query.where(VideoChannel.org_id == org_id)
                event_query = event_query.where(VideoEvent.org_id == org_id)
        else:
            if current_user.org_id is None:
                return VideoSummary()
            channel_query = channel_query.where(VideoChannel.org_id == current_user.org_id)
            event_query = event_query.where(VideoEvent.org_id == current_user.org_id)

        channel_result = await self.db.execute(channel_query)
        event_result = await self.db.execute(event_query)

        channel_row = channel_result.one()
        event_row = event_result.one()

        return VideoSummary(
            total_channels=channel_row.total_channels or 0,
            pending_survey_channels=channel_row.pending_survey_channels or 0,
            pending_installation_channels=channel_row.pending_installation_channels or 0,
            pending_networking_channels=channel_row.pending_networking_channels or 0,
            commissioning_channels=channel_row.commissioning_channels or 0,
            accepted_channels=channel_row.accepted_channels or 0,
            online_channels=channel_row.online_channels or 0,
            ai_enabled_channels=channel_row.ai_enabled_channels or 0,
            fault_channels=channel_row.fault_channels or 0,
            today_events=event_row.today_events or 0,
            pending_events=event_row.pending_events or 0,
            linked_alarm_events=event_row.linked_alarm_events or 0,
        )
