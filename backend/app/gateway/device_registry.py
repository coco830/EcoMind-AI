"""Device Registry for TCP Gateway authentication.

This module provides device authentication and caching for the TCP gateway.
It maps device MN numbers to organization IDs to support multi-tenant data isolation.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.models.device import Device

logger = structlog.get_logger()
settings = get_settings()


@dataclass
class DeviceInfo:
    """Cached device information."""
    device_id: UUID
    mn: str
    org_id: UUID
    name: str
    cached_at: datetime


class DeviceRegistry:
    """Device registry with caching for TCP gateway authentication.

    This class provides:
    - Device lookup by MN number
    - In-memory caching to reduce database queries
    - Automatic cache expiration
    - Support for device registration status
    """

    def __init__(self, cache_ttl_seconds: int = 300):
        """Initialize device registry.

        Args:
            cache_ttl_seconds: Cache time-to-live in seconds (default: 5 minutes)
        """
        self._cache: dict[str, DeviceInfo] = {}
        self._cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self._engine = None
        self._session_factory = None
        self._lock = asyncio.Lock()
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Ensure database connection is initialized."""
        if self._initialized:
            return

        async with self._lock:
            if self._initialized:
                return

            self._engine = create_async_engine(
                settings.database_url,
                echo=False,
                pool_pre_ping=True,
            )
            self._session_factory = sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            self._initialized = True
            logger.info("DeviceRegistry initialized")

    async def close(self) -> None:
        """Close database connections."""
        if self._engine:
            await self._engine.dispose()
            self._initialized = False
            logger.info("DeviceRegistry closed")

    def _is_cache_valid(self, cached_info: DeviceInfo) -> bool:
        """Check if cached device info is still valid."""
        return datetime.utcnow() - cached_info.cached_at < self._cache_ttl

    async def get_device_by_mn(self, mn: str) -> Optional[DeviceInfo]:
        """Get device information by MN number.

        Args:
            mn: Device MN number

        Returns:
            DeviceInfo if device is registered, None otherwise
        """
        # Check cache first
        if mn in self._cache:
            cached = self._cache[mn]
            if self._is_cache_valid(cached):
                logger.debug("Device cache hit", mn=mn)
                return cached
            else:
                # Cache expired, remove it
                del self._cache[mn]

        # Query database
        await self._ensure_initialized()

        try:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(Device).where(Device.mn == mn)
                )
                device = result.scalar_one_or_none()

                if device is None:
                    logger.warning("Unregistered device attempted connection", mn=mn)
                    return None

                # Cache the result
                device_info = DeviceInfo(
                    device_id=device.id,
                    mn=device.mn,
                    org_id=device.org_id,
                    name=device.name,
                    cached_at=datetime.utcnow(),
                )
                self._cache[mn] = device_info

                logger.info(
                    "Device authenticated",
                    mn=mn,
                    device_id=str(device.id),
                    org_id=str(device.org_id),
                )
                return device_info

        except Exception as e:
            logger.error("Failed to query device", mn=mn, error=str(e))
            return None

    async def invalidate_cache(self, mn: str) -> None:
        """Invalidate cache for a specific device.

        Call this when device configuration changes.
        """
        if mn in self._cache:
            del self._cache[mn]
            logger.debug("Device cache invalidated", mn=mn)

    def clear_cache(self) -> None:
        """Clear all cached device information."""
        self._cache.clear()
        logger.info("Device cache cleared")

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        valid_count = sum(
            1 for info in self._cache.values()
            if self._is_cache_valid(info)
        )
        return {
            "total_cached": len(self._cache),
            "valid_cached": valid_count,
            "expired_cached": len(self._cache) - valid_count,
        }


# Global singleton instance
_device_registry: Optional[DeviceRegistry] = None


def get_device_registry() -> DeviceRegistry:
    """Get the global device registry instance."""
    global _device_registry
    if _device_registry is None:
        _device_registry = DeviceRegistry()
    return _device_registry


async def close_device_registry() -> None:
    """Close the global device registry."""
    global _device_registry
    if _device_registry is not None:
        await _device_registry.close()
        _device_registry = None
