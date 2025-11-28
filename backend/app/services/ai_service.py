"""
AI 诊断服务

整合 SparkClient、数据分析服务和 Prompt 模板，
提供智能运维诊断、告警分析、交互式问答等功能。
"""

from datetime import date
from typing import Any, AsyncGenerator

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.prompts import (
    DOMAIN_KNOWLEDGE,
    build_alarm_analysis_prompt,
    build_chat_system_prompt,
    build_expert_diagnosis_prompt,
    get_domain_from_device_type,
    get_domain_from_pollutant_code,
    get_domain_knowledge,
    get_pollutant_info,
)
from app.services.data_analysis_service import DataAnalysisService
from app.services.llm.spark_client import SparkClient

logger = structlog.get_logger(__name__)


class AIService:
    """
    AI 诊断服务

    提供：
    - 智能运维诊断日报生成
    - 实时告警分析
    - 交互式环保问答
    """

    def __init__(
        self,
        spark_client: SparkClient,
        db_session: AsyncSession | None = None,
    ):
        """
        初始化 AI 服务。

        Args:
            spark_client: 星火大模型客户端
            db_session: 数据库会话（用于数据分析和设备查询）
        """
        self.spark = spark_client
        self.db_session = db_session
        self.data_analysis = DataAnalysisService(db_session)

    async def generate_daily_diagnosis(
        self,
        device_id: str,
        device_name: str,
        device_type: str,
        target_date: date,
        pollutant_code: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        生成智能运维诊断日报（流式输出）。

        Args:
            device_id: 设备 ID
            device_name: 设备名称
            device_type: 设备类型 (water/air/noise/soil)
            target_date: 目标日期
            pollutant_code: 指定污染物代码（可选，不指定则分析主要污染物）

        Yields:
            生成的诊断报告文本片段
        """
        logger.info(
            "Generating daily diagnosis",
            device_id=device_id,
            device_type=device_type,
            date=target_date.isoformat(),
        )

        # 步骤1：获取数据统计特征
        stats = await self.data_analysis.analyze_device_daily_stats(
            device_id=device_id,
            target_date=target_date,
            pollutant_code=pollutant_code,
        )

        if not stats.get("pollutants"):
            yield f"## 诊断报告\n\n该设备在 {target_date} 无监测数据，无法生成诊断报告。"
            return

        # 步骤2：选择主要污染物进行诊断
        pollutant_stats = stats["pollutants"][0]  # 取第一个污染物
        p_code = pollutant_stats["pollutant_code"]

        # 获取污染物信息
        domain = get_domain_from_device_type(device_type)
        pollutant_info = get_pollutant_info(domain, p_code)
        p_name = pollutant_info.get("name", p_code)
        unit = pollutant_info.get("unit", "")

        # 判断合规状态
        threshold = pollutant_stats.get("threshold_value")
        over_limit_count = pollutant_stats.get("over_limit_count", 0)

        if over_limit_count > 0:
            compliance_status = f"存在 {over_limit_count} 次超标"
        elif threshold and pollutant_stats["avg_val"] > threshold * 0.9:
            compliance_status = "临近阈值，需关注"
        else:
            compliance_status = "正常达标"

        # 步骤3：构建 Prompt
        prompt = build_expert_diagnosis_prompt(
            device_type=device_type,
            device_name=device_name,
            pollutant_code=p_code,
            pollutant_name=p_name,
            report_date=target_date.isoformat(),
            avg_val=pollutant_stats["avg_val"],
            max_val=pollutant_stats["max_val"],
            min_val=pollutant_stats["min_val"],
            peak_time=pollutant_stats.get("peak_time", "未知"),
            alarm_count=over_limit_count,
            compliance_status=compliance_status,
            trend_desc=pollutant_stats.get("trend_description", "数据正常"),
            unit=unit,
        )

        logger.debug("Built diagnosis prompt", prompt_length=len(prompt))

        # 步骤4：调用 AI 生成诊断报告
        messages = [{"role": "user", "content": prompt}]

        async for chunk in self.spark.chat_stream(messages):
            yield chunk

    async def analyze_alarm(
        self,
        device_name: str,
        device_type: str,
        pollutant_code: str,
        pollutant_name: str,
        alarm_time: str,
        current_value: float,
        threshold_value: float,
        unit: str = "",
    ) -> AsyncGenerator[str, None]:
        """
        分析告警原因（流式输出）。

        Args:
            device_name: 设备名称
            device_type: 设备类型
            pollutant_code: 污染物代码
            pollutant_name: 污染物名称
            alarm_time: 告警时间
            current_value: 当前值
            threshold_value: 阈值
            unit: 单位

        Yields:
            告警分析文本片段
        """
        logger.info(
            "Analyzing alarm",
            device_name=device_name,
            pollutant_code=pollutant_code,
            current_value=current_value,
        )

        prompt = build_alarm_analysis_prompt(
            device_name=device_name,
            device_type=device_type,
            pollutant_code=pollutant_code,
            pollutant_name=pollutant_name,
            alarm_time=alarm_time,
            current_value=current_value,
            threshold_value=threshold_value,
            unit=unit,
        )

        messages = [{"role": "user", "content": prompt}]

        async for chunk in self.spark.chat_stream(messages):
            yield chunk

    async def chat(
        self,
        user_message: str,
        conversation_history: list[dict] | None = None,
        device_type: str | None = None,
        pollutant_code: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        环保智能问答（流式输出）。

        Args:
            user_message: 用户消息
            conversation_history: 对话历史（可选）
            device_type: 设备类型（用于确定领域知识）
            pollutant_code: 污染物代码（用于推断领域）

        Yields:
            AI 回复文本片段
        """
        # 构建系统提示词
        system_prompt = build_chat_system_prompt(device_type, pollutant_code)

        # 构建消息列表
        messages = conversation_history.copy() if conversation_history else []
        messages.append({"role": "user", "content": user_message})

        async for chunk in self.spark.chat_stream(messages, system_prompt=system_prompt):
            yield chunk

    async def generate_daily_diagnosis_sync(
        self,
        device_id: str,
        device_name: str,
        device_type: str,
        target_date: date,
        pollutant_code: str | None = None,
    ) -> str:
        """
        生成智能运维诊断日报（非流式，返回完整文本）。

        Args:
            同 generate_daily_diagnosis

        Returns:
            完整的诊断报告文本
        """
        chunks = []
        async for chunk in self.generate_daily_diagnosis(
            device_id=device_id,
            device_name=device_name,
            device_type=device_type,
            target_date=target_date,
            pollutant_code=pollutant_code,
        ):
            chunks.append(chunk)
        return "".join(chunks)

    @staticmethod
    def get_available_domains() -> dict[str, dict[str, str]]:
        """
        获取所有可用的监测领域信息。

        Returns:
            领域知识库字典
        """
        return {
            domain: {
                "name": info["name"],
                "standards": info["standards"],
                "terms": info["terms"],
            }
            for domain, info in DOMAIN_KNOWLEDGE.items()
        }

    @staticmethod
    def infer_domain(
        device_type: str | None = None,
        pollutant_code: str | None = None,
    ) -> str:
        """
        推断监测领域。

        Args:
            device_type: 设备类型
            pollutant_code: 污染物代码

        Returns:
            领域标识 (water/air/noise/soil)
        """
        if device_type:
            return get_domain_from_device_type(device_type)
        if pollutant_code:
            return get_domain_from_pollutant_code(pollutant_code)
        return "water"


# =============================================================================
# 便捷工厂函数
# =============================================================================


def create_ai_service(
    app_id: str,
    api_secret: str,
    api_key: str,
    db_session: AsyncSession | None = None,
    spark_url: str = "wss://spark-api.xf-yun.com/chat/pro-128k",
    domain: str = "pro-128k",
) -> AIService:
    """
    创建 AI 服务实例。

    Args:
        app_id: 讯飞 APPID
        api_secret: API Secret
        api_key: API Key
        db_session: 数据库会话
        spark_url: WebSocket 地址
        domain: 模型域

    Returns:
        AIService 实例
    """
    spark_client = SparkClient(
        app_id=app_id,
        api_secret=api_secret,
        api_key=api_key,
        spark_url=spark_url,
        domain=domain,
    )
    return AIService(spark_client=spark_client, db_session=db_session)
