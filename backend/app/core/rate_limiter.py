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
from slowapi import Limiter
from slowapi.util import get_remote_address


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
