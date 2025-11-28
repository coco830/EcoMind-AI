"""Monitoring data API endpoints."""

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.db.postgres import get_db
from app.db.tdengine_client import get_tdengine_client
from app.models.monitoring import MonitoringDataResponse, MonitoringDataStats
from app.models.device import Device
from app.models.user import User
from app.api.deps import get_current_active_user

router = APIRouter()
logger = structlog.get_logger()


async def _verify_device_access(
    device_id: str,
    current_user: User,
    db: AsyncSession,
) -> None:
    """Verify user has access to the device by MN."""
    if current_user.is_superadmin:
        return

    if not current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User must belong to an organization",
        )

    # Check if device belongs to user's organization
    result = await db.execute(
        select(Device).where(
            Device.mn == device_id,
            Device.org_id == current_user.org_id,
        )
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this device data",
        )


async def _get_accessible_device_ids(
    current_user: User,
    db: AsyncSession,
) -> list[str] | None:
    """Get list of device MNs accessible to user. Returns None for superadmins (no filter)."""
    if current_user.is_superadmin:
        return None

    if not current_user.org_id:
        return []

    result = await db.execute(
        select(Device.mn).where(Device.org_id == current_user.org_id)
    )
    return [row[0] for row in result.fetchall()]


class DataQueryParams(BaseModel):
    """Query parameters for monitoring data."""

    device_id: str | None = None
    pollutant_code: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    limit: int = 1000


@router.get("", response_model=list[MonitoringDataResponse])
async def query_monitoring_data(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    device_id: str | None = None,
    pollutant_code: str | None = Query(
        None,
        description="污染物代码 (留空表示获取所有污染物数据)",
    ),
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = Query(1000, ge=1, le=10000),
) -> list[MonitoringDataResponse]:
    """Query monitoring data with filters from TDengine. Filtered by organization."""
    try:
        # Verify device access if specific device requested
        if device_id:
            await _verify_device_access(device_id, current_user, db)

        client = get_tdengine_client()

        # If no specific device, filter by accessible devices
        query_device_id = device_id
        if not device_id and not current_user.is_superadmin:
            accessible_ids = await _get_accessible_device_ids(current_user, db)
            if not accessible_ids:
                return []  # User has no accessible devices

        # Query data from TDengine
        results = await client.query_monitoring_data(
            device_id=query_device_id,
            pollutant_code=pollutant_code,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )

        # Filter results by accessible devices if needed
        if not device_id and not current_user.is_superadmin:
            accessible_ids = await _get_accessible_device_ids(current_user, db)
            if accessible_ids is not None:
                results = [r for r in results if r['device_id'] in accessible_ids]

        # Convert results to response model
        responses = []
        for row in results:
            responses.append(MonitoringDataResponse(
                ts=row['ts'].isoformat() if isinstance(row['ts'], datetime) else row['ts'],
                device_id=row['device_id'],
                pollutant_code=row['pollutant_code'],
                value=row['value'],
                flag=row['flag'],
                status=row['status']
            ))

        logger.info("Retrieved monitoring data", count=len(responses))
        return responses

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to query monitoring data", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve monitoring data")


@router.get("/latest")
async def get_latest_data(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    device_id: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
) -> list[MonitoringDataResponse]:
    """Get latest monitoring data from TDengine. Filtered by organization."""
    try:
        # Verify device access if specific device requested
        if device_id:
            await _verify_device_access(device_id, current_user, db)

        client = get_tdengine_client()

        # Get device IDs to query
        query_device_ids = [device_id] if device_id else None
        if not device_id and not current_user.is_superadmin:
            query_device_ids = await _get_accessible_device_ids(current_user, db)
            if not query_device_ids:
                return []

        # Get latest values
        results = await client.get_latest_values(
            device_ids=query_device_ids,
            limit=limit
        )

        # Convert results to response model
        responses = []
        for row in results:
            responses.append(MonitoringDataResponse(
                ts=row['ts'].isoformat() if isinstance(row['ts'], datetime) else row['ts'],
                device_id=row['device_id'],
                pollutant_code=row['pollutant_code'],
                value=row['value'],
                flag=row['flag'],
                status=row['status']
            ))

        logger.info("Retrieved latest data", count=len(responses))
        return responses

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get latest data", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve latest data")


