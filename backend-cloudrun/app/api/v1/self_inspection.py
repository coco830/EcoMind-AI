from __future__ import annotations

"""Self-inspection report API endpoints - 自检档案API."""

import io
import os
from datetime import date, datetime
from typing import Annotated
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, HTTPException, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.db.postgres import get_db
from app.models.user import User
from datetime import timedelta

from app.models.self_inspection import (
    SelfInspectionReportCreate,
    SelfInspectionReportUpdate,
    SelfInspectionReportResponse,
    SelfInspectionReportListResponse,
    SelfInspectionDataCreate,
    InspectionStatus,
    OCRUploadResponse,
    TrendAnalysisRequest,
    TrendAnalysisResponse,
    AIReportRequest,
    AIReportResponse,
    DeviceFlowResponse,
    DeviceFlowListResponse,
    FlowTrendPoint,
    FlowStatistics,
    OnlineMetricOption,
    DeviceOnlineMetricListResponse,
    DeviceOnlineMetricResponse,
)
from app.api.deps import get_current_active_user, require_doc_editor, require_superadmin
from app.api.deps import can_cross_tenant_doc_write
from app.api.deps import can_cross_tenant_read
from app.services.self_inspection_service import (
    SelfInspectionService,
    BaiduOCRClient,
    OCRParserService,
    TableOCRParser,
    AIDataExtractor,
    AIReportGenerator,
    get_self_inspection_service,
    get_baidu_ocr_client,
    get_ai_data_extractor,
)
from app.services.llm import get_spark_client
from app.core.config import get_settings
from app.services.cos_storage import get_cos_storage

router = APIRouter()
logger = structlog.get_logger()
settings = get_settings()


class PaginatedReportListResponse(BaseModel):
    """分页报告列表响应"""
    items: list[SelfInspectionReportListResponse]
    total: int
    page: int
    page_size: int


def _get_user_org_id(
    user: User,
    allow_superadmin_all: bool = False,
    target_org_id: UUID | None = None,
) -> UUID | None:
    """获取用户组织ID

    Args:
        user: 当前用户
        allow_superadmin_all: 是否允许超级管理员查看所有组织数据
        target_org_id: 超级管理员指定的目标组织ID

    Returns:
        组织ID，超级管理员且allow_superadmin_all=True时返回None表示查看全部
    """
    # 超级管理员特殊处理
    if user.is_superadmin:
        if target_org_id:
            return target_org_id  # 超级管理员指定了目标组织
        if allow_superadmin_all:
            return None  # 超级管理员查看全部
        # 超级管理员未指定组织时，如果有自己的org_id就用，否则报错
        if user.org_id:
            return user.org_id
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请选择目标企业后再上传报告",
        )

    # 平台文档人员（w=doc_editor under PLATFORM_ADMIN）允许跨企业操作文档数据
    if can_cross_tenant_doc_write(user):
        if target_org_id:
            return target_org_id
        if allow_superadmin_all:
            return None  # 平台文档人员允许查看全部（列表场景）
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请选择目标企业后再上传报告",
        )

    # 普通用户必须属于一个组织
    if not user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户必须属于一个组织",
        )
    return user.org_id


