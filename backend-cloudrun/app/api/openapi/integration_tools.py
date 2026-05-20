"""Integration endpoints for mini-program backend and external bridges."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, time
from typing import Annotated, Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import AliasChoices, BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.openapi.auth import ApiClientContext, get_api_client, resolve_target_org
from app.api.openapi.schemas import (
    MonitoringSummaryResponse,
    PackagePushResponse,
    PackagePushStatusResponse,
)
from app.db.postgres import get_db
from app.models.device import Device
from app.models.integration_push_job import PackagePushJob, PackagePushJobStatus
from app.models.organization import Organization
from app.services.cos_storage import get_cos_storage
from app.services.monitoring_service import MonitoringService

router = APIRouter()
logger = structlog.get_logger()

MAX_PACKAGE_SIZE_BYTES = 50 * 1024 * 1024


class MonitoringSummaryRequest(BaseModel):
    """Request payload for the monitoring summary integration endpoint."""

    model_config = {
        "populate_by_name": True,
        "str_strip_whitespace": True,
    }

    org_id: UUID | None = Field(
        default=None,
        validation_alias=AliasChoices("org_id", "orgId"),
    )
    enterprise_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("enterprise_name", "enterpriseName"),
    )
    mn_code: str = Field(
        ...,
        min_length=1,
        max_length=64,
        validation_alias=AliasChoices("mnCode", "mn_code", "device_mn", "deviceMn"),
    )
    start_date: date = Field(
        ...,
        validation_alias=AliasChoices("startDate", "start_date"),
    )
    end_date: date = Field(
        ...,
        validation_alias=AliasChoices("endDate", "end_date"),
    )

    @model_validator(mode="after")
    def validate_date_order(self) -> "MonitoringSummaryRequest":
        if self.start_date > self.end_date:
            raise ValueError("startDate 不能晚于 endDate")
        return self


def _integration_error(
    *,
    status_code: int,
    error_code: str,
    message: str,
    suggestion: str,
    possible_reasons: list[str] | None = None,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "success": False,
            "error_code": error_code,
            "message": message,
            "possible_reasons": possible_reasons or [],
            "suggestion": suggestion,
        },
    )


def _parse_metadata(metadata: str) -> dict[str, Any]:
    try:
        parsed = json.loads(metadata)
    except json.JSONDecodeError as exc:
        raise _integration_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="INVALID_METADATA_JSON",
            message="metadata 不是合法的 JSON 字符串",
            suggestion="请将 metadata 按 JSON 字符串传入 multipart/form-data 字段",
            possible_reasons=[str(exc)],
        ) from exc

    if not isinstance(parsed, dict):
        raise _integration_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="INVALID_METADATA_TYPE",
            message="metadata 必须是 JSON 对象",
            suggestion="请传入对象结构，例如 {\"jobId\":\"xxx\",\"enterprise\":{\"id\":\"...\"}}",
        )
    return parsed


def _extract_org_selector(metadata_obj: dict[str, Any]) -> tuple[str | None, UUID | None]:
    enterprise = metadata_obj.get("enterprise") or {}
    if not isinstance(enterprise, dict):
        enterprise = {}

    enterprise_name = (
        enterprise.get("name")
        or metadata_obj.get("enterpriseName")
        or metadata_obj.get("enterprise_name")
    )

    raw_org_id = (
        enterprise.get("orgId")
        or enterprise.get("org_id")
        or enterprise.get("id")
        or metadata_obj.get("orgId")
        or metadata_obj.get("org_id")
    )

    org_uuid: UUID | None = None
    if raw_org_id:
        try:
            org_uuid = UUID(str(raw_org_id))
        except ValueError:
            org_uuid = None

    return enterprise_name, org_uuid


def _ensure_zip_file(upload: UploadFile) -> None:
    filename = (upload.filename or "").lower()
    content_type = (upload.content_type or "").lower()
    if filename.endswith(".zip"):
        return
    if content_type in {"application/zip", "application/x-zip-compressed"}:
        return
    raise _integration_error(
        status_code=status.HTTP_400_BAD_REQUEST,
        error_code="INVALID_PACKAGE_TYPE",
        message="当前仅接受 ZIP 执行包文件",
        suggestion="请将执行包压缩为 .zip 后重新上传",
        possible_reasons=[f"filename={upload.filename}", f"content_type={upload.content_type}"],
    )


def _parse_metadata_safe(metadata_json: str | None) -> dict[str, Any] | None:
    if not metadata_json:
        return None
    try:
        parsed = json.loads(metadata_json)
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _format_dt(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else ""


def _build_push_job_payload(
    push_job: PackagePushJob,
    *,
    enterprise_name: str,
) -> dict[str, Any]:
    metadata_obj = _parse_metadata_safe(push_job.metadata_json)
    return {
        "pushJobId": str(push_job.id),
        "sourceJobId": push_job.source_job_id or "",
        "enterprise": enterprise_name,
        "orgId": str(push_job.org_id),
        "packageName": push_job.package_name,
        "fileName": push_job.file_name,
        "documentLink": push_job.document_link or push_job.package_uri,
        "packageUri": push_job.package_uri,
        "status": push_job.status,
        "message": push_job.message or "",
        "fileSize": push_job.file_size,
        "fileSha256": push_job.file_sha256,
        "contentType": push_job.content_type or "",
        "receivedAt": _format_dt(push_job.created_at),
        "updatedAt": _format_dt(push_job.updated_at),
        "metadata": metadata_obj or {},
    }


@router.post(
    "/monitoring/summary",
    response_model=MonitoringSummaryResponse,
    summary="获取监测摘要",
    description="按 mnCode + 时间范围返回污染物统计摘要，供运维小程序生成简报和执行包使用。",
)
async def get_monitoring_summary(
    request: MonitoringSummaryRequest,
    ctx: Annotated[ApiClientContext, Depends(get_api_client)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MonitoringSummaryResponse:
    target_org_id, target_org_name = await resolve_target_org(
        ctx=ctx,
        db=db,
        enterprise_name=request.enterprise_name,
        org_id=request.org_id,
    )

    result = await db.execute(
        select(Device).where(
            Device.org_id == target_org_id,
            Device.mn == request.mn_code,
        )
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise _integration_error(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="MN_NOT_FOUND",
            message=f"未找到 mnCode 为 {request.mn_code} 的设备",
            suggestion="请检查 mnCode 是否正确，或确认该设备是否属于当前企业",
            possible_reasons=[target_org_name],
        )

    start_time = datetime.combine(request.start_date, time.min)
    end_time = datetime.combine(request.end_date, time.max)
    summary_data = await MonitoringService(db).get_period_summary(
        device_id=device.mn,
        org_id=str(target_org_id),
        start_time=start_time,
        end_time=end_time,
    )

    items = summary_data.get("items", [])
    if not items:
        return MonitoringSummaryResponse(
            success=True,
            data={
                "enterprise": target_org_name,
                "orgId": str(target_org_id),
                "mnCode": request.mn_code,
                "deviceName": device.name,
                "startDate": str(request.start_date),
                "endDate": str(request.end_date),
                "pollutantCount": 0,
                "totalDataPoints": 0,
                "items": [],
            },
            summary=f"{device.name}在 {request.start_date} 至 {request.end_date} 期间暂无在线监测数据。",
        )

    return MonitoringSummaryResponse(
        success=True,
        data={
            "enterprise": target_org_name,
            "orgId": str(target_org_id),
            "mnCode": request.mn_code,
            "deviceName": device.name,
            "startDate": str(request.start_date),
            "endDate": str(request.end_date),
            "pollutantCount": summary_data["pollutant_count"],
            "totalDataPoints": summary_data["total_data_points"],
            "items": items,
        },
        summary=(
            f"{device.name}（{target_org_name}）在 {request.start_date} 至 {request.end_date} "
            f"共汇总 {summary_data['pollutant_count']} 项指标，"
            f"{summary_data['total_data_points']} 条监测数据。"
        ),
    )


@router.get(
    "/package/push/status",
    response_model=PackagePushStatusResponse,
    summary="查询执行包回传状态",
    description="按 pushJobId 或 sourceJobId 查询执行包回传状态，供小程序侧同步回传结果和文档链接。",
)
async def get_execution_package_status(
    ctx: Annotated[ApiClientContext, Depends(get_api_client)],
    db: Annotated[AsyncSession, Depends(get_db)],
    push_job_id: UUID | None = Query(None, alias="pushJobId", description="回传接口返回的 pushJobId，优先推荐"),
    source_job_id: str | None = Query(
        None,
        alias="sourceJobId",
        min_length=1,
        max_length=128,
        description="业务侧导出任务ID；single_org Key 可单独查询，all_orgs Key 需配合 org_id 或 enterprise_name 使用",
    ),
    enterprise_name: str | None = Query(
        None,
        description="企业名称（all_orgs + sourceJobId 查询时可选；不传则优先使用 org_id）",
    ),
    org_id: UUID | None = Query(
        None,
        description="组织ID（all_orgs + sourceJobId 查询时优先推荐）",
    ),
) -> PackagePushStatusResponse:
    if push_job_id is None and not source_job_id:
        raise _integration_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="MISSING_PUSH_JOB_SELECTOR",
            message="请至少提供 pushJobId 或 sourceJobId 其中一个查询条件",
            suggestion="优先使用 pushJobId 精确查询；如使用 sourceJobId，all_orgs Key 请同时传 org_id 或 enterprise_name",
        )

    target_org_id: UUID | None = None
    target_org_name: str | None = None

    if not ctx.is_all_orgs:
        target_org_id = ctx.org_id
        target_org_name = ctx.org_name
    elif org_id is not None or enterprise_name:
        target_org_id, target_org_name = await resolve_target_org(
            ctx=ctx,
            db=db,
            enterprise_name=enterprise_name,
            org_id=org_id,
        )
    elif push_job_id is None and source_job_id:
        raise _integration_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="MISSING_ENTERPRISE_SELECTOR",
            message="all_orgs 模式按 sourceJobId 查询时，必须同时提供 org_id 或 enterprise_name",
            suggestion="建议优先使用 org_id 精确回查，或改用 pushJobId 直接查询",
        )

    stmt = select(PackagePushJob)
    if push_job_id is not None:
        stmt = stmt.where(PackagePushJob.id == push_job_id)
    if source_job_id:
        stmt = stmt.where(PackagePushJob.source_job_id == source_job_id)
    if target_org_id is not None:
        stmt = stmt.where(PackagePushJob.org_id == target_org_id)

    result = await db.execute(
        stmt.order_by(PackagePushJob.created_at.desc(), PackagePushJob.id.desc()).limit(1)
    )
    push_job = result.scalar_one_or_none()
    if push_job is None:
        raise _integration_error(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="PUSH_JOB_NOT_FOUND",
            message="未找到匹配的执行包回传记录",
            suggestion="请检查 pushJobId/sourceJobId 是否正确，或确认该记录是否属于当前企业范围",
        )

    if target_org_name is None:
        org_result = await db.execute(select(Organization).where(Organization.id == push_job.org_id))
        organization = org_result.scalar_one_or_none()
        target_org_name = organization.name if organization else str(push_job.org_id)

    payload = _build_push_job_payload(push_job, enterprise_name=target_org_name)
    if source_job_id and push_job_id is None:
        summary = f"{target_org_name} 最近一次 sourceJobId={source_job_id} 的执行包回传状态为 {push_job.status}。"
    else:
        summary = f"{target_org_name} 的执行包回传状态为 {push_job.status}。"

    return PackagePushStatusResponse(
        success=True,
        data=payload,
        summary=summary,
    )


@router.post(
    "/package/push",
    response_model=PackagePushResponse,
    summary="接收执行包回传",
    description="接收运维小程序后端回传的 ZIP 执行包，保存审计记录并返回 pushJobId/documentLink。",
)
async def push_execution_package(
    ctx: Annotated[ApiClientContext, Depends(get_api_client)],
    db: Annotated[AsyncSession, Depends(get_db)],
    metadata: Annotated[str, Form(description="JSON 字符串，包含 jobId/packageName/enterprise/station/period 等信息")],
    package: Annotated[UploadFile, File(description="ZIP 执行包文件")],
    enterprise_name: str | None = Query(None, description="企业名称（all_orgs Key 可选；不传时尝试从 metadata.enterprise.name 解析）"),
    org_id: UUID | None = Query(None, description="组织ID（all_orgs Key 可选；不传时尝试从 metadata.enterprise.id 解析）"),
) -> PackagePushResponse:
    _ensure_zip_file(package)
    metadata_obj = _parse_metadata(metadata)

    metadata_enterprise_name, metadata_org_id = _extract_org_selector(metadata_obj)
    target_org_id, target_org_name = await resolve_target_org(
        ctx=ctx,
        db=db,
        enterprise_name=enterprise_name or metadata_enterprise_name,
        org_id=org_id or metadata_org_id,
    )

    content = await package.read()
    if not content:
        raise _integration_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="EMPTY_PACKAGE",
            message="执行包文件为空",
            suggestion="请确认上传的 ZIP 文件内容完整后重试",
        )
    if len(content) > MAX_PACKAGE_SIZE_BYTES:
        raise _integration_error(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            error_code="PACKAGE_TOO_LARGE",
            message="执行包文件过大，超过 50MB 限制",
            suggestion="请压缩执行包内容后重试",
        )

    cos = get_cos_storage()
    if not cos:
        raise _integration_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="COS_NOT_CONFIGURED",
            message="平台对象存储未配置，当前无法接收执行包",
            suggestion="请先配置 COS/CloudBase 对象存储后重试",
        )

    package_name = (
        metadata_obj.get("packageName")
        or metadata_obj.get("package_name")
        or package.filename
        or "execution-package.zip"
    )
    object_key = cos.build_key(org_id=str(target_org_id), filename=package.filename or package_name)
    cos_obj = cos.put_bytes(
        key=object_key,
        body=content,
        content_type=package.content_type or "application/zip",
        content_disposition_filename=package.filename or package_name,
    )

    file_sha256 = hashlib.sha256(content).hexdigest()
    push_job = PackagePushJob(
        org_id=target_org_id,
        client_id=getattr(ctx.client, "id", None),
        source_job_id=str(metadata_obj.get("jobId") or metadata_obj.get("job_id") or ""),
        package_name=str(package_name),
        file_name=package.filename or "execution-package.zip",
        package_uri=cos_obj.uri,
        document_link=cos_obj.uri,
        metadata_json=json.dumps(metadata_obj, ensure_ascii=False),
        file_size=len(content),
        file_sha256=file_sha256,
        content_type=package.content_type or "application/zip",
        status=PackagePushJobStatus.ACCEPTED.value,
        message="accepted",
    )
    db.add(push_job)
    await db.flush()
    await db.refresh(push_job)

    logger.info(
        "Execution package accepted",
        push_job_id=str(push_job.id),
        org_id=str(target_org_id),
        package_name=package_name,
        file_size=len(content),
    )

    return PackagePushResponse(
        success=True,
        data=_build_push_job_payload(push_job, enterprise_name=target_org_name),
        summary=f"{target_org_name} 的执行包已接收，pushJobId={push_job.id}。",
    )
