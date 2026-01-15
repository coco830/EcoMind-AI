"""PostgreSQL database connection and session management."""

from collections.abc import AsyncGenerator
from uuid import UUID as PyUUID

from sqlalchemy import String, TypeDecorator, text
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class GUID(TypeDecorator):
    """Platform-independent GUID type.

    Uses PostgreSQL's UUID type when available, otherwise uses String(36).
    """

    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PostgreSQLUUID(as_uuid=True))
        else:
            return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return value
        else:
            return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, PyUUID):
                value = PyUUID(value)
            return value

settings = get_settings()

# Configure engine based on database type
# Priority: mysql_url (if mysql_password set) > DATABASE_URL env var > postgres_url > sqlite
# Re-fetch settings to ensure environment variables are loaded
from app.core.config import Settings
_fresh_settings = Settings()  # Don't use cache to ensure env vars are read

if _fresh_settings.mysql_password:
    # MySQL configured via separate env vars (CloudBase)
    db_url = _fresh_settings.mysql_url
elif _fresh_settings.database_url.startswith("mysql"):
    # Already a MySQL URL from DATABASE_URL
    db_url = _fresh_settings.database_url
elif _fresh_settings.postgres_password:
    # PostgreSQL configured
    db_url = _fresh_settings.postgres_url
else:
    # Default to sqlite
    db_url = _fresh_settings.database_url

is_sqlite = db_url.startswith("sqlite")
is_mysql = db_url.startswith("mysql")

if is_sqlite:
    # SQLite doesn't support pool parameters
    engine = create_async_engine(
        db_url,
        echo=settings.debug,
    )
elif is_mysql:
    # MySQL with connection pooling
    engine = create_async_engine(
        db_url,
        echo=settings.debug,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600,  # Recycle connections after 1 hour
    )