@router.post("/upload", response_model=OCRUploadResponse)
async def upload_and_ocr(
    file: Annotated[UploadFile, File(description="检测报告文件（PDF/图片）")],
    inspection_date: Annotated[str | None, Form(description="检测日期（可选，AI会自动识别，格式YYYY-MM-DD）")] = None,
    inspection_agency: Annotated[str | None, Form(description="检测机构名称（可选，AI会自动识别）")] = None,
    report_number: Annotated[str | None, Form(description="报告编号")] = None,
    target_org_id: Annotated[str | None, Form(description="目标组织ID（超级管理员专用）")] = None,
    use_ai_parsing: Annotated[str, Form(description="是否使用AI智能解析")] = "true",
    current_user: Annotated[User, Depends(require_doc_editor)] = None,  # 需要文档编辑权限
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> OCRUploadResponse:
    """
    上传检测报告并进行OCR+AI智能解析。

    处理流程：
    1. 上传文件（PDF/图片）
    2. 百度OCR表格识别 → 提取表格结构化数据
    3. AI智能解析 → 从OCR结果中提取检测数据
    4. 返回解析结果供用户校验

    支持PDF和图片格式（JPG、PNG）。
    超级管理员可以通过target_org_id指定目标企业。
    """
    # 解析参数
    use_ai = use_ai_parsing.lower() in ("true", "1", "yes")
    parsed_target_org_id = UUID(target_org_id) if target_org_id else None
    parsed_inspection_date: date | None = None
    if inspection_date:
        try:
            parsed_inspection_date = date.fromisoformat(inspection_date)
        except ValueError:
            pass

    org_id = _get_user_org_id(current_user, target_org_id=parsed_target_org_id)

    # 验证文件类型
    allowed_types = ["application/pdf", "image/jpeg", "image/png", "image/jpg"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型: {file.content_type}。支持: PDF, JPG, PNG",
        )

    # 读取文件内容
    file_content = await file.read()

    # Upload original file to COS (CloudBase Storage)
    cos = get_cos_storage()
    if not cos:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="云存储未配置（COS_SECRET_ID/COS_SECRET_KEY/COS_REGION/COS_BUCKET/COS_PREFIX），无法归档原始报告文件",
        )

    object_key = cos.build_key(org_id=str(org_id), filename=file.filename or "report")
    cos_obj = cos.put_bytes(
        key=object_key,
        body=file_content,
        content_type=file.content_type or "application/octet-stream",
        content_disposition_filename=file.filename or "report",
    )
    logger.info(
        "Self-inspection file archived to COS",
        org_id=str(org_id),
        filename=file.filename,
        cos_key=cos_obj.key,
    )

    # 初始化变量
    recognized_data = []
    ocr_confidence = None
    raw_text = None
    ai_extracted_info = {}

    # 检查是否配置了百度OCR（从环境变量读取）
    ocr_client = get_baidu_ocr_client()

    if ocr_client:
        try:

            # 根据文件类型选择OCR方式
            is_pdf = file.content_type == "application/pdf"

            if is_pdf:
                # PDF文件：使用多页表格识别
                ocr_results = await ocr_client.recognize_pdf_tables(file_content)
                raw_text = TableOCRParser.tables_to_text(ocr_results)
                logger.info("PDF OCR completed", page_count=len(ocr_results))
            else:
                # 图片文件：先尝试表格识别，如果失败则用通用OCR
                try:
                    table_result = await ocr_client.recognize_table(file_content)
                    if table_result.get("table_num", 0) > 0:
                        ocr_results = [table_result]
                        raw_text = TableOCRParser.tables_to_text(ocr_results)
                    else:
                        ocr_result = await ocr_client.recognize_document(file_content)
                        ocr_results = [ocr_result]
                        if "words_result" in ocr_result:
                            raw_text = "\n".join([item["words"] for item in ocr_result["words_result"]])
                except Exception:
                    # 表格识别失败，回退到通用OCR
                    ocr_result = await ocr_client.recognize_document(file_content)
                    ocr_results = [ocr_result]
                    if "words_result" in ocr_result:
                        raw_text = "\n".join([item["words"] for item in ocr_result["words_result"]])

            logger.info("OCR completed", raw_text_length=len(raw_text) if raw_text else 0)

            # 使用AI智能解析
            ai_extractor = get_ai_data_extractor() if use_ai else None
            if ai_extractor and raw_text:
                try:
                    ai_extracted_info = await ai_extractor.extract_inspection_data(
                        ocr_text=raw_text,
                        file_name=file.filename,
                    )

                    # 转换AI提取的数据为SelfInspectionDataCreate格式
                    if ai_extracted_info.get("data_items"):
                        for item in ai_extracted_info["data_items"]:
                            recognized_data.append(SelfInspectionDataCreate(
                                pollutant_code=item.get("pollutant_code"),
                                pollutant_name=item.get("pollutant_name", ""),
                                value=float(item.get("value", 0)) if item.get("value") is not None else 0,
                                unit=item.get("unit", "mg/L"),
                                standard_limit=float(item.get("standard_limit")) if item.get("standard_limit") is not None else None,
                                is_compliant=item.get("is_compliant", True),
                                sampling_point=item.get("sampling_point"),
                            ))

                    ocr_confidence = ai_extracted_info.get("ai_confidence", 0.5)
                    logger.info("AI parsing completed",
                               data_count=len(recognized_data),
                               confidence=ocr_confidence)

                except Exception as e:
                    logger.error("AI parsing failed, falling back to rule-based parsing", error=str(e))
                    # 回退到规则解析
                    if ocr_results:
                        for result in ocr_results:
                            recognized_data.extend(OCRParserService.parse_ocr_result(result))

            else:
                # 不使用AI，使用规则解析
                if ocr_results:
                    for result in ocr_results:
                        recognized_data.extend(OCRParserService.parse_ocr_result(result))
                ocr_confidence = min(len(recognized_data) / 10.0, 1.0) if recognized_data else 0.3

        except Exception as e:
            logger.error("OCR failed", error=str(e))

    # 使用AI识别的信息填充默认值
    final_inspection_date = parsed_inspection_date
    final_inspection_agency = inspection_agency or ai_extracted_info.get("inspection_agency", "")
    final_report_number = report_number or ai_extracted_info.get("report_number")

    # 如果AI识别了日期
    if not final_inspection_date and ai_extracted_info.get("inspection_date"):
        try:
            final_inspection_date = date.fromisoformat(ai_extracted_info["inspection_date"])
        except ValueError:
            pass

    # 如果仍然没有日期，使用今天
    if not final_inspection_date:
        final_inspection_date = date.today()

    # 如果没有检测机构，使用默认值
    if not final_inspection_agency:
        final_inspection_agency = "待填写"

    # 创建报告记录（待校验状态）
    service = get_self_inspection_service(db)
    report = await service.create_report(
        org_id=org_id,
        data=SelfInspectionReportCreate(
            inspection_date=final_inspection_date,
            inspection_agency=final_inspection_agency,
            report_number=final_report_number,
            data_items=recognized_data,
        ),
    )

    # 更新文件信息
    report.original_file_path = cos_obj.uri
    report.original_file_name = file.filename
    report.ocr_raw_text = raw_text
    report.ocr_confidence = ocr_confidence
    await db.commit()

    # 构建返回消息
    if recognized_data:
        if ocr_confidence and ocr_confidence >= 0.7:
            message = f"AI智能解析完成，识别到{len(recognized_data)}项检测数据，置信度{ocr_confidence:.0%}，请校验确认"
        else:
            message = f"解析完成，识别到{len(recognized_data)}项数据，建议仔细校验"
    else:
        message = "未能自动识别检测数据，请手动填写"

    return OCRUploadResponse(
        report_id=report.id,
        ocr_confidence=ocr_confidence,
        recognized_data=recognized_data,
        raw_text=raw_text,
        message=message,
    )


