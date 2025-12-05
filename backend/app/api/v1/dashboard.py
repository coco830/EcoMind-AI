"""Dashboard API endpoints - public endpoints for dashboard display."""

from datetime import datetime, timedelta
import random

from fastapi import APIRouter, Query, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.db.postgres import get_db
from app.db.tdengine_client import get_tdengine_client
from app.models.monitoring import MonitoringDataResponse
from app.models.device import Device, DeviceStatus
from app.models.alarm import Alarm, AlarmStatus
from app.models.user import User
from app.api.deps import get_current_active_user
from typing import Annotated

router = APIRouter()
logger = structlog.get_logger()


# Demo data configuration
# 污水监测数采仪常用指标: COD、氨氮、pH、总磷、总氮、TOC、温度、流量
DEMO_POLLUTANTS = {
    # 常用指标 (与前端 COMMON_POLLUTANTS 保持一致)
    "w01018": {"name": "COD", "base": 45, "std": 12, "limit": 60},
    "w21003": {"name": "氨氮", "base": 3.5, "std": 1.2, "limit": 8},
    "w01001": {"name": "pH", "base": 7.2, "std": 0.25},
    "w21011": {"name": "总磷", "base": 0.4, "std": 0.12, "limit": 1},
    "w21001": {"name": "总氮", "base": 12, "std": 3, "limit": 20},
    "w01020": {"name": "TOC", "base": 15, "std": 5, "limit": 30},
    "w01010": {"name": "水温", "base": 25, "std": 3},
    "w00000": {"name": "瞬时流量", "base": 50, "std": 15},
    # 一类重金属
    "w20111": {"name": "总汞", "base": 0.00008, "std": 0.00002, "limit": 0.001},
    "w20115": {"name": "总镉", "base": 0.008, "std": 0.002, "limit": 0.01},
    "w20117": {"name": "六价铬", "base": 0.03, "std": 0.01, "limit": 0.05},
    "w20119": {"name": "总砷", "base": 0.02, "std": 0.008, "limit": 0.1},
    "w20120": {"name": "总铅", "base": 0.05, "std": 0.015, "limit": 0.1},
    # 二类重金属
    "w20121": {"name": "总镍", "base": 0.3, "std": 0.1, "limit": 0.5},
    "w20122": {"name": "总铜", "base": 0.25, "std": 0.08, "limit": 0.5},
    "w20123": {"name": "总锌", "base": 0.8, "std": 0.2, "limit": 1.5},
    "w20116": {"name": "总铬", "base": 0.6, "std": 0.2, "limit": 1.0},
    "w20124": {"name": "总锰", "base": 0.5, "std": 0.15, "limit": 2.0},
    # 毒性阴离子
    "w21016": {"name": "氰化物", "base": 0.15, "std": 0.06, "limit": 0.3},
}


class DashboardStats(BaseModel):
    """Dashboard statistics."""
    device_count: int = 0
    online_count: int = 0
    offline_count: int = 0
    alarm_count: int = 0
    data_count: int = 0
    pending_alarms: int = 0


class TrendDataPoint(BaseModel):
    """Single data point for trend chart."""
    ts: str
    value: float
    pollutant_code: str


