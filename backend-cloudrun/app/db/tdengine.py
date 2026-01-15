"""TDengine time-series database connection and operations - Legacy compatibility wrapper.

支持宽表模式：所有污染物指标作为列存储。
"""

from datetime import datetime
from typing import Any

# Import the secure client implementation
from app.db.tdengine_client import get_tdengine_client as get_secure_client

# Re-export for backward compatibility
def get_tdengine_client():
    """Get or create global TDengine client (uses secure implementation)."""
    return get_secure_client()


# Legacy TDengineClient class that delegates to secure implementation
class TDengineClient:
    """
    Legacy TDengine client for backward compatibility.
    Delegates all operations to the secure implementation.
    """

    def __init__(self) -> None:
        """Initialize TDengine client using secure implementation."""
        self._client = get_secure_client()

    async def execute(self, sql: str) -> None:
        """Execute SQL statement (deprecated - use secure methods instead)."""
        await self._client.execute(sql)

    async def query(self, sql: str) -> list[dict[str, Any]]:
        """Execute query (deprecated - use secure methods instead)."""
        return await self._client.execute(sql)

    async def init_database(self) -> None:
        """Initialize TDengine database and tables."""
        await self._client.init_database()

    async def insert_monitoring_data(
        self,
        device_id: str,
        pollutant_code: str,
        org_id: str,
        ts: datetime,
        value: float,
        flag: str = "N",
        status: int = 0,
    ) -> None:
        """Insert a single monitoring data point (now SQL injection safe)."""
        await self._client.insert_monitoring_data(
            device_id=device_id,
            pollutant_code=pollutant_code,
            org_id=org_id,
            timestamp=ts,
            value=value,
            flag=flag,
            status=status
        )

    async def query_monitoring_data(
        self,
        device_id: str | None = None,
        pollutant_code: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Query monitoring data with optional filters (now SQL injection safe)."""
        return await self._client.query_monitoring_data(
            device_id=device_id,
            pollutant_code=pollutant_code,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )

    async def insert_wide_monitoring_data(
        self,
        device_id: str,
        org_id: str,
        timestamp: datetime,
        pollutants: dict[str, dict[str, Any]],
        data_type: str = "realtime",
    ) -> bool:
        """Insert wide-table monitoring data with all pollutants in one record."""
        return await self._client.insert_wide_monitoring_data(
            device_id=device_id,
            org_id=org_id,
            timestamp=timestamp,
            pollutants=pollutants,
            data_type=data_type
        )

    async def query_wide_monitoring_data(
        self,
        device_id: str,
        pollutant_codes: list[str] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Query wide-table monitoring data."""
        return await self._client.query_wide_monitoring_data(
            device_id=device_id,
            pollutant_codes=pollutant_codes,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )

    async def alter_table_add_columns(self, new_pollutant_codes: list[str]) -> bool:
        """Dynamically add new pollutant columns to the super table."""
        return await self._client.alter_table_add_columns(new_pollutant_codes)

    async def close(self) -> None:
        """Close TDengine connection."""
        await self._client.close()


# For compatibility with existing imports
from contextlib import asynccontextmanager

@asynccontextmanager
async def tdengine_lifespan():
    """Context manager for TDengine lifecycle."""
    client = get_tdengine_client()
    try:
        await client.init_database()
        yield client
    finally:
        await client.close()