@router.post("", response_model=SelfInspectionReportResponse)
async def create_report(
    data: SelfInspectionReportCreate,
    current_user: Annotated[User, Depends(require_doc_editor)],  # 需要文档编辑权限
    db: Annotated[AsyncSession, Depends(get_db)],
    target_org_id: UUID | None = Query(None, description="目标组织ID（超级管理员专用）"),
) -> SelfInspectionReportResponse:
    """
    手动创建自检报告（不通过OCR）。
    需要文档编辑权限（doc_editor 或 superadmin）。
    超级管理员可以通过target_org_id指定目标企业。
    """
    org_id = _get_user_org_id(current_user, target_org_id=target_org_id)
    service = get_self_inspection_service(db)

    report = await service.create_report(org_id=org_id, data=data)

    # 重新查询以获取完整数据
    report = await service.get_report(report.id, org_id)

    return SelfInspectionReportResponse(
        id=report.id,
        org_id=report.org_id,
        inspection_date=report.inspection_date,
        inspection_agency=report.inspection_agency,
        report_number=report.report_number,
        original_file_name=report.original_file_name,
        ocr_confidence=report.ocr_confidence,
        status=InspectionStatus(report.status),
        is_verified=report.is_verified,
        verified_at=report.verified_at,
        remarks=report.remarks,
        created_at=report.created_at,
        updated_at=report.updated_at,
        data_items=[
            {
                "id": item.id,
                "report_id": item.report_id,
                "pollutant_code": item.pollutant_code,
                "pollutant_name": item.pollutant_name,
                "value": item.value,
                "unit": item.unit,
                "standard_limit": item.standard_limit,
                "is_compliant": item.is_compliant,
                "sampling_point": item.sampling_point,
                "sampling_time": item.sampling_time,
                "remarks": item.remarks,
                "created_at": item.created_at,
            }
            for item in report.data_items
        ],
    )


