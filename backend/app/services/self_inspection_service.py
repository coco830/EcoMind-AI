from __future__ import annotations

"""
自检档案服务层

提供：
- 百度OCR识别检测报告
- 自检数据CRUD操作
- 趋势分析
- AI运维报告生成
"""

import io
import re
from datetime import date, datetime
from typing import Any
from uuid import UUID

import httpx
import structlog
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.self_inspection import (
    SelfInspectionReport,
    SelfInspectionData,
    SelfInspectionReportCreate,
    SelfInspectionReportUpdate,
    SelfInspectionDataCreate,
    InspectionStatus,
)
from app.protocols.enums import PARAMETER_DESCRIPTIONS, PARAMETER_UNITS

logger = structlog.get_logger(__name__)
settings = get_settings()


class BaiduOCRClient:
    """百度OCR客户端 - 支持通用文字识别和表格识别"""

    TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
    # 通用文字识别（高精度版）
    OCR_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic"
    # 表格文字识别V2
    TABLE_OCR_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/table"
    # 通用文字识别（含位置信息）
    GENERAL_OCR_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/general"

    def __init__(self, api_key: str | None = None, secret_key: str | None = None):
        """
        初始化百度OCR客户端

        Args:
            api_key: 百度OCR API Key，若为None则从环境变量读取
            secret_key: 百度OCR Secret Key，若为None则从环境变量读取
        """
        # 从配置读取（优先使用传入参数）
        self.api_key = api_key or settings.baidu_ocr_api_key
        self.secret_key = secret_key or settings.baidu_ocr_secret_key

        if not self.api_key or not self.secret_key:
            logger.warning("Baidu OCR credentials not configured")

        self._access_token: str | None = None
        self._token_expires: datetime | None = None

    async def _get_access_token(self) -> str:
        """获取百度OCR access token"""
        if self._access_token and self._token_expires and datetime.now() < self._token_expires:
            return self._access_token

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                params={
                    "grant_type": "client_credentials",
                    "client_id": self.api_key,
                    "client_secret": self.secret_key,
                },
            )
            response.raise_for_status()
            data = response.json()
            self._access_token = data["access_token"]
            # Token有效期30天，提前1天刷新
            from datetime import timedelta
            self._token_expires = datetime.now() + timedelta(days=29)
            return self._access_token

    async def recognize_document(self, file_content: bytes) -> dict[str, Any]:
        """
        识别文档内容（通用文字识别）

        Args:
            file_content: 文件二进制内容（支持PDF/图片）

        Returns:
            OCR识别结果
        """
        import base64

        access_token = await self._get_access_token()

        # Base64编码
        image_base64 = base64.b64encode(file_content).decode("utf-8")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.OCR_URL}?access_token={access_token}",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={"image": image_base64, "detect_direction": "true"},
            )
            response.raise_for_status()
            return response.json()

    async def recognize_table(self, file_content: bytes) -> dict[str, Any]:
        """
        表格文字识别 - 自动检测并返回表格内容

        Args:
            file_content: 文件二进制内容（支持图片）

        Returns:
            表格识别结果，包含表格结构化数据
            {
                "tables_result": [
                    {
                        "table_location": {...},
                        "header": [...],
                        "body": [
                            {"row_start": 0, "row_end": 0, "col_start": 0, "col_end": 0, "words": "..."},
                            ...
                        ]
                    }
                ],
                "table_num": 1
            }
        """
        import base64

        access_token = await self._get_access_token()
        image_base64 = base64.b64encode(file_content).decode("utf-8")

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.TABLE_OCR_URL}?access_token={access_token}",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "image": image_base64,
                    "return_excel": "false",  # 不需要Excel，我们用结构化数据
                },
            )
            response.raise_for_status()
            return response.json()

    async def recognize_pdf_tables(self, pdf_content: bytes) -> list[dict[str, Any]]:
        """
        识别PDF中的表格 - 将PDF转换为图片后识别

        Args:
            pdf_content: PDF文件二进制内容

        Returns:
            每页的表格识别结果列表
        """
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.warning("PyMuPDF not installed, using basic OCR for PDF")
            return [await self.recognize_document(pdf_content)]

        results = []
        pdf_document = fitz.open(stream=pdf_content, filetype="pdf")

        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            # 提高分辨率以获得更好的识别效果
            mat = fitz.Matrix(2.0, 2.0)  # 2倍缩放
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")

            try:
                # 先尝试表格识别
                table_result = await self.recognize_table(img_bytes)
                if table_result.get("table_num", 0) > 0:
                    table_result["page_num"] = page_num + 1
                    results.append(table_result)
                else:
                    # 如果没有检测到表格，使用通用OCR
                    text_result = await self.recognize_document(img_bytes)
                    text_result["page_num"] = page_num + 1
                    text_result["is_text_only"] = True
                    results.append(text_result)
            except Exception as e:
                logger.error(f"OCR failed for page {page_num + 1}", error=str(e))
                continue

        pdf_document.close()
        return results


