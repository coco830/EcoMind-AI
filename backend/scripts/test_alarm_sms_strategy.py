#!/usr/bin/env python3
"""Test script for Tencent SMS 1+12 frequency control strategy."""

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

from app.db.postgres import AsyncSessionLocal, init_db
from app.models.alarm import Alarm, AlarmType
from app.models.device import Device, PollutantThreshold
from app.services.alarm_service import AlarmService


def utc_now() -> datetime:
    """Timezone-aware UTC converted to naive timestamp (matches DB usage)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def run_scenario() -> None:
    await init_db()
    async with AsyncSessionLocal() as session:
        device_result = await session.execute(
            select(Device).options(selectinload(Device.organization)).limit(1)
        )
        device = device_result.scalar_one_or_none()
        if device is None:
            print("❌ 未找到任何设备，无法测试。")
            return

        # Ensure organization contact phone exists for logging
        if device.organization and not device.organization.contact_phone:
            device.organization.contact_phone = "13800138000"
            await session.commit()
            print("ℹ️ 已为组织填写默认联系人手机号 13800138000（仅测试打印日志）。")

        # Clean previous alarms for deterministic results
        await session.execute(
            delete(Alarm).where(
                Alarm.device_id == device.id,
                Alarm.alarm_type == AlarmType.THRESHOLD.value,
                Alarm.pollutant_code == "w01018",
            )
        )
        await session.commit()

        service = AlarmService(db=session)
        threshold = PollutantThreshold(
            pollutant_code="w01018",
            pollutant_name="COD",
            warning_value=80.0,
            alarm_value=100.0,
            unit="mg/L",
        )

        print("\n=== 场景 A：触发新的 CRITICAL 告警，预期发送第 1 条短信 ===")
        alarm = await service.create_threshold_alarm(
            device_id=device.id,
            device_mn=device.mn,
            pollutant_code="w01018",
            value=135.5,
            threshold=threshold,
            is_warning=False,
        )
        await session.refresh(alarm)
        print(f"短信发送次数: {alarm.sms_sent_count}, 最后一次: {alarm.last_sms_time}")

        print("\n=== 场景 B：仅过去 1 小时，同一告警持续，预期不发送 ===")
        alarm.last_sms_time = utc_now() - timedelta(hours=1)
        await session.commit()
        alarm = await service.create_threshold_alarm(
            device_id=device.id,
            device_mn=device.mn,
            pollutant_code="w01018",
            value=130.0,
            threshold=threshold,
            is_warning=False,
        )
        await session.refresh(alarm)
        print(f"短信发送次数: {alarm.sms_sent_count}, 最后一次: {alarm.last_sms_time}")

        print("\n=== 场景 C：过去 13 小时，预期发送第 2 条短信 ===")
        alarm.last_sms_time = utc_now() - timedelta(hours=13)
        alarm.sms_sent_count = 1
        await session.commit()
        alarm = await service.create_threshold_alarm(
            device_id=device.id,
            device_mn=device.mn,
            pollutant_code="w01018",
            value=128.0,
            threshold=threshold,
            is_warning=False,
        )
        await session.refresh(alarm)
        print(f"短信发送次数: {alarm.sms_sent_count}, 最后一次: {alarm.last_sms_time}")

        print("\n=== 场景 D：已发送 2 条短信，即使过去 25 小时也不再发送 ===")
        alarm.last_sms_time = utc_now() - timedelta(hours=25)
        await session.commit()
        alarm = await service.create_threshold_alarm(
            device_id=device.id,
            device_mn=device.mn,
            pollutant_code="w01018",
            value=126.0,
            threshold=threshold,
            is_warning=False,
        )
        await session.refresh(alarm)
        print(f"短信发送次数: {alarm.sms_sent_count}, 最后一次: {alarm.last_sms_time}")


if __name__ == "__main__":
    asyncio.run(run_scenario())