@router.get("", response_model=PaginatedReportListResponse)
async def list_reports(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    start_date: date | None = Query(None, description="开始日期"),
    end_date: date | None = Query(None, description="结束日期"),
    status: InspectionStatus | None = Query(None, description="状态筛选"),
    target_org_id: UUID | None = Query(None, description="目标组织ID（超级管理员按企业过滤）"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
) -> PaginatedReportListResponse:
    """
    获取自检报告列表。
    超级管理员可以查看所有组织的报告，或通过target_org_id过滤特定组织。
    """
    # 超级管理员如果指定了target_org_id，则按该组织过滤
    org_id = _get_user_org_id(current_user, allow_superadmin_all=True, target_org_id=target_org_id)
    service = get_self_inspection_service(db)

    skip = (page - 1) * page_size
    reports, total = await service.list_reports(
        org_id=org_id,
        start_date=start_date,
        end_date=end_date,
        status=status,
        skip=skip,
        limit=page_size,
    )

    return PaginatedReportListResponse(
        items=[SelfInspectionReportListResponse(**r) for r in reports],
        total=total,
        page=page,
        page_size=page_size,
    )


# ============== Device Flow Endpoints (Read-only from Data Acquisition Device) ==============
# Note: These routes MUST be defined BEFORE /{report_id} to avoid path conflicts

@router.get("/device-flow", response_model=DeviceFlowListResponse)
async def get_device_flow(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    hours: int = Query(default=24, ge=1, le=168, description="数据时间范围（小时）"),
    include_history: bool = Query(default=False, description="是否包含趋势数据"),
    target_org_id: UUID | None = Query(default=None, description="目标组织ID（超级管理员指定企业）"),
) -> DeviceFlowListResponse:
    """
    获取企业设备的瞬时流量数据（只读）。

    此端点从数采仪获取瞬时流量数据，用于在文档数据页面展示。
    数据来源明确标注为数采仪，不会存储到自检报告表中。

    - **hours**: 查询最近多少小时的数据（默认24小时）
    - **include_history**: 是否包含趋势数据点（默认否）
    - **target_org_id**: 超级管理员指定要查看的企业ID
    """
    # 组织选择规则：
    # - 平台侧（超级管理员/平台人员）必须显式选择 target_org_id，否则默认显示“未选择企业”
    # - 企业侧（普通租户用户）默认使用自己的 org_id
    if can_cross_tenant_read(current_user):
        if not target_org_id:
            return DeviceFlowListResponse(
                devices=[],
                org_name="未选择企业",
                query_time=datetime.utcnow(),
                data_source_note="请在页面上方选择要查看的企业",
            )
        org_id = target_org_id
    else:
        org_id = current_user.org_id
        if not org_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="用户未绑定企业",
            )

    # 导入必要的模型和服务
    from app.models.device import Device
    from app.models.organization import Organization
    from app.services.monitoring_service import MonitoringService
    from sqlalchemy import select

    # 获取组织信息
    org_result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = org_result.scalar_one_or_none()
    org_name = org.name if org else "未知企业"

    # 获取该组织的所有设备
    devices_result = await db.execute(
        select(Device).where(Device.org_id == org_id)
    )
    devices = devices_result.scalars().all()

    if not devices:
        return DeviceFlowListResponse(
            devices=[],
            org_name=org_name,
            query_time=datetime.utcnow(),
            data_source_note="该企业暂无绑定设备",
        )

    # 初始化监测数据服务
    monitoring_service = MonitoringService(db)

    # 时间范围
    end_time = datetime.utcnow() + timedelta(hours=9)  # UTC+8
    start_time = end_time - timedelta(hours=hours + 9)

    device_flow_list = []

    for device in devices:
        # 获取设备的最新瞬时流量数据 (w00000)
        latest_flow_data = await monitoring_service.get_latest_values(
            device_ids=[device.mn],
            org_id=str(org_id),
            pollutant_code="w00000",
        )

        latest_flow = None
        latest_flow_ts = None

        if latest_flow_data:
            for data in latest_flow_data:
                if data.get("pollutant_code") == "w00000":
                    latest_flow = data.get("value")
                    latest_flow_ts = data.get("ts")
                    break

        # 如果需要历史趋势数据
        trend_data = None
        if include_history:
            history_data = await monitoring_service.query_monitoring_data(
                device_id=device.mn,
                org_id=str(org_id),
                pollutant_code="w00000",
                start_time=start_time,
                end_time=end_time,
                limit=200,
            )
            if history_data:
                trend_data = [
                    FlowTrendPoint(
                        ts=item["ts"],
                        value=item["value"],
                        flag=item.get("flag", "N"),
                    )
                    for item in history_data
                ]

        device_flow_list.append(
            DeviceFlowResponse(
                device_id=device.mn,
                device_name=device.name,
                device_status=device.status or "unknown",
                latest_flow=latest_flow,
                latest_flow_ts=latest_flow_ts,
                flow_unit="L/s",
                data_source="datacollector",
                trend_data=trend_data,
            )
        )

    return DeviceFlowListResponse(
        devices=device_flow_list,
        org_name=org_name,
        query_time=datetime.utcnow(),
        data_source_note="数据来自环境监测数采仪（只读），不存储到自检报告",
    )


@router.get("/device-flow/statistics", response_model=FlowStatistics)
async def get_device_flow_statistics(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    device_id: str = Query(..., description="设备MN号"),
    start_date: date = Query(..., description="开始日期"),
    end_date: date = Query(..., description="结束日期"),
) -> FlowStatistics:
    """
    获取设备瞬时流量统计数据（只读）。

    用于AI报告生成时计算污染负荷。
    """
    org_id = current_user.org_id
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先选择目标企业" if current_user.is_superadmin else "用户未绑定企业",
        )

    # 验证设备属于该组织
    from app.models.device import Device
    from app.services.monitoring_service import MonitoringService
    from sqlalchemy import select

    device_result = await db.execute(
        select(Device).where(Device.mn == device_id, Device.org_id == org_id)
    )
    device = device_result.scalar_one_or_none()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="设备不存在或无权访问",
        )

    # 获取统计数据
    monitoring_service = MonitoringService(db)
    start_time = datetime.combine(start_date, datetime.min.time())
    end_time = datetime.combine(end_date, datetime.max.time())

    stats = await monitoring_service.get_statistics(
        device_id=device_id,
        pollutant_code="w00000",
        start_time=start_time,
        end_time=end_time,
    )

    if not stats or stats.get("count", 0) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="指定时间范围内没有流量数据",
        )

    # 计算总流量体积 (L/s * 秒数 / 1000 = m³)
    duration_seconds = (end_time - start_time).total_seconds()
    avg_flow = stats.get("avg_value", 0) or 0
    total_volume = avg_flow * duration_seconds / 1000  # 转换为立方米

    return FlowStatistics(
        avg_flow=avg_flow,
        max_flow=stats.get("max_value", 0) or 0,
        min_flow=stats.get("min_value", 0) or 0,
        total_volume=round(total_volume, 2),
        unit="L/s",
        data_points_count=stats.get("count", 0),
    )


