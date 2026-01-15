from __future__ import annotations

"""Report generation API endpoints."""

from datetime import datetime, date
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog
import io
import json

from app.db.postgres import get_db
from app.models.device import Device, ThresholdConfig
from app.models.user import User
from app.api.deps import get_current_active_user, can_cross_tenant_read
from app.core.masking import is_demo_viewer, mask_device_name
from app.services.report_service import get_report_service

router = APIRouter()
logger = structlog.get_logger()


class PollutantStats(BaseModel):
    """Statistics for a single pollutant."""

    pollutant_code: str
    pollutant_name: str
    unit: str
    min_value: float
    max_value: float
    avg_value: float
    std_value: float
    data_count: int
    exceedance_count: int
    threshold: float | None = None
    abnormal_flag_count: int = 0


class ReportSummary(BaseModel):
    """Summary statistics for the report."""

    total_records: int
    expected_records: int
    capture_rate: float
    exceedance_count: int


class ReportPeriod(BaseModel):
    """Time period for the report."""

    start: str
    end: str
    days: int


class ReportPreviewResponse(BaseModel):
    """Response model for report preview."""

    device_id: str
    device_name: str
    period: ReportPeriod
    pollutants: list[PollutantStats]
    summary: ReportSummary


class ReportRequest(BaseModel):
    """Request model for generating reports."""

    device_id: UUID = Field(..., description="Device UUID")
    report_type: str = Field("daily", pattern="^(daily|monthly)$", description="Report type: daily or monthly")
    report_date: date | None = Field(None, description="Date for daily report (YYYY-MM-DD)")
    year: int | None = Field(None, ge=2020, le=2100, description="Year for monthly report")
    month: int | None = Field(None, ge=1, le=12, description="Month for monthly report (1-12)")


async def _get_device_with_access(
    device_id: UUID,
    current_user: User,
    db: AsyncSession,
) -> Device:
    """Get device and verify user has access."""
    # Build query
    query = select(Device).where(Device.id == device_id)

    # Filter by organization if not cross-tenant staff
    if not can_cross_tenant_read(current_user):
        if not current_user.org_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User must belong to an organization",
            )
        query = query.where(Device.org_id == current_user.org_id)

    result = await db.execute(query)
    device = result.scalar_one_or_none()

    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found or access denied",
        )

    return device


def _parse_thresholds(device: Device) -> dict[str, float]:
    """Parse threshold configuration from device."""
    thresholds = {}
    if device.thresholds:
        try:
            config = ThresholdConfig.model_validate_json(device.thresholds)
            if config.enabled:
                for pollutant in config.pollutants:
                    if getattr(pollutant, "enabled", True) and pollutant.alarm_value > 0:
                        thresholds[pollutant.pollutant_code] = pollutant.alarm_value
        except Exception:
            pass
    return thresholds


def _parse_pollutant_codes(device: Device) -> list[str] | None:
    """Parse pollutant codes from device."""
    if device.pollutant_codes:
        return [code.strip() for code in device.pollutant_codes.split(",") if code.strip()]
    return None


@router.post("/preview", response_model=ReportPreviewResponse)
async def preview_report(
    request: ReportRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReportPreviewResponse:
    """
    Preview report statistics without generating a file.

    Returns key statistics that will be included in the report.
    """
    try:
        # Get device with access check
        device = await _get_device_with_access(request.device_id, current_user, db)
        device_name = device.name
        if is_demo_viewer(current_user) and can_cross_tenant_read(current_user):
            device_name = mask_device_name(device_id=str(device.id), mn=device.mn)
        device_name = device.name
        if is_demo_viewer(current_user) and can_cross_tenant_read(current_user):
            device_name = mask_device_name(device_id=str(device.id), mn=device.mn)

        # Parse thresholds and pollutant codes
        thresholds = _parse_thresholds(device)
        pollutant_codes = _parse_pollutant_codes(device)

        # Get report service (传入 db_session 以使用 MySQL)
        report_service = get_report_service(db)

        # Generate statistics based on report type
        if request.report_type == "daily":
            if not request.report_date:
                request.report_date = date.today()

            stats = await report_service.generate_daily_report(
                device_id=device.mn,
                device_name=device_name,
                report_date=request.report_date,
                pollutant_codes=pollutant_codes,
                thresholds=thresholds,
            )
        else:  # monthly
            if not request.year or not request.month:
                today = date.today()
                request.year = today.year
                request.month = today.month

            stats = await report_service.generate_monthly_report(
                device_id=device.mn,
                device_name=device_name,
                year=request.year,
                month=request.month,
                pollutant_codes=pollutant_codes,
                thresholds=thresholds,
            )

        logger.info(
            "Report preview generated",
            device_id=str(device.id),
            report_type=request.report_type,
        )

        return ReportPreviewResponse(**stats)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to preview report", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate report preview",
        )