else:
    # PostgreSQL with connection pooling
    engine = create_async_engine(
        db_url,
        echo=settings.debug,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy ORM models."""

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await _ensure_alarm_sms_columns()
    await _ensure_regulator_scope_columns()
    # Create default organization if not exists
    await _create_default_organization()


async def _create_default_organization() -> None:
    """Create default organization for admin users."""
    from uuid import UUID
    from sqlalchemy import select
    from app.models.organization import Organization

    DEFAULT_ORG_ID = UUID("00000000-0000-0000-0000-000000000001")

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Organization).where(Organization.id == DEFAULT_ORG_ID)
        )
        if not result.scalar_one_or_none():
            org = Organization(
                id=DEFAULT_ORG_ID,
                name="Default Organization",
                code="DEFAULT",
                address="Default Address",
            )
            session.add(org)
            await session.commit()


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()


async def _ensure_alarm_sms_columns() -> None:
    """Ensure new SMS-related columns exist for alarms table."""
    async with engine.begin() as conn:
        if is_sqlite:
            result = await conn.exec_driver_sql("PRAGMA table_info('alarms')")
            columns = {row[1] for row in result}
            if "sms_sent_count" not in columns:
                await conn.exec_driver_sql(
                    "ALTER TABLE alarms ADD COLUMN sms_sent_count INTEGER NOT NULL DEFAULT 0"
                )
            if "last_sms_time" not in columns:
                await conn.exec_driver_sql(
                    "ALTER TABLE alarms ADD COLUMN last_sms_time DATETIME NULL"
                )
        elif is_mysql:
            result = await conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='alarms' AND table_schema=DATABASE()"
                )
            )
            columns = {row[0] for row in result}
            if "sms_sent_count" not in columns:
                try:
                    await conn.execute(
                        text(
                            "ALTER TABLE alarms ADD COLUMN "
                            "sms_sent_count INTEGER NOT NULL DEFAULT 0"
                        )
                    )
                except Exception:
                    pass  # Column might already exist
            if "last_sms_time" not in columns:
                try:
                    await conn.execute(
                        text(
                            "ALTER TABLE alarms ADD COLUMN "
                            "last_sms_time DATETIME NULL"
                        )
                    )
                except Exception:
                    pass
        else:
            result = await conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='alarms'"
                )
            )
            columns = {row[0] for row in result}
            if "sms_sent_count" not in columns:
                await conn.execute(
                    text(
                        "ALTER TABLE alarms ADD COLUMN IF NOT EXISTS "
                        "sms_sent_count INTEGER NOT NULL DEFAULT 0"
                    )
                )
            if "last_sms_time" not in columns:
                await conn.execute(
                    text(
                        "ALTER TABLE alarms ADD COLUMN IF NOT EXISTS "
                        "last_sms_time TIMESTAMP WITH TIME ZONE"
                    )
                )


async def _ensure_regulator_scope_columns() -> None:
    """Ensure regulator-related columns exist for organizations/invitations/devices."""
    async with engine.begin() as conn:
        if is_sqlite:
            await _ensure_sqlite_columns(conn)
        elif is_mysql:
            await _ensure_mysql_columns(conn)
        else:
            await _ensure_postgres_columns(conn)


async def _ensure_sqlite_columns(conn) -> None:
    org_columns = {
        "org_type": "org_type VARCHAR(32) NOT NULL DEFAULT 'enterprise'",
        "region_code": "region_code VARCHAR(64) NULL",
        "region_name": "region_name VARCHAR(128) NULL",
        "park_code": "park_code VARCHAR(64) NULL",
        "park_name": "park_name VARCHAR(128) NULL",
        "industry_type": "industry_type VARCHAR(64) NULL",
        "jurisdiction_level": "jurisdiction_level VARCHAR(32) NULL",
        "jurisdiction_codes": "jurisdiction_codes TEXT NULL",
        "status": "status VARCHAR(20) NOT NULL DEFAULT 'active'",
    }
    invitation_columns = {
        "org_type": "org_type VARCHAR(32) NOT NULL DEFAULT 'enterprise'",
        "region_code": "region_code VARCHAR(64) NULL",
        "region_name": "region_name VARCHAR(128) NULL",
        "park_code": "park_code VARCHAR(64) NULL",
        "park_name": "park_name VARCHAR(128) NULL",
        "industry_type": "industry_type VARCHAR(64) NULL",
        "jurisdiction_level": "jurisdiction_level VARCHAR(32) NULL",
        "jurisdiction_codes": "jurisdiction_codes TEXT NULL",
    }
    device_columns = {
        "industry_type": "industry_type VARCHAR(64) NULL",
    }
    daily_stats_columns = {
        "data_count": "data_count INTEGER NOT NULL DEFAULT 0",
        "exceed_count": "exceed_count INTEGER NOT NULL DEFAULT 0",
        "invalid_count": "invalid_count INTEGER NOT NULL DEFAULT 0",
        "avg_value": "avg_value DOUBLE NULL",
    }

    await _ensure_sqlite_table_columns(conn, "organizations", org_columns)
    await _ensure_sqlite_table_columns(conn, "invitation_codes", invitation_columns)
    await _ensure_sqlite_table_columns(conn, "devices", device_columns)
    await _ensure_sqlite_table_columns(conn, "monitoring_daily_stats", daily_stats_columns)


async def _ensure_sqlite_table_columns(conn, table: str, columns: dict[str, str]) -> None:
    result = await conn.exec_driver_sql(f"PRAGMA table_info('{table}')")
    existing = {row[1] for row in result}
    for name, ddl in columns.items():
        if name in existing:
            continue
        await conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {ddl}")


async def _ensure_mysql_columns(conn) -> None:
    org_columns = {
        "org_type": "VARCHAR(32) NOT NULL DEFAULT 'enterprise'",
        "region_code": "VARCHAR(64) NULL",
        "region_name": "VARCHAR(128) NULL",
        "park_code": "VARCHAR(64) NULL",
        "park_name": "VARCHAR(128) NULL",
        "industry_type": "VARCHAR(64) NULL",
        "jurisdiction_level": "VARCHAR(32) NULL",
        "jurisdiction_codes": "TEXT NULL",
        "status": "VARCHAR(20) NOT NULL DEFAULT 'active'",
    }
    invitation_columns = {
        "org_type": "VARCHAR(32) NOT NULL DEFAULT 'enterprise'",
        "region_code": "VARCHAR(64) NULL",
        "region_name": "VARCHAR(128) NULL",
        "park_code": "VARCHAR(64) NULL",
        "park_name": "VARCHAR(128) NULL",
        "industry_type": "VARCHAR(64) NULL",
        "jurisdiction_level": "VARCHAR(32) NULL",
        "jurisdiction_codes": "TEXT NULL",
    }
    device_columns = {
        "industry_type": "VARCHAR(64) NULL",
    }
    daily_stats_columns = {
        "data_count": "INT NOT NULL DEFAULT 0",
        "exceed_count": "INT NOT NULL DEFAULT 0",
        "invalid_count": "INT NOT NULL DEFAULT 0",
        "avg_value": "DOUBLE NULL",
    }

    await _ensure_mysql_table_columns(conn, "organizations", org_columns)
    await _ensure_mysql_table_columns(conn, "invitation_codes", invitation_columns)
    await _ensure_mysql_table_columns(conn, "devices", device_columns)
    await _ensure_mysql_table_columns(conn, "monitoring_daily_stats", daily_stats_columns)


async def _ensure_mysql_table_columns(conn, table: str, columns: dict[str, str]) -> None:
    result = await conn.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name=:table AND table_schema=DATABASE()"
        ),
        {"table": table},
    )
    existing = {row[0] for row in result}
    for name, ddl in columns.items():
        if name in existing:
            continue
        try:
            await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN `{name}` {ddl}"))
        except Exception:
            pass


async def _ensure_postgres_columns(conn) -> None:
    org_columns = {
        "org_type": "VARCHAR(32) NOT NULL DEFAULT 'enterprise'",
        "region_code": "VARCHAR(64) NULL",
        "region_name": "VARCHAR(128) NULL",
        "park_code": "VARCHAR(64) NULL",
        "park_name": "VARCHAR(128) NULL",
        "industry_type": "VARCHAR(64) NULL",
        "jurisdiction_level": "VARCHAR(32) NULL",
        "jurisdiction_codes": "TEXT NULL",
        "status": "VARCHAR(20) NOT NULL DEFAULT 'active'",
    }
    invitation_columns = {
        "org_type": "VARCHAR(32) NOT NULL DEFAULT 'enterprise'",
        "region_code": "VARCHAR(64) NULL",
        "region_name": "VARCHAR(128) NULL",
        "park_code": "VARCHAR(64) NULL",
        "park_name": "VARCHAR(128) NULL",
        "industry_type": "VARCHAR(64) NULL",
        "jurisdiction_level": "VARCHAR(32) NULL",
        "jurisdiction_codes": "TEXT NULL",
    }
    device_columns = {
        "industry_type": "VARCHAR(64) NULL",
    }
    daily_stats_columns = {
        "data_count": "INTEGER NOT NULL DEFAULT 0",
        "exceed_count": "INTEGER NOT NULL DEFAULT 0",
        "invalid_count": "INTEGER NOT NULL DEFAULT 0",
        "avg_value": "DOUBLE PRECISION NULL",
    }

    await _ensure_postgres_table_columns(conn, "organizations", org_columns)
    await _ensure_postgres_table_columns(conn, "invitation_codes", invitation_columns)
    await _ensure_postgres_table_columns(conn, "devices", device_columns)
    await _ensure_postgres_table_columns(conn, "monitoring_daily_stats", daily_stats_columns)


async def _ensure_postgres_table_columns(conn, table: str, columns: dict[str, str]) -> None:
    result = await conn.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name=:table"
        ),
        {"table": table},
    )
    existing = {row[0] for row in result}
    for name, ddl in columns.items():
        if name in existing:
            continue
        await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {name} {ddl}"))
