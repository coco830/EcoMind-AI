"""LLM services module."""

from .spark_client import SparkClient
from app.core.config import get_settings


def get_spark_client() -> SparkClient | None:
    """
    获取配置好的讯飞星火客户端实例

    Returns:
        SparkClient实例，如果未配置则返回None
    """
    settings = get_settings()

    if not settings.spark_app_id or not settings.spark_api_key or not settings.spark_api_secret:
        return None

    return SparkClient(
        app_id=settings.spark_app_id,
        api_secret=settings.spark_api_secret,
        api_key=settings.spark_api_key,
        api_password=settings.spark_api_password,
        spark_url=settings.spark_api_url,
        domain=settings.spark_domain,
    )


__all__ = ["SparkClient", "get_spark_client"]
