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
db_url = settings.postgres_url
is_sqlite = db_url.startswith("sqlite")

if is_sqlite:
    # SQLite doesn't support pool parameters
    engine = create_async_engine(
        db_url,
        echo=settings.debug,
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
