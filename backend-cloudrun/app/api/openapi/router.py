"""OpenAPI router aggregating all agent tool endpoints.

These endpoints are designed for external AI agent integrations (e.g. OpenClaw).
Authentication is via API Key (X-API-Key header) instead of JWT.
"""

from fastapi import APIRouter

from app.api.openapi import device_tools, data_tools, alarm_tools, ai_tools

openapi_router = APIRouter()

openapi_router.include_router(device_tools.router, tags=["openapi-devices"])
openapi_router.include_router(data_tools.router, tags=["openapi-data"])
openapi_router.include_router(alarm_tools.router, tags=["openapi-alarms"])
openapi_router.include_router(ai_tools.router, tags=["openapi-ai"])