class SelfInspectionService:
    """自检档案服务"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def create_report(
        self,
        org_id: UUID,
        data: SelfInspectionReportCreate,
    ) -> SelfInspectionReport:
        """创建自检报告"""
        report = SelfInspectionReport(
            org_id=org_id,
            inspection_date=data.inspection_date,
            inspection_agency=data.inspection_agency,
            report_number=data.report_number,
            remarks=data.remarks,
            status=InspectionStatus.PENDING.value,
        )
        self.db.add(report)
        await self.db.flush()

        # 添加数据项
        for item_data in data.data_items:
            item = SelfInspectionData(
                report_id=report.id,
                pollutant_code=item_data.pollutant_code,
                pollutant_name=item_data.pollutant_name,
                value=item_data.value,
                unit=item_data.unit,
                standard_limit=item_data.standard_limit,
                is_compliant=item_data.is_compliant,
                sampling_point=item_data.sampling_point,
                sampling_time=item_data.sampling_time,
                remarks=item_data.remarks,
            )
            self.db.add(item)

        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def get_report(self, report_id: UUID, org_id: UUID | None) -> SelfInspectionReport | None:
        """获取单个报告详情

        Args:
            report_id: 报告ID
            org_id: 组织ID，为None时表示超级管理员查看任意报告
        """
        conditions = [SelfInspectionReport.id == report_id]
        if org_id is not None:
            conditions.append(SelfInspectionReport.org_id == org_id)

        result = await self.db.execute(
            select(SelfInspectionReport)
            .options(selectinload(SelfInspectionReport.data_items))
            .where(and_(*conditions))
        )
        return result.scalar_one_or_none()

    async def list_reports(
        self,
        org_id: UUID | None,
        start_date: date | None = None,
        end_date: date | None = None,
        status: InspectionStatus | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict], int]:
        """获取报告列表

        Args:
            org_id: 组织ID，为None时表示超级管理员查看所有组织报告
        """
        # 构建查询条件
        conditions = []
        if org_id is not None:
            conditions.append(SelfInspectionReport.org_id == org_id)
        if start_date:
            conditions.append(SelfInspectionReport.inspection_date >= start_date)
        if end_date:
            conditions.append(SelfInspectionReport.inspection_date <= end_date)
        if status:
            conditions.append(SelfInspectionReport.status == status.value)

        # 查询总数
        count_query = select(func.count(SelfInspectionReport.id)).where(and_(*conditions))
        total = (await self.db.execute(count_query)).scalar() or 0

        # 查询列表（包含数据项数量）
        query = (
            select(
                SelfInspectionReport,
                func.count(SelfInspectionData.id).label("data_count"),
            )
            .outerjoin(SelfInspectionData)
            .where(and_(*conditions))
            .group_by(SelfInspectionReport.id)
            .order_by(SelfInspectionReport.inspection_date.desc())
            .offset(skip)
            .limit(limit)
        )

        result = await self.db.execute(query)
        rows = result.all()

        reports = []
        for row in rows:
            report = row[0]
            data_count = row[1]
            reports.append({
                "id": report.id,
                "org_id": report.org_id,
                "inspection_date": report.inspection_date,
                "inspection_agency": report.inspection_agency,
                "report_number": report.report_number,
                "original_file_name": report.original_file_name,
                "status": report.status,
                "is_verified": report.is_verified,
                "data_count": data_count,
                "created_at": report.created_at,
            })

        return reports, total

    async def update_report(
        self,
        report_id: UUID,
        org_id: UUID | None,
        data: SelfInspectionReportUpdate,
        verified_by: UUID | None = None,
    ) -> SelfInspectionReport | None:
        """更新报告

        Args:
            report_id: 报告ID
            org_id: 组织ID，为None时表示超级管理员可更新任意报告
        """
        report = await self.get_report(report_id, org_id)
        if not report:
            return None

        # 更新基本信息
        if data.inspection_date is not None:
            report.inspection_date = data.inspection_date
        if data.inspection_agency is not None:
            report.inspection_agency = data.inspection_agency
        if data.report_number is not None:
            report.report_number = data.report_number
        if data.status is not None:
            report.status = data.status.value
            if data.status == InspectionStatus.VERIFIED:
                report.is_verified = True
                report.verified_by = verified_by
                report.verified_at = datetime.utcnow()
        if data.remarks is not None:
            report.remarks = data.remarks

        # 更新数据项（如果提供）
        if data.data_items is not None:
            # 删除旧数据项
            for item in report.data_items:
                await self.db.delete(item)

            # 添加新数据项
            for item_data in data.data_items:
                item = SelfInspectionData(
                    report_id=report.id,
                    pollutant_code=item_data.pollutant_code,
                    pollutant_name=item_data.pollutant_name,
                    value=item_data.value,
                    unit=item_data.unit,
                    standard_limit=item_data.standard_limit,
                    is_compliant=item_data.is_compliant,
                    sampling_point=item_data.sampling_point,
                    sampling_time=item_data.sampling_time,
                    remarks=item_data.remarks,
                )
                self.db.add(item)

        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def delete_report(self, report_id: UUID, org_id: UUID | None) -> bool:
        """删除报告

        Args:
            report_id: 报告ID
            org_id: 组织ID，为None时表示超级管理员可删除任意报告
        """
        report = await self.get_report(report_id, org_id)
        if not report:
            return False

        await self.db.delete(report)
        await self.db.commit()
        return True

    async def get_trend_analysis(
        self,
        org_id: UUID | None,
        start_date: date,
        end_date: date,
        pollutant_codes: list[str] | None = None,
    ) -> dict[str, Any]:
        """获取趋势分析数据

        Args:
            org_id: 组织ID，为None时表示超级管理员查看所有组织数据
        """
        # 查询时间范围内的所有数据
        conditions = [
            SelfInspectionReport.inspection_date >= start_date,
            SelfInspectionReport.inspection_date <= end_date,
            SelfInspectionReport.status == InspectionStatus.VERIFIED.value,
        ]
        if org_id is not None:
            conditions.append(SelfInspectionReport.org_id == org_id)

        query = (
            select(
                SelfInspectionReport.inspection_date,
                SelfInspectionData.pollutant_code,
                SelfInspectionData.pollutant_name,
                SelfInspectionData.value,
                SelfInspectionData.unit,
                SelfInspectionData.standard_limit,
                SelfInspectionData.is_compliant,
            )
            .join(SelfInspectionData)
            .where(and_(*conditions))
        )

        if pollutant_codes:
            query = query.where(SelfInspectionData.pollutant_code.in_(pollutant_codes))

        query = query.order_by(
            SelfInspectionReport.inspection_date,
            SelfInspectionData.pollutant_code,
        )

        result = await self.db.execute(query)
        rows = result.all()

        # 构建数据点
        data_points = []
        for row in rows:
            data_points.append({
                "date": row[0],
                "pollutant_code": row[1],
                "pollutant_name": row[2],
                "value": row[3],
                "unit": row[4],
                "standard_limit": row[5],
                "is_compliant": row[6],
            })

        # 计算统计信息
        statistics = {}
        if data_points:
            from collections import defaultdict
            pollutant_values = defaultdict(list)
            for dp in data_points:
                pollutant_values[dp["pollutant_code"]].append(dp["value"])

            for code, values in pollutant_values.items():
                statistics[code] = {
                    "count": len(values),
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values),
                    "name": PARAMETER_DESCRIPTIONS.get(code, code),
                }

        return {
            "start_date": start_date,
            "end_date": end_date,
            "data_points": data_points,
            "statistics": statistics,
        }


class OCRParserService:
    """OCR结果解析服务"""

    # 常见污染物名称到代码的映射
    POLLUTANT_NAME_MAP = {
        "化学需氧量": "w01018",
        "COD": "w01018",
        "氨氮": "w21003",
        "总磷": "w21011",
        "总氮": "w21001",
        "悬浮物": "w01012",
        "SS": "w01012",
        "pH": "w01001",
        "pH值": "w01001",
        "五日生化需氧量": "w01017",
        "BOD5": "w01017",
        "BOD": "w01017",
        "色度": "w01003",
        "动植物油": "w02003",
        "石油类": "w22001",
        "阴离子表面活性剂": "w19002",
        "LAS": "w19002",
        "总汞": "w20111",
        "汞": "w20111",
        "总镉": "w20115",
        "镉": "w20115",
        "总铬": "w20117",
        "铬": "w20117",
        "六价铬": "w20119",
        "总砷": "w20141",
        "砷": "w20141",
        "总铅": "w20120",
        "铅": "w20120",
        "总镍": "w20121",
        "镍": "w20121",
        "总铜": "w20122",
        "铜": "w20122",
        "总锌": "w20123",
        "锌": "w20123",
        "粪大肠菌群": "w02001",
        "瞬时流量": "w00000",
        "流量": "w00000",
    }

    @classmethod
    def parse_ocr_result(cls, ocr_result: dict) -> list[SelfInspectionDataCreate]:
        """
        解析OCR识别结果，提取污染物数据

        Args:
            ocr_result: 百度OCR返回的结果

        Returns:
            解析出的污染物数据列表
        """
        if "words_result" not in ocr_result:
            return []

        # 提取所有文本行
        lines = [item["words"] for item in ocr_result.get("words_result", [])]
        full_text = "\n".join(lines)

        logger.debug("OCR full text", text=full_text[:500])

        parsed_data = []

        # 尝试匹配表格格式的数据
        # 常见格式：污染物名称 | 检测值 | 单位 | 标准限值
        for line in lines:
            # 尝试匹配各种格式
            data = cls._try_parse_line(line)
            if data:
                parsed_data.append(data)

        # 如果表格解析失败，尝试正则匹配
        if not parsed_data:
            parsed_data = cls._regex_parse(full_text)

        return parsed_data

    @classmethod
    def _try_parse_line(cls, line: str) -> SelfInspectionDataCreate | None:
        """尝试解析单行数据"""
        # 清理空格
        line = line.strip()

        # 跳过表头行
        if any(header in line for header in ["检测项目", "项目名称", "监测项目", "序号"]):
            return None

        # 尝试匹配污染物名称
        for name, code in cls.POLLUTANT_NAME_MAP.items():
            if name in line:
                # 提取数值
                numbers = re.findall(r"(\d+\.?\d*)", line)
                if numbers:
                    value = float(numbers[0])
                    standard_limit = float(numbers[1]) if len(numbers) > 1 else None

                    # 判断是否达标
                    is_compliant = True
                    if standard_limit and value > standard_limit:
                        is_compliant = False

                    return SelfInspectionDataCreate(
                        pollutant_code=code,
                        pollutant_name=name,
                        value=value,
                        unit=PARAMETER_UNITS.get(code, "mg/L"),
                        standard_limit=standard_limit,
                        is_compliant=is_compliant,
                    )

        return None

    @classmethod
    def _regex_parse(cls, text: str) -> list[SelfInspectionDataCreate]:
        """使用正则表达式解析全文"""
        parsed_data = []

        for name, code in cls.POLLUTANT_NAME_MAP.items():
            # 匹配格式：污染物名称 + 数值
            pattern = rf"{re.escape(name)}[：:\s]*(\d+\.?\d*)\s*(mg/L|mg/m³|pH|倍|个/L)?"
            matches = re.findall(pattern, text, re.IGNORECASE)

            for match in matches:
                value = float(match[0])
                unit = match[1] if match[1] else PARAMETER_UNITS.get(code, "mg/L")

                parsed_data.append(SelfInspectionDataCreate(
                    pollutant_code=code,
                    pollutant_name=name,
                    value=value,
                    unit=unit,
                    is_compliant=True,  # 默认达标，需要人工校验
                ))

        return parsed_data


class TableOCRParser:
    """表格OCR结果解析器 - 专门处理百度表格识别API返回的结构化数据"""

    @staticmethod
    def parse_table_result(table_result: dict) -> list[list[str]]:
        """
        将百度表格OCR结果转换为二维数组

        Args:
            table_result: 百度表格OCR返回的单个表格数据

        Returns:
            二维数组格式的表格数据
        """
        if "body" not in table_result:
            return []

        # 找出表格的行列范围
        body = table_result["body"]
        if not body:
            return []

        max_row = max(cell.get("row_end", 0) for cell in body) + 1
        max_col = max(cell.get("col_end", 0) for cell in body) + 1

        # 初始化二维数组
        table = [["" for _ in range(max_col)] for _ in range(max_row)]

        # 填充数据
        for cell in body:
            row = cell.get("row_start", 0)
            col = cell.get("col_start", 0)
            words = cell.get("words", "")
            if 0 <= row < max_row and 0 <= col < max_col:
                table[row][col] = words

        return table

    @staticmethod
    def tables_to_text(ocr_results: list[dict]) -> str:
        """
        将所有OCR结果转换为文本格式，便于AI处理

        Args:
            ocr_results: 多页OCR结果

        Returns:
            格式化的文本内容
        """
        text_parts = []

        for result in ocr_results:
            page_num = result.get("page_num", "?")

            # 处理表格数据
            if "tables_result" in result:
                for i, table in enumerate(result["tables_result"]):
                    table_data = TableOCRParser.parse_table_result(table)
                    if table_data:
                        text_parts.append(f"\n=== 第{page_num}页 表格{i+1} ===")
                        for row in table_data:
                            text_parts.append(" | ".join(str(cell) for cell in row))

            # 处理纯文本数据
            elif "words_result" in result:
                text_parts.append(f"\n=== 第{page_num}页 文本内容 ===")
                for item in result["words_result"]:
                    text_parts.append(item.get("words", ""))

        return "\n".join(text_parts)


class AIDataExtractor:
    """AI智能数据提取器 - 使用大模型从OCR结果中提取结构化检测数据"""

    # 污染物代码映射（用于标准化）
    POLLUTANT_CODE_MAP = OCRParserService.POLLUTANT_NAME_MAP

    def __init__(self, spark_client):
        """
        初始化AI数据提取器

        Args:
            spark_client: 讯飞星火客户端
        """
        self.spark = spark_client

    async def extract_inspection_data(
        self,
        ocr_text: str,
        file_name: str | None = None,
    ) -> dict[str, Any]:
        """
        使用AI从OCR文本中提取检测数据

        Args:
            ocr_text: OCR识别的文本内容（包含表格数据）
            file_name: 原始文件名（可能包含企业名称等信息）

        Returns:
            {
                "enterprise_name": "企业名称",
                "inspection_date": "检测日期",
                "inspection_agency": "检测机构",
                "report_number": "报告编号",
                "reference_standard": "参考标准",
                "data_items": [
                    {
                        "pollutant_name": "污染物名称",
                        "pollutant_code": "污染物代码",
                        "value": 检测值,
                        "unit": "单位",
                        "standard_limit": 标准限值,
                        "is_compliant": true/false,
                        "sampling_point": "采样点",
                        "detection_method": "检测方法"
                    },
                    ...
                ],
                "ai_confidence": 0.85,
                "extraction_notes": "提取过程中的备注"
            }
        """
        prompt = self._build_extraction_prompt(ocr_text, file_name)

        messages = [{"role": "user", "content": prompt}]
        response_chunks = []

        try:
            async for chunk in self.spark.chat_stream(messages):
                response_chunks.append(chunk)

            full_response = "".join(response_chunks)
            logger.debug("AI extraction response", response=full_response[:500])

            # 解析AI响应
            return self._parse_ai_response(full_response)

        except Exception as e:
            logger.error("AI extraction failed", error=str(e))
            return {
                "data_items": [],
                "ai_confidence": 0,
                "extraction_notes": f"AI解析失败: {str(e)}",
            }

    def _build_extraction_prompt(self, ocr_text: str, file_name: str | None) -> str:
        """构建数据提取Prompt"""

        # 限制文本长度避免超出token限制
        max_text_length = 8000
        if len(ocr_text) > max_text_length:
            ocr_text = ocr_text[:max_text_length] + "\n...(内容过长已截断)"

        prompt = f"""你是一位专业的环境检测报告数据提取专家。请从以下OCR识别的检测报告内容中，提取结构化的检测数据。