@router.get("/online-metrics/options", response_model=list[OnlineMetricOption])
async def get_online_metric_options(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    hours: int = Query(default=24, ge=1, le=168, description="统计最近多少小时内出现过的指标"),
    target_org_id: UUID | None = Query(default=None, description="目标组织ID（超级管理员/平台人员指定企业）"),
) -> list[OnlineMetricOption]:
    """获取企业在线监测可用指标列表（来自实际数据出现情况）"""
    if can_cross_tenant_read(current_user):
        if not target_org_id:
            return []
        org_id = target_org_id
    else:
        org_id = current_user.org_id
        if not org_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户未绑定企业")

    from app.models.monitoring_mysql import MonitoringDataMySQL
    from sqlalchemy import select, func
    from app.core.pollutant_library import get_pollutant_info

    end_time = datetime.utcnow() + timedelta(hours=9)  # 兼容历史：本库时间戳多数为本地时间
    start_time = datetime.utcnow() - timedelta(hours=hours)

    rows = (
        await db.execute(
            select(
                MonitoringDataMySQL.pollutant_code,
                func.max(MonitoringDataMySQL.pollutant_name).label("pollutant_name"),
            )
            .where(
                MonitoringDataMySQL.org_id == str(org_id),
                MonitoringDataMySQL.ts >= start_time,
                MonitoringDataMySQL.ts <= end_time,
            )
            .group_by(MonitoringDataMySQL.pollutant_code)
            .order_by(MonitoringDataMySQL.pollutant_code)
        )
    ).all()

    options: list[OnlineMetricOption] = []
    for code, name in rows:
        info = get_pollutant_info(code) or {}
        options.append(
            OnlineMetricOption(
                pollutant_code=code,
                pollutant_name=info.get("name") or (name or code),
                unit=info.get("unit"),
            )
        )
    return options


@router.get("/online-metrics", response_model=DeviceOnlineMetricListResponse)
async def get_device_online_metrics(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    pollutant_code: str = Query(..., description="指标代码，如 w00000/w01018"),
    hours: int = Query(default=24, ge=1, le=168, description="数据时间范围（小时）"),
    include_history: bool = Query(default=True, description="是否包含趋势数据"),
    target_org_id: UUID | None = Query(default=None, description="目标组织ID（超级管理员/平台人员指定企业）"),
) -> DeviceOnlineMetricListResponse:
    """获取企业设备在线数据（设备维度，指标可选）"""
    if can_cross_tenant_read(current_user):
        if not target_org_id:
            return DeviceOnlineMetricListResponse(
                pollutant_code=pollutant_code,
                pollutant_name=pollutant_code,
                unit=None,
                devices=[],
                org_name="未选择企业",
                query_time=datetime.utcnow(),
                data_source_note="请在页面上方选择要查看的企业",
            )
        org_id = target_org_id
    else:
        org_id = current_user.org_id
        if not org_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户未绑定企业")

    from app.models.device import Device
    from app.models.organization import Organization
    from app.services.monitoring_service import MonitoringService
    from sqlalchemy import select
    from app.core.pollutant_library import get_pollutant_info

    pol = pollutant_code.strip()
    pol_info = get_pollutant_info(pol) or {}
    pol_name = pol_info.get("name") or pol
    pol_unit = pol_info.get("unit")

    org_result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = org_result.scalar_one_or_none()
    org_name = org.name if org else "未知企业"

    devices_result = await db.execute(select(Device).where(Device.org_id == org_id))
    devices = devices_result.scalars().all()
    if not devices:
        return DeviceOnlineMetricListResponse(
            pollutant_code=pol,
            pollutant_name=pol_name,
            unit=pol_unit,
            devices=[],
            org_name=org_name,
            query_time=datetime.utcnow(),
            data_source_note="该企业暂无绑定设备",
        )

    monitoring_service = MonitoringService(db)

    end_time = datetime.utcnow() + timedelta(hours=9)
    start_time = datetime.utcnow() - timedelta(hours=hours)

    latest_rows = await monitoring_service.get_latest_values(
        device_ids=[d.mn for d in devices],
        org_id=str(org_id),
        pollutant_code=pol,
    )
    latest_map = {r.get("device_id"): r for r in (latest_rows or [])}

    device_metrics: list[DeviceOnlineMetricResponse] = []
    for d in devices:
        latest = latest_map.get(d.mn) or {}
        latest_value = latest.get("value")
        latest_ts = latest.get("ts")
        latest_flag = latest.get("flag", "N")

        trend_data = None
        if include_history:
            history = await monitoring_service.query_monitoring_data(
                device_id=d.mn,
                org_id=str(org_id),
                pollutant_code=pol,
                start_time=start_time,
                end_time=end_time,
                limit=200,
            )
            if history:
                trend_data = [
                    FlowTrendPoint(
                        ts=item["ts"],
                        value=item["value"],
                        flag=item.get("flag", "N"),
                    )
                    for item in history
                ]

        device_metrics.append(
            DeviceOnlineMetricResponse(
                device_id=d.mn,
                device_name=d.name,
                device_status=d.status or "unknown",
                pollutant_code=pol,
                pollutant_name=pol_name,
                unit=pol_unit,
                latest_value=latest_value,
                latest_ts=latest_ts,
                data_source="datacollector",
                trend_data=trend_data,
            )
        )

    return DeviceOnlineMetricListResponse(
        pollutant_code=pol,
        pollutant_name=pol_name,
        unit=pol_unit,
        devices=device_metrics,
        org_name=org_name,
        query_time=datetime.utcnow(),
        data_source_note="数据来自环境监测数采仪（只读），不存储到自检报告",
    )