@router.post("/download")
async def download_report(
    request: ReportRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    format: str = Query("excel", pattern="^(excel|pdf)$"),
) -> StreamingResponse:
    """
    Download report as Excel or PDF file.

    Args:
        request: Report parameters
        format: Output format - 'excel' or 'pdf'

    Returns:
        StreamingResponse with file content
    """
    try:
        # Get device with access check
        device = await _get_device_with_access(request.device_id, current_user, db)

        # Parse thresholds and pollutant codes
        thresholds = _parse_thresholds(device)
        pollutant_codes = _parse_pollutant_codes(device)

        # Calculate time range
        if request.report_type == "daily":
            if not request.report_date:
                request.report_date = date.today()
            start_time = datetime.combine(request.report_date, datetime.min.time())
            end_time = datetime.combine(request.report_date, datetime.max.time())
            date_str = request.report_date.strftime("%Y%m%d")
        else:  # monthly
            if not request.year or not request.month:
                today = date.today()
                request.year = today.year
                request.month = today.month
            start_time = datetime(request.year, request.month, 1)
            if request.month == 12:
                end_time = datetime(request.year + 1, 1, 1)
            else:
                end_time = datetime(request.year, request.month + 1, 1)
            date_str = f"{request.year}{request.month:02d}"

        # Get report service (传入 db_session 以使用 MySQL)
        report_service = get_report_service(db)

        # Generate report file
        if format == "excel":
            file_content = await report_service.generate_excel_report(
                device_id=device.mn,
                device_name=device_name,
                start_time=start_time,
                end_time=end_time,
                report_type=request.report_type,
                pollutant_codes=pollutant_codes,
                thresholds=thresholds,
            )
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            extension = "xlsx"
        else:  # pdf
            file_content = await report_service.generate_pdf_report(
                device_id=device.mn,
                device_name=device_name,
                start_time=start_time,
                end_time=end_time,
                report_type=request.report_type,
                pollutant_codes=pollutant_codes,
                thresholds=thresholds,
            )
            media_type = "application/pdf"
            extension = "pdf"

        # Generate filename
        report_type_cn = "日报" if request.report_type == "daily" else "月报"
        filename = f"{device_name}_{report_type_cn}_{date_str}.{extension}"
        # URL encode the filename for Content-Disposition header
        encoded_filename = quote(filename, safe='')

        logger.info(
            "Report downloaded",
            device_id=str(device.id),
            report_type=request.report_type,
            format=format,
        )

        # Return file as streaming response
        return StreamingResponse(
            io.BytesIO(file_content),
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
                "Content-Length": str(len(file_content)),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to download report", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate report file",
        )


@router.get("/devices")
async def list_devices_for_reports(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    """
    List devices available for report generation.

    Returns a simplified list of devices with id, name, and pollutant codes.
    """
    try:
        # Build query
        query = select(Device)

        # Filter by organization if not cross-tenant staff
        if not can_cross_tenant_read(current_user):
            if not current_user.org_id:
                return []
            query = query.where(Device.org_id == current_user.org_id)

        result = await db.execute(query)
        devices = result.scalars().all()

        mask = is_demo_viewer(current_user) and can_cross_tenant_read(current_user)
        # Return simplified device list
        return [
            {
                "id": str(device.id),
                "mn": device.mn,
                "name": (mask_device_name(device_id=str(device.id), mn=device.mn) if mask else device.name),
                "device_type": device.device_type,
                "pollutant_codes": device.pollutant_codes.split(",") if device.pollutant_codes else [],
            }
            for device in devices
        ]

    except Exception as e:
        logger.error("Failed to list devices for reports", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list devices",
        )
