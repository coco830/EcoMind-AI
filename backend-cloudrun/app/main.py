"""EcoMind-AI Backend Application Entry Point."""

import asyncio
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import get_settings
from app.core.rate_limiter import limiter
from app.db.postgres import init_db, close_db
from app.api.v1.router import api_router
from app.services.scheduler import setup_scheduler, start_scheduler, stop_scheduler
from app.services.default_users import ensure_default_users

settings = get_settings()
logger = structlog.get_logger()

# Use uvloop for better async performance (optional, graceful fallback)
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    logger.info("Using uvloop for async performance")
except ImportError:
    logger.info("uvloop not available, using default event loop")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting EcoMind-AI Backend", version=settings.app_version)

    # Initialize PostgreSQL/MySQL
    await init_db()
    logger.info("Database initialized (MySQL)")

    # Ensure default platform users exist (idempotent, can be disabled via env)
    if settings.bootstrap_default_users:
        try:
            from app.db.postgres import AsyncSessionLocal

            async with AsyncSessionLocal() as db:
                result = await ensure_default_users(
                    db,
                    reset_passwords=settings.bootstrap_default_users_reset_passwords,
                )
                await db.commit()
            logger.info("Default users ensured", **result)
        except Exception as e:
            # Never block service startup due to bootstrap failures
            logger.warning("Default user bootstrap failed", error=str(e))

    # Sync device health once at startup (offline alarms, etc.)
    try:
        from app.db.postgres import AsyncSessionLocal
        from app.services.device_health import sync_device_health

        async with AsyncSessionLocal() as db:
            result = await sync_device_health(db)
            await db.commit()
        logger.info("Device health synced on startup", **result)
    except Exception as e:
        logger.warning("Device health startup sync failed", error=str(e))

    # Note: TDengine removed - using MySQL for all data storage
    # Note: TCP Gateway removed - using HTTP Gateway via tcp_proxy_server.py

    # Start scheduler for daily tasks
    setup_scheduler(app)
    start_scheduler()
    logger.info("Scheduler started for daily report generation (02:00 Asia/Shanghai)")

    yield

    # Shutdown
    logger.info("Shutting down EcoMind-AI Backend")

    # Stop scheduler
    stop_scheduler()

    # Close PostgreSQL/MySQL
    await close_db()

    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="智慧环保SaaS平台 - 环境监测数据采集与分析系统",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware - now configured from environment
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # Configured from environment
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=3600,  # Cache preflight requests for 1 hour
)

# Include API routes
app.include_router(api_router, prefix="/api/v1")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Log validation errors with full details."""
    logger.warning(
        "Request validation error",
        path=request.url.path,
        method=request.method,
        errors=exc.errors(),
        body=exc.body if hasattr(exc, 'body') else None
    )
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()}
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Return JSON error for unexpected exceptions to aid debugging."""
    logger.exception(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.app_version,
        "environment": settings.environment,
    }


@app.get("/")
async def root() -> dict:
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
    }


@app.post("/init-superadmin")
async def init_superadmin(secret: str, reset_passwords: bool = False) -> dict:
    """Initialize default platform users (one-time setup).

    Historical route name kept for compatibility.
    Protected by INIT_SECRET environment variable.
    """
    import os
    # Security check - must provide correct secret from environment
    expected_secret = os.getenv("INIT_SECRET", "")
    if not expected_secret or secret != expected_secret:
        return {"success": False, "message": "Invalid secret"}

    from app.db.postgres import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        result = await ensure_default_users(db, reset_passwords=reset_passwords)
        await db.commit()

        return {"success": True, "message": "Default users ensured", **result}
