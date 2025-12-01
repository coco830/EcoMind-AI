"""EcoMind-AI Backend Application Entry Point."""

import asyncio
from contextlib import asynccontextmanager

import structlog
import uvloop
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import get_settings
from app.core.rate_limiter import limiter
from app.db.postgres import init_db, close_db
from app.db.tdengine_client import get_tdengine_client
from app.api.v1.router import api_router
from app.gateway.server import get_tcp_server

settings = get_settings()
logger = structlog.get_logger()

# Use uvloop for better async performance
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting EcoMind-AI Backend", version=settings.app_version)

    # Initialize PostgreSQL
    await init_db()
    logger.info("PostgreSQL initialized")

    # Initialize TDengine
    tdengine = get_tdengine_client()
    await tdengine.connect()
    await tdengine.init_database()
    logger.info("TDengine initialized")

    # Start TCP Gateway Server
    tcp_server = get_tcp_server(host="0.0.0.0", port=9880)
    # Create task but don't block (server will run in background)
    gateway_task = asyncio.create_task(tcp_server.start())
    app.state.gateway_task = gateway_task  # Store reference
    app.state.tcp_server = tcp_server
    logger.info("TCP Gateway Server started on port 9880")

    yield

    # Shutdown
    logger.info("Shutting down EcoMind-AI Backend")

    # Stop TCP Gateway Server
    if hasattr(app.state, 'tcp_server'):
        await app.state.tcp_server.stop()
    if hasattr(app.state, 'gateway_task'):
        app.state.gateway_task.cancel()
        try:
            await app.state.gateway_task
        except asyncio.CancelledError:
            pass

    # Close TDengine
    await tdengine.close()

    # Close PostgreSQL
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
