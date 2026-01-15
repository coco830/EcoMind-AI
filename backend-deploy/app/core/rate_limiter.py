"""Rate limiting configuration for API endpoints.

Security:
- Prevents brute force attacks on login endpoints
- Prevents abuse of registration endpoints
- Protects against DDoS by limiting request rates

Testing:
- Rate limiting uses unique keys in test environment to avoid hitting limits
- Set TESTING=true or ENVIRONMENT=test to enable test mode
"""

import os
from datetime import datetime, timedelta
from collections import defaultdict
from threading import Lock
from uuid import UUID

import structlog
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = structlog.get_logger(__name__)


def _is_testing() -> bool:
    """Check if running in test environment.

    Checks for common test environment indicators:
    - TESTING=true environment variable
    - ENVIRONMENT=test environment variable
    - PYTEST_CURRENT_TEST set by pytest
    """
    return (
        os.getenv("TESTING", "").lower() == "true" or
        os.getenv("ENVIRONMENT", "").lower() == "test" or
        os.getenv("PYTEST_CURRENT_TEST") is not None
    )


def _get_rate_limit_key(request) -> str:
    """Get rate limit key.

    In test environment, returns a unique key per request to avoid rate limit issues.
    In production, uses the client's IP address.
    """
    if _is_testing():
        # Return unique key per request to effectively disable rate limiting in tests
        return f"test_{id(request)}"
    return get_remote_address(request)


# Initialize rate limiter with custom key function
# In test environment, each request gets a unique key to avoid rate limit issues
# This is checked at request time, not at module import time
limiter = Limiter(key_func=_get_rate_limit_key)


def get_limiter() -> Limiter:
    """Get the global rate limiter instance."""
    return limiter


# ==================== AI Report Rate Limiter ====================


class AIReportRateLimiter:
    """
    AI 报告生成限流器。

    实现两层限流：
    1. 设备冷却时间：同一设备在冷却时间内不能重复生成报告
    2. 用户每日配额：每个用户每天最多生成指定次数的报告

    使用内存存储，重启后会清空。如果需要持久化，可以替换为 Redis。
    """

    def __init__(
        self,
        device_cooldown_minutes: int = 10,
        user_daily_quota: int = 5,
    ):
        """
        初始化限流器。

        Args:
            device_cooldown_minutes: 设备冷却时间（分钟），默认10分钟
            user_daily_quota: 用户每日配额，默认5次
        """
        self.device_cooldown_minutes = device_cooldown_minutes
        self.user_daily_quota = user_daily_quota

        # 存储：设备ID -> 最后生成时间
        self._device_last_report: dict[str, datetime] = {}

        # 存储：用户ID + 日期 -> 调用次数
        self._user_daily_count: dict[str, int] = defaultdict(int)

        # 线程安全锁
        self._lock = Lock()

    def _get_user_date_key(self, user_id: UUID) -> str:
        """获取用户每日计数的 key。"""
        today = datetime.now().strftime("%Y-%m-%d")
        return f"{user_id}:{today}"

    def _cleanup_old_entries(self) -> None:
        """清理过期的条目（可在定时任务中调用）。"""
        now = datetime.now()
        cooldown = timedelta(minutes=self.device_cooldown_minutes)

        # 清理过期的设备冷却记录
        expired_devices = [
            device_id
            for device_id, last_time in self._device_last_report.items()
            if now - last_time > cooldown
        ]
        for device_id in expired_devices:
            del self._device_last_report[device_id]

        # 清理过期的用户配额记录（非今日的）
        today = datetime.now().strftime("%Y-%m-%d")
        expired_users = [
            key
            for key in self._user_daily_count.keys()
            if not key.endswith(today)
        ]
        for key in expired_users:
            del self._user_daily_count[key]

    def check_device_cooldown(self, device_id: str) -> tuple[bool, int | None]:
        """
        检查设备是否在冷却期。

        Args:
            device_id: 设备ID

        Returns:
            (是否允许, 剩余冷却秒数)
            如果允许，返回 (True, None)
            如果不允许，返回 (False, 剩余秒数)
        """
        if _is_testing():
            return True, None

        with self._lock:
            last_time = self._device_last_report.get(device_id)
            if last_time is None:
                return True, None

            elapsed = datetime.now() - last_time
            cooldown = timedelta(minutes=self.device_cooldown_minutes)

            if elapsed >= cooldown:
                return True, None

            remaining = (cooldown - elapsed).total_seconds()
            return False, int(remaining)

    def check_user_quota(self, user_id: UUID) -> tuple[bool, int, int]:
        """
        检查用户每日配额。

        Args:
            user_id: 用户ID

        Returns:
            (是否允许, 已使用次数, 总配额)
        """
        if _is_testing():
            return True, 0, self.user_daily_quota

        with self._lock:
            key = self._get_user_date_key(user_id)
            used = self._user_daily_count[key]

            if used >= self.user_daily_quota:
                return False, used, self.user_daily_quota

            return True, used, self.user_daily_quota

    def record_report_generation(self, device_id: str, user_id: UUID) -> None:
        """
        记录一次报告生成（在生成成功后调用）。

        Args:
            device_id: 设备ID
            user_id: 用户ID
        """
        if _is_testing():
            return

        with self._lock:
            # 记录设备冷却时间
            self._device_last_report[device_id] = datetime.now()

            # 增加用户每日计数
            key = self._get_user_date_key(user_id)
            self._user_daily_count[key] += 1

            logger.info(
                "AI report rate limit recorded",
                device_id=device_id,
                user_id=str(user_id),
                user_daily_count=self._user_daily_count[key],
            )

    def get_status(self, device_id: str, user_id: UUID) -> dict:
        """
        获取当前限流状态。

        Args:
            device_id: 设备ID
            user_id: 用户ID

        Returns:
            包含限流状态的字典
        """
        device_allowed, remaining_cooldown = self.check_device_cooldown(device_id)
        user_allowed, used_quota, total_quota = self.check_user_quota(user_id)

        return {
            "device_id": device_id,
            "device_cooldown": {
                "allowed": device_allowed,
                "remaining_seconds": remaining_cooldown,
                "cooldown_minutes": self.device_cooldown_minutes,
            },
            "user_quota": {
                "allowed": user_allowed,
                "used": used_quota,
                "total": total_quota,
                "remaining": total_quota - used_quota,
            },
            "can_generate": device_allowed and user_allowed,
        }


# 全局限流器实例
ai_report_limiter = AIReportRateLimiter(
    device_cooldown_minutes=10,  # 设备冷却10分钟
    user_daily_quota=5,          # 用户每日5次
)


def get_ai_report_limiter() -> AIReportRateLimiter:
    """获取 AI 报告限流器实例。"""
    return ai_report_limiter
