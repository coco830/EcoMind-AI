from __future__ import annotations

"""Regulator-facing aggregate endpoints."""

from datetime import date
from typing import Annotated
from urllib.parse import quote
import io

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.api.deps import require_regulator_access
from app.db.postgres import get_db
from app.models.user import User
from app.services.regulatory_service import RegulatoryService

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.get("/overview")
async def get_regulator_overview(
    current_user: Annotated[User, Depends(require_regulator_access)],
    db: Annotated[AsyncSession, Depends(get_db)],
    target_date: date | None = Query(None, description="YYYY-MM-DD, default yesterday (T+1)"),
    region_code: str | None = Query(None),
    park_code: str | None = Query(None),
) -> dict:
    service = RegulatoryService(db)
    return await service.get_overview(current_user, target_date, region_code, park_code)


@router.get("/heatmap")
async def get_regulator_heatmap(
    current_user: Annotated[User, Depends(require_regulator_access)],
    db: Annotated[AsyncSession, Depends(get_db)],
    target_date: date | None = Query(None, description="YYYY-MM-DD, default yesterday (T+1)"),
    resolution: int = Query(7, ge=4, le=10),
    region_code: str | None = Query(None),
    park_code: str | None = Query(None),
) -> dict:
    service = RegulatoryService(db)
    return await service.get_heatmap(current_user, target_date, resolution, region_code, park_code)


@router.get("/trends")
async def get_regulator_trends(
    current_user: Annotated[User, Depends(require_regulator_access)],
    db: Annotated[AsyncSession, Depends(get_db)],
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    granularity: str = Query("daily", pattern="^(daily|monthly)$"),
) -> dict:
    if granularity not in {"daily", "monthly"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid granularity")
    service = RegulatoryService(db)
    return await service.get_trends(current_user, start_date, end_date, granularity)


@router.get("/consistency")
async def get_regulator_consistency(
    current_user: Annotated[User, Depends(require_regulator_access)],
    db: Annotated[AsyncSession, Depends(get_db)],
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
) -> dict:
    service = RegulatoryService(db)
    return await service.get_consistency(current_user, start_date, end_date)


@router.get("/reports/download")
async def download_regulator_report(
    current_user: Annotated[User, Depends(require_regulator_access)],
    db: Annotated[AsyncSession, Depends(get_db)],
    report_type: str = Query("daily", pattern="^(daily|monthly)$"),
    target_date: date | None = Query(None),
    year: int | None = Query(None, ge=2020, le=2100),
    month: int | None = Query(None, ge=1, le=12),
    format: str = Query("excel", pattern="^(excel|pdf)$"),
    region_code: str | None = Query(None),
    park_code: str | None = Query(None),
) -> StreamingResponse:
    service = RegulatoryService(db)

    try:
        payload = await service.build_report_payload(
            current_user,
            report_type,
            target_date,
            year,
            month,
            region_code,
            park_code,
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid report params")

    if format == "excel":
        file_content = await service.generate_excel_report(payload)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        extension = "xlsx"
    else:
        file_content = await service.generate_pdf_report(payload)
        media_type = "application/pdf"
        extension = "pdf"

    filename = f"regulator_report_{payload['period_label']}.{extension}"
    encoded_filename = quote(filename, safe="")

    logger.info(
        "Regulator report downloaded",
        report_type=payload["report_type"],
        period=payload["period_label"],
        format=format,
        user_id=str(current_user.id),
    )

    return StreamingResponse(
        io.BytesIO(file_content),
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
            "Content-Length": str(len(file_content)),
        },
    )
