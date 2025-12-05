"""API v1 router aggregating all endpoints."""

from fastapi import APIRouter

from app.api.v1 import auth, devices, data, alarms, dashboard, ai, organizations, reports, invitations

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(devices.router, prefix="/devices", tags=["devices"])
api_router.include_router(data.router, prefix="/data", tags=["data"])
api_router.include_router(alarms.router, prefix="/alarms", tags=["alarms"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(invitations.router, prefix="/invitations", tags=["invitations"])
