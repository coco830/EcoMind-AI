"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "EcoMind-AI"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: Literal["development", "staging", "production"] = "development"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    tcp_gateway_port: int = 9999

    # Database (can be PostgreSQL or SQLite)
    database_url: str = "sqlite+aiosqlite:///./ecomind.db"

    # PostgreSQL (for production)
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "ecomind"
    postgres_user: str = "ecomind"
    postgres_password: str = "ecomind123"

    @property
    def postgres_url(self) -> str:
        """PostgreSQL connection URL for SQLAlchemy."""
        # Use database_url if set, otherwise build PostgreSQL URL
        if self.database_url and not self.database_url.startswith("postgresql"):
            return self.database_url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # TDengine
    tdengine_host: str = "localhost"
    tdengine_port: int = 6030
    tdengine_user: str = "root"
    tdengine_password: str = "taosdata"
    tdengine_database: str = "ecomind"

    # JWT Authentication
    jwt_secret: str = "your-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24  # 24 hours

    # SM4 Encryption
    sm4_key: str = "0123456789abcdef"  # 16 bytes hex key

    # AI Model
    anomaly_detection_enabled: bool = True
    anomaly_threshold: float = 0.85

    # Spark LLM (讯飞星火大模型)
    spark_app_id: str = ""
    spark_api_key: str = ""
    spark_api_secret: str = ""
    spark_api_url: str = "wss://spark-api.xf-yun.com/chat/pro-128k"
    spark_domain: str = "pro-128k"

    # CORS Configuration
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"  # Comma-separated list

    # Tencent Cloud SMS
    tencent_secret_id: str = ""
    tencent_secret_key: str = ""
    tencent_sms_sdk_app_id: str = ""
    tencent_sms_sign_name: str = ""
    tencent_sms_template_id: str = ""

    @property
    def cors_origins(self) -> list[str]:
        """Parse CORS allowed origins from environment variable."""
        if self.allowed_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