@router.get("/stats")
async def get_dashboard_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> DashboardStats:
    """
    Get dashboard statistics for the current user's organization.

    Returns aggregated stats filtered by user's org_id for multi-tenant isolation.
    """
    try:
        # Superadmin can see all data, regular users only see their org's data
        org_id = None if current_user.is_superadmin else current_user.org_id

        # Build base query with org filter
        device_base_query = select(func.count(Device.id))
        if org_id:
            device_base_query = device_base_query.where(Device.org_id == org_id)

        # Query device counts
        device_count_result = await db.execute(device_base_query)
        device_count = device_count_result.scalar() or 0

        online_query = select(func.count(Device.id)).where(Device.status == DeviceStatus.ONLINE)
        if org_id:
            online_query = online_query.where(Device.org_id == org_id)
        online_count_result = await db.execute(online_query)
        online_count = online_count_result.scalar() or 0

        offline_count = device_count - online_count

        # Query alarm counts - devices with issues in user's org
        alarm_query = select(func.count(Device.id)).where(
            Device.status.in_([DeviceStatus.OFFLINE, DeviceStatus.WARNING])
        )
        if org_id:
            alarm_query = alarm_query.where(Device.org_id == org_id)
        alarm_device_result = await db.execute(alarm_query)
        alarm_count = alarm_device_result.scalar() or 0

        # Pending alarms count - only for devices in user's org (or all for superadmin)
        if org_id:
            # Get device IDs for user's org first
            device_ids_query = select(Device.id).where(Device.org_id == org_id)
            device_ids_result = await db.execute(device_ids_query)
            device_ids = [row[0] for row in device_ids_result.fetchall()]

            if device_ids:
                pending_alarms_result = await db.execute(
                    select(func.count(Alarm.id)).where(
                        Alarm.status == AlarmStatus.PENDING,
                        Alarm.device_id.in_(device_ids)
                    )
                )
                pending_alarms = pending_alarms_result.scalar() or 0
            else:
                pending_alarms = 0
        else:
            # Superadmin sees all pending alarms
            pending_alarms_result = await db.execute(
                select(func.count(Alarm.id)).where(Alarm.status == AlarmStatus.PENDING)
            )
            pending_alarms = pending_alarms_result.scalar() or 0

        # Get data count from TDengine (last 24 hours) - filtered by org's devices
        data_count = 0
        try:
            client = get_tdengine_client()
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=24)

            # Superadmin sees all data, regular users only see their org's devices
            if org_id:
                device_mns_query = select(Device.mn).where(Device.org_id == org_id)
                device_mns_result = await db.execute(device_mns_query)
                device_mns = [row[0] for row in device_mns_result.fetchall()]

                # Query data for each device
                for mn in device_mns:
                    results = await client.query_monitoring_data(
                        device_id=mn,
                        start_time=start_time,
                        end_time=end_time,
                        limit=10000
                    )
                    data_count += len(results)
            else:
                # Superadmin: query all data
                results = await client.query_monitoring_data(
                    start_time=start_time,
                    end_time=end_time,
                    limit=10000
                )
                data_count = len(results)
        except Exception as e:
            logger.warning("Failed to get data count from TDengine", error=str(e))

        return DashboardStats(
            device_count=device_count,
            online_count=online_count,
            offline_count=offline_count,
            alarm_count=alarm_count,
            data_count=data_count,
            pending_alarms=pending_alarms
        )

    except Exception as e:
        logger.error("Failed to get dashboard stats", error=str(e))
        # Return empty stats on error instead of failing
        return DashboardStats()