@router.get("/realtime/{device_id}")
async def get_realtime_data(
    device_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[MonitoringDataResponse]:
    """Get real-time data for a specific device (last 5 minutes). Access controlled by organization."""
    try:
        # Verify device access
        await _verify_device_access(device_id, current_user, db)

        client = get_tdengine_client()

        # Calculate time range for real-time data (last 5 minutes)
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=5)

        # Query recent data from TDengine
        results = await client.query_monitoring_data(
            device_id=device_id,
            start_time=start_time,
            end_time=end_time,
            limit=300  # 5 minutes * 60 seconds = 300 data points max
        )

        # Convert results to response model
        responses = []
        for row in results:
            responses.append(MonitoringDataResponse(
                ts=row['ts'].isoformat() if isinstance(row['ts'], datetime) else row['ts'],
                device_id=row['device_id'],
                pollutant_code=row['pollutant_code'],
                value=row['value'],
                flag=row['flag'],
                status=row['status']
            ))

        logger.info("Retrieved real-time data", device_id=device_id, count=len(responses))
        return responses

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get real-time data", device_id=device_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve real-time data")


@router.get("/history/{device_id}")
async def get_historical_data(
    device_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    pollutant_code: str | None = Query(
        None,
        description="污染物代码 (留空表示获取所有污染物数据)",
    ),
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = Query(1000, ge=1, le=10000),
) -> list[MonitoringDataResponse]:
    """Get historical data for a specific device. Access controlled by organization."""
    try:
        # Verify device access
        await _verify_device_access(device_id, current_user, db)

        client = get_tdengine_client()

        # Query historical data from TDengine
        results = await client.query_monitoring_data(
            device_id=device_id,
            pollutant_code=pollutant_code,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )

        # Convert results to response model
        responses = []
        for row in results:
            responses.append(MonitoringDataResponse(
                ts=row['ts'].isoformat() if isinstance(row['ts'], datetime) else row['ts'],
                device_id=row['device_id'],
                pollutant_code=row['pollutant_code'],
                value=row['value'],
                flag=row['flag'],
                status=row['status']
            ))

        logger.info(
            "Retrieved historical data",
            device_id=device_id,
            pollutant_code=pollutant_code,
            count=len(responses)
        )
        return responses

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get historical data",
            device_id=device_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve historical data")


@router.get("/stats/{device_id}")
async def get_data_stats(
    device_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    pollutant_code: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> list[dict]:
    """Get statistics for device monitoring data. Access controlled by organization."""
    try:
        # Verify device access
        await _verify_device_access(device_id, current_user, db)

        client = get_tdengine_client()

        # Use the safe statistics method from TDengine client
        stats = await client.get_statistics(
            device_id=device_id,
            pollutant_code=pollutant_code,
            start_time=start_time,
            end_time=end_time
        )

        if stats:
            logger.info("Retrieved statistics", device_id=device_id)
            return [stats]

        return []

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get data statistics", device_id=device_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")


@router.get("/export")
async def export_data(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    device_id: str,
    pollutant_code: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    format: str = Query("json", regex="^(json|csv)$"),
) -> dict:
    """Export monitoring data (returns download URL or data). Access controlled by organization."""
    try:
        # Verify device access
        await _verify_device_access(device_id, current_user, db)

        client = get_tdengine_client()

        # Query data from TDengine
        results = await client.query_monitoring_data(
            device_id=device_id,
            pollutant_code=pollutant_code,
            start_time=start_time,
            end_time=end_time,
            limit=10000  # Larger limit for export
        )

        if format == "csv":
            # Generate CSV format
            import csv
            import io

            output = io.StringIO()
            if results:
                writer = csv.DictWriter(
                    output,
                    fieldnames=['ts', 'device_id', 'pollutant_code', 'value', 'flag', 'status']
                )
                writer.writeheader()
                for row in results:
                    # Convert datetime to string if necessary
                    if isinstance(row['ts'], datetime):
                        row['ts'] = row['ts'].isoformat()
                    writer.writerow(row)

            csv_data = output.getvalue()
            return {"data": csv_data, "format": "csv"}

        else:  # JSON format
            # Convert datetime objects to strings
            json_data = []
            for row in results:
                json_row = dict(row)
                if isinstance(json_row.get('ts'), datetime):
                    json_row['ts'] = json_row['ts'].isoformat()
                json_data.append(json_row)

            return {"data": json_data, "format": "json"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to export data", device_id=device_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to export data")
