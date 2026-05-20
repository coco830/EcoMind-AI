"""PostgreSQL database connection and session management."""

from collections.abc import AsyncGenerator
from uuid import UUID as PyUUID

import structlog
from sqlalchemy import String, TypeDecorator, inspect, text
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

logger = structlog.get_logger(__name__)


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


def _is_production() -> bool:
    return _fresh_settings.environment == "production"


def _load_model_metadata() -> None:
    """Import ORM models so Base.metadata is complete before schema checks."""
    import app.models  # noqa: F401


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


async def check_schema() -> None:
    """Validate that the database schema already exists.

    Production startup must not mutate schema. Deployments should run Alembic
    migrations before the service starts.
    """
    _load_model_metadata()
    required_tables = set(Base.metadata.tables)
    if not required_tables:
        raise RuntimeError("No SQLAlchemy table metadata is registered")

    async with engine.connect() as conn:
        existing_tables = await conn.run_sync(
            lambda sync_conn: set(inspect(sync_conn).get_table_names())
        )

    missing_tables = sorted(required_tables - existing_tables)
    if missing_tables:
        logger.error("Database schema check failed", missing_tables=missing_tables)
        raise RuntimeError(
            "Database schema is not initialized; run Alembic migrations before "
            "starting production. Missing tables: {}".format(", ".join(missing_tables))
        )

    logger.info("Database schema check passed", table_count=len(required_tables))


async def init_db(*, mutate_schema: bool | None = None) -> None:
    """Initialize or validate database schema.

    Development/test defaults to local schema initialization. Production defaults
    to a read-only schema check and refuses create_all/ensure_* mutations.
    """
    if mutate_schema is None:
        mutate_schema = not _is_production()

    if not mutate_schema:
        await check_schema()
        return

    if _is_production():
        raise RuntimeError(
            "Production schema mutations must use Alembic or explicit migration tooling; "
            "init_db() will not run create_all/ensure_* in production."
        )

    _load_model_metadata()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await _ensure_alarm_sms_columns()
    await _ensure_regulator_scope_columns()
    await _ensure_video_columns()
    await _ensure_cascade_delete_fks()
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
                except SQLAlchemyError as exc:
                    _handle_schema_adjustment_error(
                        exc,
                        table="alarms",
                        column="sms_sent_count",
                    )
            if "last_sms_time" not in columns:
                try:
                    await conn.execute(
                        text(
                            "ALTER TABLE alarms ADD COLUMN "
                            "last_sms_time DATETIME NULL"
                        )
                    )
                except SQLAlchemyError as exc:
                    _handle_schema_adjustment_error(
                        exc,
                        table="alarms",
                        column="last_sms_time",
                    )
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