@router.get("/trend")
async def get_trend_data(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    device_id: str | None = None,
    pollutant_code: str = Query("w01018", description="污染物代码 (默认: w01018/COD)"),
    hours: int = Query(24, ge=1, le=168),  # 1 hour to 7 days
    limit: int = Query(100, ge=1, le=1000),
) -> list[MonitoringDataResponse]:
    """
    Get trend data for charts - requires authentication.

    Returns time-series data for the specified device and time range.
    Only returns data for devices belonging to user's organization.
    """
    try:
        # Superadmin can see all data, regular users only see their org's data
        org_id = None if current_user.is_superadmin else current_user.org_id

        # Verify device belongs to user's organization if device_id is specified (skip for superadmin)
        if device_id and org_id:
            device_result = await db.execute(
                select(Device).where(Device.mn == device_id, Device.org_id == org_id)
            )
            if not device_result.scalar_one_or_none():
                # Device not found or doesn't belong to user's org
                return []

        # If no device_id specified, get all device MNs for user's org (skip for superadmin)
        allowed_device_ids = None
        if org_id and not device_id:
            device_mns_query = select(Device.mn).where(Device.org_id == org_id)
            device_mns_result = await db.execute(device_mns_query)
            allowed_device_ids = [row[0] for row in device_mns_result.fetchall()]
            if not allowed_device_ids:
                return []

        client = get_tdengine_client()

        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)

        # Query data from TDengine
        results = await client.query_monitoring_data(
            device_id=device_id,
            pollutant_code=pollutant_code,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )

        # Filter results by allowed devices if needed
        if allowed_device_ids:
            results = [r for r in results if r['device_id'] in allowed_device_ids]

        # Convert results to response model
        responses = []
        for row in results:
            responses.append(MonitoringDataResponse(
                ts=row['ts'].isoformat() if isinstance(row['ts'], datetime) else str(row['ts']),
                device_id=row['device_id'],
                pollutant_code=row['pollutant_code'],
                value=row['value'],
                flag=row['flag'],
                status=row['status']
            ))

        logger.info("Retrieved trend data", count=len(responses), org_id=str(org_id))
        return responses

    except Exception as e:
        logger.error("Failed to get trend data", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve trend data")


@router.get("/device-pollutants")
async def get_device_pollutants(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    device_id: str = Query(..., description="设备ID"),
    hours: int = Query(24, ge=1, le=168, description="查询时间范围"),
) -> list[MonitoringDataResponse]:
    """
    获取设备实际上报的所有污染物最新数据 - requires authentication.

    返回设备在指定时间范围内上报的所有污染物的最新值。
    用于"设备实际"模式显示企业数采仪实际采集的指标。
    Only returns data for devices belonging to user's organization.
    """
    try:
        # Superadmin can see all data, regular users only see their org's data
        org_id = None if current_user.is_superadmin else current_user.org_id

        # Verify device belongs to user's organization (skip for superadmin)
        if org_id:
            device_result = await db.execute(
                select(Device).where(Device.mn == device_id, Device.org_id == org_id)
            )
            if not device_result.scalar_one_or_none():
                # Device not found or doesn't belong to user's org
                return []

        client = get_tdengine_client()

        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)

        # Query all data for this device (no pollutant_code filter)
        results = await client.query_monitoring_data(
            device_id=device_id,
            pollutant_code=None,  # Get all pollutants
            start_time=start_time,
            end_time=end_time,
            limit=5000,  # Higher limit to get all pollutants
        )

        # Group by pollutant and get latest value for each
        latest_by_pollutant: dict[str, dict] = {}
        for row in results:
            code = row['pollutant_code']
            ts = row['ts']
            if code not in latest_by_pollutant or ts > latest_by_pollutant[code]['ts']:
                latest_by_pollutant[code] = row

        # Convert to response format
        responses = []
        for row in latest_by_pollutant.values():
            responses.append(MonitoringDataResponse(
                ts=row['ts'].isoformat() if isinstance(row['ts'], datetime) else str(row['ts']),
                device_id=row['device_id'],
                pollutant_code=row['pollutant_code'],
                value=row['value'],
                flag=row['flag'],
                status=row['status']
            ))

        logger.info("Retrieved device pollutants", device_id=device_id, pollutant_count=len(responses), org_id=str(org_id))
        return responses

    except Exception as e:
        logger.error("Failed to get device pollutants", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve device pollutants")


@router.get("/latest")
async def get_latest_monitoring_data(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    pollutant_code: str | None = Query(None, description="可选污染物代码过滤"),
    limit: int = Query(50, ge=1, le=200),
) -> list[MonitoringDataResponse]:
    """
    Get latest monitoring data - requires authentication.

    Returns the most recent data points for devices in user's organization.
    """
    try:
        # Superadmin can see all data, regular users only see their org's data
        org_id = None if current_user.is_superadmin else current_user.org_id

        # Get device MNs for user's org (superadmin sees all)
        allowed_device_ids = None
        if org_id:
            device_mns_query = select(Device.mn).where(Device.org_id == org_id)
            device_mns_result = await db.execute(device_mns_query)
            allowed_device_ids = [row[0] for row in device_mns_result.fetchall()]
            if not allowed_device_ids:
                return []

        client = get_tdengine_client()

        # Get latest values
        results = await client.get_latest_values(
            limit=limit,
            pollutant_code=pollutant_code,
        )

        # Filter by allowed devices (superadmin sees all)
        if allowed_device_ids:
            results = [r for r in results if r['device_id'] in allowed_device_ids]

        # Convert results to response model
        responses = []
        for row in results:
            responses.append(MonitoringDataResponse(
                ts=row['ts'].isoformat() if isinstance(row['ts'], datetime) else str(row['ts']),
                device_id=row['device_id'],
                pollutant_code=row['pollutant_code'],
                value=row['value'],
                flag=row['flag'],
                status=row['status']
            ))

        logger.info("Retrieved latest data", count=len(responses), org_id=str(org_id))
        return responses

    except Exception as e:
        logger.error("Failed to get latest data", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve latest data")


@router.get("/realtime")
async def get_realtime_data(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    pollutant_code: str | None = Query(None, description="可选污染物代码过滤"),
    limit: int = Query(100, ge=1, le=500),
) -> list[MonitoringDataResponse]:
    """
    Get real-time data stream - requires authentication.

    Returns the most recent data points for devices in user's organization.
    """
    try:
        # Superadmin can see all data, regular users only see their org's data
        org_id = None if current_user.is_superadmin else current_user.org_id

        # Get device MNs for user's org (superadmin sees all)
        allowed_device_ids = None
        if org_id:
            device_mns_query = select(Device.mn).where(Device.org_id == org_id)
            device_mns_result = await db.execute(device_mns_query)
            allowed_device_ids = [row[0] for row in device_mns_result.fetchall()]
            if not allowed_device_ids:
                return []

        client = get_tdengine_client()

        # Get data from last 5 minutes
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=5)

        results = await client.query_monitoring_data(
            start_time=start_time,
            end_time=end_time,
            pollutant_code=pollutant_code,
            limit=limit
        )

        # Filter by allowed devices (superadmin sees all)
        if allowed_device_ids:
            results = [r for r in results if r['device_id'] in allowed_device_ids]

        # Convert results to response model
        responses = []
        for row in results:
            responses.append(MonitoringDataResponse(
                ts=row['ts'].isoformat() if isinstance(row['ts'], datetime) else str(row['ts']),
                device_id=row['device_id'],
                pollutant_code=row['pollutant_code'],
                value=row['value'],
                flag=row['flag'],
                status=row['status']
            ))

        logger.info("Retrieved real-time data", count=len(responses), org_id=str(org_id))
        return responses

    except Exception as e:
        logger.error("Failed to get real-time data", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve real-time data")


class DemoDataResponse(BaseModel):
    """Response for demo data injection."""
    success: bool
    message: str
    data_points: int
    pollutants: int
    anomalies: int


@router.post("/demo/inject")
async def inject_demo_data(
    device_id: str = Query("BEIJING001", description="设备ID"),
    hours: int = Query(24, ge=1, le=72, description="生成多少小时的历史数据"),
    interval_minutes: int = Query(15, ge=5, le=60, description="数据间隔(分钟)"),
    include_anomalies: bool = Query(True, description="是否包含异常数据"),
) -> DemoDataResponse:
    """
    注入演示数据 - 用于测试和演示 (仅在 Mock 模式下有效)

    生成包含常用指标、重金属、异常数据的模拟监测数据。
    """
    try:
        client = get_tdengine_client()
        org_id = "00000000-0000-0000-0000-000000000001"

        now = datetime.now()
        total_points = (hours * 60) // interval_minutes
        data_count = 0
        anomaly_count = 0

        # COD趋势参数
        trend_start = total_points // 3
        trend_peak = trend_start + total_points // 6
        trend_end = trend_peak + total_points // 6

        for i in range(total_points):
            timestamp = now - timedelta(minutes=(total_points - i - 1) * interval_minutes)

            # COD趋势
            if trend_start <= i < trend_peak:
                progress = (i - trend_start) / (trend_peak - trend_start)
                cod_trend = 25 * progress
            elif trend_peak <= i < trend_end:
                progress = (i - trend_peak) / (trend_end - trend_peak)
                cod_trend = 25 * (1 - progress)
            else:
                cod_trend = 0

            for code, config in DEMO_POLLUTANTS.items():
                trend = cod_trend if code == "w01018" else 0
                value = config["base"] + random.gauss(0, config["std"]) + trend
                value = max(0, value)

                # 判断是否超标
                flag = "N"
                if "limit" in config and value > config["limit"]:
                    flag = "B"
                    anomaly_count += 1

                # 随机触发异常
                if include_anomalies and random.random() < 0.03:
                    if "limit" in config:
                        value = config["limit"] * random.uniform(1.1, 1.4)
                        flag = "B"
                        anomaly_count += 1

                # 插入数据
                await client.insert_monitoring_data(
                    device_id=device_id,
                    org_id=org_id,
                    pollutant_code=code,
                    value=round(value, 6),
                    flag=flag,
                    timestamp=timestamp,
                )
                data_count += 1

        logger.info(
            "Demo data injected",
            device_id=device_id,
            hours=hours,
            data_points=data_count,
            anomalies=anomaly_count,
        )

        return DemoDataResponse(
            success=True,
            message=f"成功注入 {hours} 小时的演示数据",
            data_points=data_count,
            pollutants=len(DEMO_POLLUTANTS),
            anomalies=anomaly_count,
        )

    except Exception as e:
        logger.error("Failed to inject demo data", error=str(e))
        raise HTTPException(status_code=500, detail=f"注入演示数据失败: {str(e)}")