## 文件信息
文件名：{file_name or "未知"}

## OCR识别内容
{ocr_text}

## 提取要求
请提取以下信息，并以JSON格式返回：

1. **基本信息**：
   - enterprise_name: 被检测企业名称
   - inspection_date: 检测日期（格式：YYYY-MM-DD）
   - inspection_agency: 检测机构名称
   - report_number: 报告编号
   - reference_standard: 参考的排放标准（如 GB 18466-2005）

2. **检测数据**（data_items数组）：
   对于每个检测项目，提取：
   - pollutant_name: 污染物名称（如：COD、氨氮、pH值、悬浮物、粪大肠菌群等）
   - value: 检测值（数字）
   - unit: 单位（如：mg/L、pH、个/L、倍等）
   - standard_limit: 标准限值（数字，如果有）
   - is_compliant: 是否达标（true/false，通过对比检测值和标准限值判断）
   - sampling_point: 采样点位置（如果有）
   - detection_method: 检测方法（如果有）

## 重要说明
- 只提取"检测结果"表格中的有效数据，忽略采样信息、仪器信息等
- pH值特殊处理：标准通常是范围（如6-9），检测值在范围内即为达标
- 粪大肠菌群单位通常是"个/L"或"MPN/L"
- 如果某项数据无法确定，可以设为null
- 只提取明确的检测数据，不要猜测

