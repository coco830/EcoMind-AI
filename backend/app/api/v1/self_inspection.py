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
)
from app.api.deps import get_current_active_user
from app.services.self_inspection_service import (
    SelfInspectionService,
    BaiduOCRClient,
    OCRParserService,
    TableOCRParser,
    AIDataExtractor,
    AIReportGenerator,
    get_self_inspection_service,
)
from app.core.config import get_settings

router = APIRouter()
logger = structlog.get_logger()
settings = get_settings()

# 文件上传目录
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "uploads", "self_inspection")
os.makedirs(UPLOAD_DIR, exist_ok=True)


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
            detail="超级管理员需要指定目标组织ID",
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
    inspection_date: Annotated[date | None, Form(description="检测日期（可选，AI会自动识别）")] = None,
    inspection_agency: Annotated[str | None, Form(description="检测机构名称（可选，AI会自动识别）")] = None,
    report_number: Annotated[str | None, Form(description="报告编号")] = None,
    target_org_id: Annotated[UUID | None, Form(description="目标组织ID（超级管理员专用）")] = None,
    use_ai_parsing: Annotated[bool, Form(description="是否使用AI智能解析")] = True,
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
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
    org_id = _get_user_org_id(current_user, target_org_id=target_org_id)

    # 验证文件类型
    allowed_types = ["application/pdf", "image/jpeg", "image/png", "image/jpg"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型: {file.content_type}。支持: PDF, JPG, PNG",
        )

    # 读取文件内容
    file_content = await file.read()

    # 保存原始文件
    file_ext = file.filename.split(".")[-1] if file.filename else "pdf"
    saved_filename = f"{uuid4()}.{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, saved_filename)

    with open(file_path, "wb") as f:
        f.write(file_content)

    logger.info("File uploaded", filename=file.filename, saved_as=saved_filename)

    # 初始化变量
    recognized_data = []
    ocr_confidence = None
    raw_text = None
    ai_extracted_info = {}

    # 检查是否配置了百度OCR
    baidu_api_key = os.getenv("BAIDU_OCR_API_KEY", "")
    baidu_secret_key = os.getenv("BAIDU_OCR_SECRET_KEY", "")

    if baidu_api_key and baidu_secret_key:
        try:
            ocr_client = BaiduOCRClient(baidu_api_key, baidu_secret_key)

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
            if use_ai_parsing and raw_text and settings.spark_app_id and settings.spark_api_key:
                try:
                    from app.services.llm.spark_client import SparkClient

                    spark_client = SparkClient(
                        app_id=settings.spark_app_id,
                        api_secret=settings.spark_api_secret,
                        api_key=settings.spark_api_key,
                        spark_url=settings.spark_api_url,
                        domain=settings.spark_domain,
                    )

                    ai_extractor = AIDataExtractor(spark_client)
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
    final_inspection_date = inspection_date
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
    report.original_file_path = file_path
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
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    target_org_id: UUID | None = Query(None, description="目标组织ID（超级管理员专用）"),
) -> SelfInspectionReportResponse:
    """
    手动创建自检报告（不通过OCR）。
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
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
) -> PaginatedReportListResponse:
    """
    获取自检报告列表。
    超级管理员可以查看所有组织的报告。
    """
    org_id = _get_user_org_id(current_user, allow_superadmin_all=True)
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
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SelfInspectionReportResponse:
    """
    更新报告（校验/修正数据）。
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
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """
    删除报告。
    超级管理员可以删除任何组织的报告。
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


@router.post("/analysis/trend", response_model=TrendAnalysisResponse)
async def get_trend_analysis(
    request: TrendAnalysisRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TrendAnalysisResponse:
    """
    获取趋势分析数据。
    仅分析已校验的报告数据。
    超级管理员可以查看所有组织的趋势数据。
    """
    org_id = _get_user_org_id(current_user, allow_superadmin_all=True)
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
    """
    org_id = _get_user_org_id(current_user, allow_superadmin_all=True)
    service = get_self_inspection_service(db)

    # 获取趋势数据
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

    # 检查是否配置了讯飞星火
    if not settings.spark_app_id or not settings.spark_api_key:
        # 返回简化版报告（无AI）
        period = f"{request.start_date} 至 {request.end_date}"
        stats_lines = [
            f"- {stats['name']}：平均值 {stats['avg']:.2f}，范围 {stats['min']:.2f} - {stats['max']:.2f}"
            for code, stats in trend_result["statistics"].items()
        ]
        return AIReportResponse(
            period=period,
            generated_at=datetime.utcnow(),
            summary=f"## 数据概述\n\n本报告周期（{period}）共有 {len(trend_result['data_points'])} 条检测数据。\n\n## 统计信息\n\n" + "\n".join(stats_lines),
            recommendations=["建议定期检查处理设施运行状态", "建议保持监测频率", "建议关注指标变化趋势"],
        )

    # 使用AI生成报告
    from app.services.llm.spark_client import SparkClient

    spark_client = SparkClient(
        app_id=settings.spark_app_id,
        api_secret=settings.spark_api_secret,
        api_key=settings.spark_api_key,
        spark_url=settings.spark_api_url,
        domain=settings.spark_domain,
    )

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
        )

        return AIReportResponse(
            period=result["period"],
            generated_at=result["generated_at"],
            summary=result["summary"],
            recommendations=result["recommendations"],
            data_source_note=result["data_source_note"],
        )

    except Exception as e:
        logger.error("AI report generation failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI报告生成失败，请稍后重试",
        )
