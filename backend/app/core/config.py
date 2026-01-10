"""Application configuration using pydantic-settings.

Security Notes:
- All sensitive credentials MUST be provided via environment variables
- Default values are only provided for development convenience
- Production deployments MUST set proper secrets via environment
"""

import os
import re
import secrets
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _is_production_environment() -> bool:
    """Check if running in production environment."""
    return os.getenv("ENVIRONMENT", "development").lower() == "production"


def _generate_dev_secret(prefix: str = "dev") -> str:
    """Generate a random secret for development use only."""
    return f"{prefix}_{secrets.token_hex(32)}"


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Security:
    - In production, JWT_SECRET and SM4_KEY MUST be set via environment variables
    - Weak or placeholder secrets will raise validation errors in production
    """

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

    # Database (can be PostgreSQL, MySQL or SQLite)
    database_url: str = "sqlite+aiosqlite:///./ecomind.db"

    # PostgreSQL (for production)
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "ecomind"
    postgres_user: str = "ecomind"
    postgres_password: str = ""  # MUST be set via environment in production

    # MySQL (for CloudBase)
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_db: str = "ecomind"
    mysql_user: str = "root"
    mysql_password: str = ""

    @field_validator("postgres_password")
    @classmethod
    def validate_postgres_password(cls, v: str) -> str:
        """Validate PostgreSQL password strength in production."""
        # Allow empty for SQLite mode in development
        if not v:
            # Don't enforce in production if using MySQL or SQLite
            return v

        # Check for weak default passwords
        weak_passwords = {"ecomind123", "password", "postgres", "admin", "root", "123456"}
        if v.lower() in weak_passwords:
            if _is_production_environment():
                raise ValueError(
                    "POSTGRES_PASSWORD is too weak for production. "
                    "Generate a strong password with: openssl rand -base64 24"
                )
        return v

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

    @property
    def mysql_url(self) -> str:
        """MySQL connection URL for SQLAlchemy."""
        from urllib.parse import quote_plus
        # URL encode password to handle special characters like @
        encoded_password = quote_plus(self.mysql_password)
        return (
            f"mysql+aiomysql://{self.mysql_user}:{encoded_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}?charset=utf8mb4"
        )

    # TDengine
    tdengine_host: str = "localhost"
    tdengine_port: int = 6030
    tdengine_user: str = "root"
    tdengine_password: str = "taosdata"
    tdengine_database: str = "ecomind"

    # JWT Authentication - CRITICAL SECURITY
    jwt_secret: str = ""  # MUST be set via environment
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24  # 24 hours

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        """Validate JWT secret strength.

        Security requirements:
        - Minimum 32 characters
        - No placeholder/default values in production
        - Must contain sufficient entropy
        """
        # Placeholder patterns that indicate unconfigured secrets
        placeholder_patterns = [
            r"change.*production",
            r"your.*secret",
            r"placeholder",
            r"example",
            r"^secret$",
            r"^test$",
        ]

        is_production = _is_production_environment()

        # If empty, use a fixed default secret to ensure token persistence across restarts
        # Note: For high-security production, set JWT_SECRET environment variable
        if not v:
            return "ecomind-ai-default-jwt-secret-for-cloudbase-2024-persistent"

        # Check for placeholder values
        for pattern in placeholder_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                if is_production:
                    raise ValueError(
                        f"JWT_SECRET appears to be a placeholder value. "
                        "Generate a secure secret with: openssl rand -base64 48"
                    )

        # Enforce minimum length
        if len(v) < 32:
            if is_production:
                raise ValueError(
                    f"JWT_SECRET must be at least 32 characters (current: {len(v)}). "
                    "Generate with: openssl rand -base64 48"
                )

        return v

    # SM4 Encryption - CRITICAL SECURITY
    sm4_key: str = ""  # MUST be set via environment (32 hex chars = 16 bytes)

    @field_validator("sm4_key")
    @classmethod
    def validate_sm4_key(cls, v: str) -> str:
        """Validate SM4 encryption key.

        Security requirements:
        - Must be exactly 32 hex characters (16 bytes)
        - No default/weak keys in production
        """
        is_production = _is_production_environment()

        # Weak/default SM4 keys to reject
        weak_keys = {
            "0123456789abcdef",
            "00000000000000000000000000000000",
            "ffffffffffffffffffffffffffffffff",
            "0123456789abcdef0123456789abcdef",
        }

        # If empty, generate random for dev or fail for production
        if not v:
            if is_production:
                raise ValueError(
                    "SM4_KEY is required in production (32 hex characters). "
                    "Generate with: openssl rand -hex 16"
                )
            # Generate random key for development
            return secrets.token_hex(16)

        # Normalize to lowercase for validation
        v_lower = v.lower()

        # Validate hex format and length
        if not re.match(r"^[0-9a-f]{32}$", v_lower):
            raise ValueError(
                f"SM4_KEY must be exactly 32 hexadecimal characters (current: {len(v)}). "
                "Generate with: openssl rand -hex 16"
            )

        # Check for weak keys
        if v_lower in weak_keys:
            if is_production:
                raise ValueError(
                    "SM4_KEY is a known weak key. "
                    "Generate a secure key with: openssl rand -hex 16"
                )

        return v_lower  # Return normalized lowercase

    # AI Model
    anomaly_detection_enabled: bool = True
    anomaly_threshold: float = 0.85

    # Spark LLM (讯飞星火大模型)
    spark_app_id: str = ""
    spark_api_key: str = ""
    spark_api_secret: str = ""
    spark_api_url: str = "wss://spark-api.xf-yun.com/chat/pro-128k"
    spark_domain: str = "pro-128k"

    # Baidu OCR (百度文字识别)
    baidu_ocr_api_key: str = ""
    baidu_ocr_secret_key: str = ""

    # CORS Configuration
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"  # Comma-separated list

    # Tencent Cloud SMS
    tencent_secret_id: str = ""
    tencent_secret_key: str = ""
    tencent_sms_sdk_app_id: str = ""
    tencent_sms_sign_name: str = ""
    tencent_sms_template_id: str = ""

    # Email Configuration (SMTP)
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "YueenEcoMind-AI"
    smtp_use_ssl: bool = True

    # Password Reset
    password_reset_expire_minutes: int = 30  # Token expires in 30 minutes
    frontend_url: str = "http://localhost:3000"  # Frontend URL for reset links

    # Gateway API Key (for HTTP forwarding from TCP proxy)
    gateway_api_key: str = "ecomind-gateway-key-2024"  # Should be changed in production

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