## 返回格式
请严格按以下JSON格式返回，不要包含其他内容：
```json
{{
  "enterprise_name": "xxx",
  "inspection_date": "YYYY-MM-DD",
  "inspection_agency": "xxx",
  "report_number": "xxx",
  "reference_standard": "xxx",
  "data_items": [
    {{
      "pollutant_name": "xxx",
      "value": 0.0,
      "unit": "xxx",
      "standard_limit": 0.0,
      "is_compliant": true,
      "sampling_point": "xxx",
      "detection_method": "xxx"
    }}
  ],
  "extraction_notes": "提取过程中的备注或不确定项说明"
}}
```"""

        return prompt

    def _parse_ai_response(self, response: str) -> dict[str, Any]:
        """解析AI返回的JSON响应"""
        import json

        # 尝试提取JSON部分
        json_match = re.search(r"```json\s*([\s\S]*?)\s*```", response)
        if json_match:
            json_str = json_match.group(1)
        else:
            # 尝试直接解析整个响应
            json_str = response.strip()
            # 移除可能的markdown代码块标记
            if json_str.startswith("```"):
                lines = json_str.split("\n")
                json_str = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        try:
            result = json.loads(json_str)

            # 标准化污染物代码
            if "data_items" in result:
                for item in result["data_items"]:
                    name = item.get("pollutant_name", "")
                    if name and name in self.POLLUTANT_CODE_MAP:
                        item["pollutant_code"] = self.POLLUTANT_CODE_MAP[name]
                    else:
                        # 尝试模糊匹配
                        for known_name, code in self.POLLUTANT_CODE_MAP.items():
                            if known_name in name or name in known_name:
                                item["pollutant_code"] = code
                                break
                        else:
                            item["pollutant_code"] = None

            # 计算置信度（基于提取的数据量）
            data_count = len(result.get("data_items", []))
            has_basic_info = all([
                result.get("enterprise_name"),
                result.get("inspection_agency"),
            ])
            result["ai_confidence"] = min(0.5 + data_count * 0.1 + (0.2 if has_basic_info else 0), 0.95)

            return result

        except json.JSONDecodeError as e:
            logger.error("Failed to parse AI response as JSON", error=str(e), response=response[:500])
            return {
                "data_items": [],
                "ai_confidence": 0,
                "extraction_notes": f"JSON解析失败: {str(e)}",
            }


class AIReportGenerator:
    """AI运维报告生成器"""

    def __init__(self, spark_client):
        """
        初始化AI报告生成器

        Args:
            spark_client: 讯飞星火客户端
        """
        self.spark = spark_client

    async def generate_report(
        self,
        org_name: str,
        period: str,
        data_summary: dict[str, Any],
        trend_data: list[dict],
        flow_data: dict[str, Any] | None = None,
        online_data: dict[str, Any] | None = None,
        calculate_pollutant_load: bool = False,
    ) -> dict[str, Any]:
        """
        生成AI运维报告

        Args:
            org_name: 企业名称
            period: 报告周期（如"2024年1月"）
            data_summary: 数据统计摘要
            trend_data: 趋势数据
            flow_data: 数采仪流量数据（可选，来自monitoring_data表）
            online_data: 数采仪在线数据统计（可选，按指标汇总）
            calculate_pollutant_load: 是否计算污染负荷

        Returns:
            AI生成的报告内容
        """
        # 计算污染负荷（如果启用且有流量数据）
        pollutant_loads = None
        if calculate_pollutant_load and flow_data:
            pollutant_loads = self._calculate_pollutant_loads(data_summary, flow_data)

        # 构建Prompt
        prompt = self._build_report_prompt(
            org_name, period, data_summary, trend_data, flow_data, online_data, pollutant_loads
        )

        # 调用AI生成
        messages = [{"role": "user", "content": prompt}]
        response_chunks = []

        async for chunk in self.spark.chat_stream(messages):
            response_chunks.append(chunk)

        full_response = "".join(response_chunks)

        # 解析AI响应
        result = self._parse_ai_response(full_response, period)

        # 添加污染负荷数据到结果
        if pollutant_loads:
            result["pollutant_loads"] = pollutant_loads

        return result

    def _calculate_pollutant_loads(
        self,
        data_summary: dict[str, Any],
        flow_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        计算污染负荷（污染物浓度 × 流量）

        Args:
            data_summary: 检测数据统计（浓度数据，来自第三方检测报告）
            flow_data: 流量统计数据（来自数采仪）

        Returns:
            各污染物的污染负荷数据
        """
        loads = {}

        # 流量数据：平均流量(L/s) → 转换为 m³/day
        avg_flow_ls = flow_data.get("avg_flow", 0)  # L/s
        daily_volume_m3 = avg_flow_ls * 86400 / 1000  # m³/day

        for code, stats in data_summary.items():
            # 跳过流量本身和pH等无量纲参数
            if code in ("w00000", "w01001"):
                continue

            avg_concentration = stats.get("avg", 0)  # mg/L
            pollutant_name = stats.get("name", code)

            # 污染负荷 = 浓度(mg/L) × 日流量(m³/day) / 1000 = kg/day
            daily_load_kg = avg_concentration * daily_volume_m3 / 1000

            loads[code] = {
                "name": pollutant_name,
                "avg_concentration_mg_l": round(avg_concentration, 3),
                "daily_volume_m3": round(daily_volume_m3, 2),
                "daily_load_kg": round(daily_load_kg, 4),
                "monthly_load_kg": round(daily_load_kg * 30, 2),
                "formula": "污染负荷(kg/d) = 浓度(mg/L) × 日流量(m³/d) ÷ 1000",
            }

        return {
            "flow_source": "数采仪实测数据",
            "concentration_source": "第三方检测报告",
            "avg_flow_l_s": round(avg_flow_ls, 2),
            "daily_volume_m3": round(daily_volume_m3, 2),
            "pollutant_loads": loads,
            "note": "污染负荷计算采用数采仪实测流量与第三方检测浓度数据",
        }

    def _build_report_prompt(
        self,
        org_name: str,
        period: str,
        data_summary: dict[str, Any],
        trend_data: list[dict],
        flow_data: dict[str, Any] | None = None,
        online_data: dict[str, Any] | None = None,
        pollutant_loads: dict[str, Any] | None = None,
    ) -> str:
        """构建报告生成Prompt"""
        # 格式化数据摘要
        summary_text = []
        for code, stats in data_summary.items():
            summary_text.append(
                f"- {stats['name']}：平均值 {stats['avg']:.2f}，"
                f"最小值 {stats['min']:.2f}，最大值 {stats['max']:.2f}，"
                f"检测次数 {stats['count']}"
            )

        # 格式化趋势描述
        trend_text = []
        if trend_data:
            from collections import defaultdict
            by_pollutant = defaultdict(list)
            for dp in trend_data:
                by_pollutant[dp["pollutant_name"]].append(dp)

            for name, points in by_pollutant.items():
                if len(points) >= 2:
                    first_val = points[0]["value"]
                    last_val = points[-1]["value"]
                    change = ((last_val - first_val) / first_val * 100) if first_val > 0 else 0
                    trend = "上升" if change > 5 else "下降" if change < -5 else "稳定"
                    trend_text.append(f"- {name}：{trend}趋势（变化率 {change:.1f}%）")

        # 格式化流量数据（来自数采仪）
        flow_text = ""
        if flow_data:
            flow_text = f"""
## 实时流量数据（数采仪）
- 数据来源：环境监测数采仪（实测数据，可信度高）
- 平均流量：{flow_data.get('avg_flow', 0):.2f} L/s
- 最大流量：{flow_data.get('max_flow', 0):.2f} L/s
- 最小流量：{flow_data.get('min_flow', 0):.2f} L/s
- 日总流量：{flow_data.get('total_volume', 0):.2f} m³
"""

        # 格式化在线监测指标统计（来自数采仪）
        online_text = ""
        if online_data and isinstance(online_data, dict):
            pols = online_data.get("pollutants") or []
            items = []
            # 限制最多展示 20 个指标，避免 prompt 过长
            for p in pols[:20]:
                try:
                    name = p.get("pollutant_name") or p.get("pollutant_code")
                    unit = p.get("unit") or ""
                    avg = p.get("avg")
                    mn = p.get("min")
                    mx = p.get("max")
                    cnt = p.get("count")
                    dev_cnt = p.get("device_count")
                    if avg is None or mn is None or mx is None:
                        continue
                    items.append(
                        f"- {name}：均值 {avg:.3f}{unit}，范围 {mn:.3f}-{mx:.3f}{unit}，点数 {cnt}，设备数 {dev_cnt}"
                    )
                except Exception:
                    continue
            if items:
                online_text = f"""
## 在线监测数据统计（数采仪）
- 数据来源：环境监测数采仪（在线实测数据）
- 说明：以下为企业范围内按指标汇总统计（不同设备/点位数据已合并）
{chr(10).join(items)}
"""

        # 格式化污染负荷数据
        load_text = ""
        if pollutant_loads:
            load_items = []
            for code, load_info in pollutant_loads.get("pollutant_loads", {}).items():
                load_items.append(
                    f"- {load_info['name']}：日排放量 {load_info['daily_load_kg']:.4f} kg/d，"
                    f"月排放量 {load_info['monthly_load_kg']:.2f} kg/月"
                )
            load_text = f"""
## 污染负荷计算
- 计算公式：污染负荷(kg/d) = 浓度(mg/L) × 日流量(m³/d) ÷ 1000
- 流量数据来源：数采仪实测
- 浓度数据来源：第三方检测报告
{chr(10).join(load_items) if load_items else "暂无污染负荷数据"}
"""

        # 数据来源说明
        data_source_note = """
## 数据来源说明
⚠️ 重要提示：
- **流量数据**：来自环境监测数采仪，为设备实测数据，可信度高
- **在线监测数据**：来自数采仪/在线监测系统（若有），可用于过程波动/异常识别
- **浓度数据**：来自第三方检测机构报告，数据准确性以原始报告为准
- 污染负荷计算整合了两个数据源，请注意数据来源差异
""" if (flow_data or online_text) else ""

        prompt = f"""你是一位专业的环保运维专家。请根据以下企业自行检测数据，生成一份专业的运维分析报告。

## 企业信息
- 企业名称：{org_name}
- 报告周期：{period}

## 检测数据统计（第三方检测报告）
{chr(10).join(summary_text) if summary_text else "暂无数据"}
{flow_text}{online_text}{load_text}{data_source_note}
## 趋势分析
{chr(10).join(trend_text) if trend_text else "数据点不足，无法分析趋势"}

## 要求
请生成包含以下内容的运维报告：
1. **数据概述**：简要总结本周期的监测数据情况
2. **合规性分析**：分析各项指标是否达标，是否存在风险
3. **趋势分析**：分析各污染物的变化趋势
{"4. **污染负荷分析**：分析污染物排放总量及其环境影响" if pollutant_loads else ""}
{"5" if pollutant_loads else "4"}. **运维建议**：提供3-5条具体可行的运维建议

注意：
- 语言专业但易懂
- 建议要具体可操作
- 如果数据不足，请如实说明
- 注意区分数据来源（数采仪在线数据 vs 第三方检测报告），在分析中体现数据可信度差异，并可做交叉验证

请直接输出报告内容，不要包含额外的解释。"""

        return prompt

    def _parse_ai_response(self, response: str, period: str) -> dict[str, Any]:
        """解析AI响应"""
        # 提取建议（简单的分割方式）
        recommendations = []
        lines = response.split("\n")
        in_recommendations = False

        for line in lines:
            line = line.strip()
            if "运维建议" in line or "建议" in line:
                in_recommendations = True
                continue
            if in_recommendations and line:
                # 提取编号列表项
                if re.match(r"^[\d\.\-\*]+", line):
                    # 清理编号
                    clean_line = re.sub(r"^[\d\.\-\*\s]+", "", line).strip()
                    if clean_line:
                        recommendations.append(clean_line)

        return {
            "period": period,
            "generated_at": datetime.utcnow(),
            "summary": response,
            "recommendations": recommendations[:5],  # 最多5条建议
            "data_source_note": "本报告基于企业提交的第三方检测机构报告数据生成，数据准确性以原始检测报告为准。",
        }


def get_self_inspection_service(db_session: AsyncSession) -> SelfInspectionService:
    """获取自检档案服务实例"""
    return SelfInspectionService(db_session)


def get_baidu_ocr_client() -> BaiduOCRClient | None:
    """
    获取配置好的百度OCR客户端实例

    Returns:
        BaiduOCRClient实例，如果未配置则返回None
    """
    if not settings.baidu_ocr_api_key or not settings.baidu_ocr_secret_key:
        logger.warning("Baidu OCR credentials not configured in environment variables")
        return None

    return BaiduOCRClient()


def get_ai_data_extractor() -> AIDataExtractor | None:
    """
    获取配置好的AI数据提取器实例

    Returns:
        AIDataExtractor实例，如果未配置则返回None
    """
    from app.services.llm import get_spark_client

    spark_client = get_spark_client()
    if not spark_client:
        logger.warning("Spark client not configured, AI extraction unavailable")
        return None

    return AIDataExtractor(spark_client)