# ============== Report CRUD (with path parameter) ==============

@router.get("/{report_id}", response_model=SelfInspectionReportResponse)
async def get_report(
    report_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SelfInspectionReportResponse:
    """
    获取单个报告详情。
    超级管理员可以查看任何组织的报告。
    """
    org_id = _get_user_org_id(current_user, allow_superadmin_all=True)
    service = get_self_inspection_service(db)

    report = await service.get_report(report_id, org_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="报告不存在",
        )

    return SelfInspectionReportResponse(
        id=report.id,
        org_id=report.org_id,
        inspection_date=report.inspection_date,
        inspection_agency=report.inspection_agency,
        report_number=report.report_number,
        original_file_name=report.original_file_name,
        ocr_confidence=report.ocr_confidence,
        status=InspectionStatus(report.status),
        is_verified=report.is_verified,
        verified_at=report.verified_at,
        remarks=report.remarks,
        created_at=report.created_at,
        updated_at=report.updated_at,
        data_items=[
            {
                "id": item.id,
                "report_id": item.report_id,
                "pollutant_code": item.pollutant_code,
                "pollutant_name": item.pollutant_name,
                "value": item.value,
                "unit": item.unit,
                "standard_limit": item.standard_limit,
                "is_compliant": item.is_compliant,
                "sampling_point": item.sampling_point,
                "sampling_time": item.sampling_time,
                "remarks": item.remarks,
                "created_at": item.created_at,
            }
            for item in report.data_items
        ],
    )


@router.put("/{report_id}", response_model=SelfInspectionReportResponse)
async def update_report(
    report_id: UUID,
    data: SelfInspectionReportUpdate,
    current_user: Annotated[User, Depends(require_doc_editor)],  # 需要文档编辑权限
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SelfInspectionReportResponse:
    """
    更新报告（校验/修正数据）。
    需要文档编辑权限（doc_editor 或 superadmin）。
    超级管理员可以更新任何组织的报告。
    """
    # 超级管理员可以更新任何报告
    org_id = _get_user_org_id(current_user, allow_superadmin_all=True)
    service = get_self_inspection_service(db)

    report = await service.update_report(
        report_id=report_id,
        org_id=org_id,
        data=data,
        verified_by=current_user.id if data.status == InspectionStatus.VERIFIED else None,
    )

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="报告不存在",
        )

    # 重新查询以获取完整数据
    report = await service.get_report(report_id, org_id)

    return SelfInspectionReportResponse(
        id=report.id,
        org_id=report.org_id,
        inspection_date=report.inspection_date,
        inspection_agency=report.inspection_agency,
        report_number=report.report_number,
        original_file_name=report.original_file_name,
        ocr_confidence=report.ocr_confidence,
        status=InspectionStatus(report.status),
        is_verified=report.is_verified,
        verified_at=report.verified_at,
        remarks=report.remarks,
        created_at=report.created_at,
        updated_at=report.updated_at,
        data_items=[
            {
                "id": item.id,
                "report_id": item.report_id,
                "pollutant_code": item.pollutant_code,
                "pollutant_name": item.pollutant_name,
                "value": item.value,
                "unit": item.unit,
                "standard_limit": item.standard_limit,
                "is_compliant": item.is_compliant,
                "sampling_point": item.sampling_point,
                "sampling_time": item.sampling_time,
                "remarks": item.remarks,
                "created_at": item.created_at,
            }
            for item in report.data_items
        ],
    )


@router.delete("/{report_id}")
async def delete_report(
    report_id: UUID,
    current_user: Annotated[User, Depends(require_superadmin)],  # 仅超级管理员可删除
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """
    删除报告。
    仅超级管理员可以删除报告。
    """
    # 超级管理员可以删除任何报告
    org_id = _get_user_org_id(current_user, allow_superadmin_all=True)
    service = get_self_inspection_service(db)

    success = await service.delete_report(report_id, org_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="报告不存在",
        )

    return {"message": "删除成功"}


# ============== Analysis Endpoints ==============

@router.post("/analysis/trend", response_model=TrendAnalysisResponse)
async def get_trend_analysis(
    request: TrendAnalysisRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TrendAnalysisResponse:
    """
    获取趋势分析数据。
    仅分析已校验的报告数据。
    超级管理员可以查看所有组织的趋势数据，或通过target_org_id过滤特定组织。
    """
    # 超级管理员如果指定了target_org_id，则按该组织过滤
    org_id = _get_user_org_id(current_user, allow_superadmin_all=True, target_org_id=request.target_org_id)
    service = get_self_inspection_service(db)

    result = await service.get_trend_analysis(
        org_id=org_id,
        start_date=request.start_date,
        end_date=request.end_date,
        pollutant_codes=request.pollutant_codes,
    )

    return TrendAnalysisResponse(**result)


@router.post("/analysis/ai-report", response_model=AIReportResponse)
async def generate_ai_report(
    request: AIReportRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AIReportResponse:
    """
    生成AI运维报告。

    基于指定时间范围内的自检数据，使用AI生成运维分析报告。
    超级管理员可以基于所有组织的数据生成报告。

    可选功能：
    - **include_flow_data**: 整合数采仪瞬时流量数据
    - **calculate_pollutant_load**: 计算污染负荷（流量×浓度）
    - **target_org_id**: 超级管理员指定目标组织（流量数据必须指定组织）
    """
    # 确定报告的组织范围
    org_id = _get_user_org_id(current_user, allow_superadmin_all=True, target_org_id=request.target_org_id)

    # 确定获取流量数据的组织ID
    # 超级管理员如果要获取流量数据，必须指定具体组织
    flow_org_id = request.target_org_id or (org_id if org_id else current_user.org_id)

    service = get_self_inspection_service(db)

    # 获取趋势数据（来自第三方检测报告）
    trend_result = await service.get_trend_analysis(
        org_id=org_id,
        start_date=request.start_date,
        end_date=request.end_date,
    )

    if not trend_result["data_points"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="指定时间范围内没有已校验的数据",
        )

    # 获取流量数据（如果启用）
    flow_data = None
    online_data = None
    if request.include_flow_data:
        if not flow_org_id:
            # 超级管理员未指定组织且自身没有org_id，无法获取流量数据
            logger.warning("Flow data requested but no organization specified for superadmin")
        else:
            # 有有效的组织ID，尝试获取流量数据
            try:
                # 获取组织的设备
                from app.models.device import Device
                from app.services.monitoring_service import MonitoringService
                from sqlalchemy import select

                devices_result = await db.execute(
                    select(Device).where(Device.org_id == flow_org_id)
                )
                devices = devices_result.scalars().all()

                if devices:
                    monitoring_service = MonitoringService(db)
                    start_time = datetime.combine(request.start_date, datetime.min.time())
                    end_time = datetime.combine(request.end_date, datetime.max.time())
                    duration_seconds = (end_time - start_time).total_seconds()

                    device_flow_stats: list[dict[str, Any]] = []
                    for device in devices:
                        stats = await monitoring_service.get_statistics(
                            device_id=device.mn,
                            pollutant_code="w00000",
                            start_time=start_time,
                            end_time=end_time,
                        )
                        if not stats or stats.get("count", 0) <= 0:
                            continue

                        avg_flow = float(stats.get("avg_value", 0) or 0)
                        max_flow = float(stats.get("max_value", 0) or 0)
                        min_flow = float(stats.get("min_value", 0) or 0)
                        count = int(stats.get("count", 0) or 0)

                        device_flow_stats.append(
                            {
                                "device_mn": device.mn,
                                "device_name": device.name,
                                "avg_flow": avg_flow,
                                "max_flow": max_flow,
                                "min_flow": min_flow,
                                "data_points_count": count,
                            }
                        )

                    if device_flow_stats:
                        # 企业级汇总：多设备流量按“求和”汇总（更符合排口/支路总量语义）
                        agg_avg_flow = sum(d["avg_flow"] for d in device_flow_stats)
                        agg_max_flow = max(d["max_flow"] for d in device_flow_stats)
                        agg_min_flow = min(d["min_flow"] for d in device_flow_stats)
                        agg_points = sum(d["data_points_count"] for d in device_flow_stats)

                        daily_volume_m3 = agg_avg_flow * 86400 / 1000
                        period_total_volume_m3 = agg_avg_flow * duration_seconds / 1000

                        flow_data = {
                            "avg_flow": round(agg_avg_flow, 4),
                            "max_flow": round(agg_max_flow, 4),
                            "min_flow": round(agg_min_flow, 4),
                            # Backward compatible key used by AI prompts ("日总流量"语义)
                            "total_volume": round(daily_volume_m3, 2),
                            "daily_volume_m3": round(daily_volume_m3, 2),
                            "period_total_volume_m3": round(period_total_volume_m3, 2),
                            "data_points_count": agg_points,
                            "device_count": len(device_flow_stats),
                            "devices": device_flow_stats,
                        }
                        logger.info(
                            "Flow data fetched for AI report",
                            org_id=str(flow_org_id),
                            device_count=len(device_flow_stats),
                            avg_flow=agg_avg_flow,
                            data_points=agg_points,
                        )
                    else:
                        logger.warning(
                            "No flow data found for period",
                            org_id=str(flow_org_id),
                            start_date=str(request.start_date),
                            end_date=str(request.end_date),
                        )
                else:
                    logger.warning("No devices found for organization", org_id=str(flow_org_id))
            except Exception as e:
                logger.warning("Failed to fetch flow data for AI report", error=str(e))
                # 继续生成报告，但不包含流量数据

        # 获取企业在线数据（全部指标）统计（如果启用）
        try:
            if not flow_org_id:
                raise ValueError("online_data requested but flow_org_id is empty")
            from app.models.monitoring_mysql import MonitoringDataMySQL
            from app.core.pollutant_library import get_pollutant_info
            from sqlalchemy import select, func

            start_time = datetime.combine(request.start_date, datetime.min.time())
            end_time = datetime.combine(request.end_date, datetime.max.time())

            rows = (
                await db.execute(
                    select(
                        MonitoringDataMySQL.pollutant_code,
                        func.max(MonitoringDataMySQL.pollutant_name).label("pollutant_name"),
                        func.min(MonitoringDataMySQL.value).label("min_value"),
                        func.max(MonitoringDataMySQL.value).label("max_value"),
                        func.avg(MonitoringDataMySQL.value).label("avg_value"),
                        func.count(MonitoringDataMySQL.id).label("count"),
                        func.count(func.distinct(MonitoringDataMySQL.device_id)).label("device_count"),
                    )
                    .where(
                        MonitoringDataMySQL.org_id == str(flow_org_id),
                        MonitoringDataMySQL.ts >= start_time,
                        MonitoringDataMySQL.ts <= end_time,
                    )
                    .group_by(MonitoringDataMySQL.pollutant_code)
                    .order_by(MonitoringDataMySQL.pollutant_code)
                )
            ).all()

            pollutants: list[dict[str, Any]] = []
            for code, name, min_v, max_v, avg_v, cnt, dev_cnt in rows:
                info = get_pollutant_info(code) or {}
                pollutants.append(
                    {
                        "pollutant_code": code,
                        "pollutant_name": info.get("name") or (name or code),
                        "unit": info.get("unit"),
                        "min": float(min_v) if min_v is not None else None,
                        "max": float(max_v) if max_v is not None else None,
                        "avg": float(avg_v) if avg_v is not None else None,
                        "count": int(cnt or 0),
                        "device_count": int(dev_cnt or 0),
                    }
                )

            online_data = {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "pollutants": pollutants,
                "note": "在线数据来自数采仪实测；第三方检测报告数据为人工/实验室检测，二者可用于交叉验证。",
            }
        except Exception as e:
            logger.warning("Failed to fetch online monitoring data for AI report", error=str(e))

    # 检查是否配置了讯飞星火（从环境变量读取）
    spark_client = get_spark_client()
    if not spark_client:
        # 返回简化版报告（无AI）
        period = f"{request.start_date} 至 {request.end_date}"
        stats_lines = [
            f"- {stats['name']}：平均值 {stats['avg']:.2f}，范围 {stats['min']:.2f} - {stats['max']:.2f}"
            for code, stats in trend_result["statistics"].items()
        ]
        summary = f"## 数据概述\n\n本报告周期（{period}）共有 {len(trend_result['data_points'])} 条检测数据。\n\n## 统计信息\n\n" + "\n".join(stats_lines)

        # 如果有流量数据，添加到摘要中
        if flow_data:
            summary += (
                "\n\n## 流量数据（数采仪）\n\n"
                f"- 平均流量：{flow_data['avg_flow']:.2f} L/s\n"
                f"- 日总流量：{flow_data.get('daily_volume_m3', flow_data['total_volume']):.2f} m³\n"
                f"- 周期总流量：{flow_data.get('period_total_volume_m3', 0):.2f} m³"
            )

        # 如果有在线数据，添加到摘要中（按指标汇总）
        if online_data and isinstance(online_data, dict):
            pols = online_data.get("pollutants") or []
            lines: list[str] = []
            for p in pols[:10]:
                try:
                    name = p.get("pollutant_name") or p.get("pollutant_code")
                    unit = p.get("unit") or ""
                    avg = p.get("avg")
                    mn = p.get("min")
                    mx = p.get("max")
                    cnt = p.get("count")
                    if avg is None or mn is None or mx is None:
                        continue
                    lines.append(f"- {name}：均值 {avg:.3f}{unit}，范围 {mn:.3f}-{mx:.3f}{unit}（{cnt} 点）")
                except Exception:
                    continue
            if lines:
                summary += "\n\n## 在线监测数据统计（数采仪）\n\n" + "\n".join(lines)

        return AIReportResponse(
            period=period,
            generated_at=datetime.utcnow(),
            summary=summary,
            recommendations=["建议定期检查处理设施运行状态", "建议保持监测频率", "建议关注指标变化趋势"],
            flow_data=flow_data,
            online_data=online_data,
        )

    # 使用AI生成报告
    generator = AIReportGenerator(spark_client)

    # 获取组织名称
    org_name = "全部组织" if org_id is None else None
    if org_id is not None:
        from app.models.organization import Organization
        from sqlalchemy import select
        org_result = await db.execute(select(Organization).where(Organization.id == org_id))
        org = org_result.scalar_one_or_none()
        org_name = org.name if org else "企业"

    period = f"{request.start_date} 至 {request.end_date}"

    try:
        result = await generator.generate_report(
            org_name=org_name,
            period=period,
            data_summary=trend_result["statistics"],
            trend_data=trend_result["data_points"],
            flow_data=flow_data,
            online_data=online_data,
            calculate_pollutant_load=request.calculate_pollutant_load,
        )

        return AIReportResponse(
            period=result["period"],
            generated_at=result["generated_at"],
            summary=result["summary"],
            recommendations=result["recommendations"],
            data_source_note=result["data_source_note"],
            flow_data=flow_data,
            online_data=online_data,
            pollutant_loads=result.get("pollutant_loads"),
        )

    except Exception as e:
        logger.error("AI report generation failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI报告生成失败，请稍后重试",
        )