async def _ensure_video_columns() -> None:
    """Ensure video channel ledger columns exist for existing deployments."""
    sqlite_video_channel_columns = {
        "lifecycle_status": "lifecycle_status VARCHAR(32) NOT NULL DEFAULT 'pending_survey'",
        "network_provider": "network_provider VARCHAR(64) NULL",
        "fixed_ip": "fixed_ip VARCHAR(64) NULL",
        "install_location": "install_location TEXT NULL",
        "surveyor_name": "surveyor_name VARCHAR(64) NULL",
        "installer_name": "installer_name VARCHAR(64) NULL",
        "accepted_by": "accepted_by VARCHAR(64) NULL",
        "accepted_at": "accepted_at DATETIME NULL",
        "acceptance_notes": "acceptance_notes TEXT NULL",
    }
    generic_video_channel_columns = {
        "lifecycle_status": "VARCHAR(32) NOT NULL DEFAULT 'pending_survey'",
        "network_provider": "VARCHAR(64) NULL",
        "fixed_ip": "VARCHAR(64) NULL",
        "install_location": "TEXT NULL",
        "surveyor_name": "VARCHAR(64) NULL",
        "installer_name": "VARCHAR(64) NULL",
        "accepted_by": "VARCHAR(64) NULL",
        "accepted_at": "DATETIME NULL" if is_mysql else "TIMESTAMP WITH TIME ZONE NULL",
        "acceptance_notes": "TEXT NULL",
    }

    async with engine.begin() as conn:
        if is_sqlite:
            await _ensure_sqlite_table_columns(conn, "video_channels", sqlite_video_channel_columns)
        elif is_mysql:
            await _ensure_mysql_table_columns(conn, "video_channels", generic_video_channel_columns)
        else:
            await _ensure_postgres_table_columns(conn, "video_channels", generic_video_channel_columns)


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
    api_client_columns = {
        "access_scope": "access_scope VARCHAR(32) NOT NULL DEFAULT 'single_org'",
    }

    await _ensure_sqlite_table_columns(conn, "organizations", org_columns)
    await _ensure_sqlite_table_columns(conn, "invitation_codes", invitation_columns)
    await _ensure_sqlite_table_columns(conn, "devices", device_columns)
    await _ensure_sqlite_table_columns(conn, "monitoring_daily_stats", daily_stats_columns)
    await _ensure_sqlite_table_columns(conn, "api_clients", api_client_columns)


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
    api_client_columns = {
        "access_scope": "VARCHAR(32) NOT NULL DEFAULT 'single_org'",
    }

    await _ensure_mysql_table_columns(conn, "organizations", org_columns)
    await _ensure_mysql_table_columns(conn, "invitation_codes", invitation_columns)
    await _ensure_mysql_table_columns(conn, "devices", device_columns)
    await _ensure_mysql_table_columns(conn, "monitoring_daily_stats", daily_stats_columns)
    await _ensure_mysql_table_columns(conn, "api_clients", api_client_columns)


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
        except SQLAlchemyError as exc:
            _handle_schema_adjustment_error(exc, table=table, column=name)


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
    api_client_columns = {
        "access_scope": "VARCHAR(32) NOT NULL DEFAULT 'single_org'",
    }

    await _ensure_postgres_table_columns(conn, "organizations", org_columns)
    await _ensure_postgres_table_columns(conn, "invitation_codes", invitation_columns)
    await _ensure_postgres_table_columns(conn, "devices", device_columns)
    await _ensure_postgres_table_columns(conn, "monitoring_daily_stats", daily_stats_columns)
    await _ensure_postgres_table_columns(conn, "api_clients", api_client_columns)


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


async def _ensure_cascade_delete_fks() -> None:
    """Ensure device foreign keys have ON DELETE CASCADE (MySQL only)."""
    if not is_mysql:
        return

    async with engine.begin() as conn:
        # Check current FK definitions for alarms and daily_reports
        for table_name in ("alarms", "daily_reports"):
            result = await conn.execute(
                text(
                    "SELECT CONSTRAINT_NAME, DELETE_RULE "
                    "FROM information_schema.REFERENTIAL_CONSTRAINTS "
                    "WHERE CONSTRAINT_SCHEMA = DATABASE() "
                    "AND TABLE_NAME = :table "
                    "AND REFERENCED_TABLE_NAME = 'devices'"
                ),
                {"table": table_name},
            )
            row = result.first()
            if row is None:
                continue
            constraint_name, delete_rule = row
            if delete_rule == "CASCADE":
                continue
            # Drop old FK and recreate with CASCADE
            try:
                await conn.execute(
                    text(f"ALTER TABLE `{table_name}` DROP FOREIGN KEY `{constraint_name}`")
                )
                await conn.execute(
                    text(
                        f"ALTER TABLE `{table_name}` ADD CONSTRAINT `{constraint_name}` "
                        f"FOREIGN KEY (`device_id`) REFERENCES `devices` (`id`) ON DELETE CASCADE"
                    )
                )
            except SQLAlchemyError as exc:
                _handle_schema_adjustment_error(
                    exc,
                    table=table_name,
                    operation="ensure ON DELETE CASCADE",
                )


def _handle_schema_adjustment_error(
    exc: SQLAlchemyError,
    *,
    table: str,
    column: str | None = None,
    operation: str = "add column",
) -> None:
    if _is_production():
        logger.error(
            "Schema adjustment failed in production",
            table=table,
            column=column,
            operation=operation,
            error=str(exc),
        )
        raise exc

    logger.warning(
        "Schema adjustment skipped after database error",
        table=table,
        column=column,
        operation=operation,
        error=str(exc),
    )
