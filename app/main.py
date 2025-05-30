from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import auth, users, oauth, two_factor_auth, devices
from app.core.config import settings
from app.core import rate_limit
from app.core.logging import app_logger as logger, setup_uvicorn_logging
from app.db.database import db_manager
from app.tasks import cleanup
from app.middleware.logging import setup_logging_middleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.PROJECT_VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}, Mode: {settings.APP_MODE}")
    
    await db_manager.initialize()
    await db_manager.create_tables()
    
    # Set AsyncSessionLocal for backward compatibility
    from app.db import database
    database.AsyncSessionLocal = db_manager.async_session_maker
    
    # Start background tasks
    cleanup.start_background_tasks()
    await rate_limit.rate_limit_store.start_cleanup()
    
    logger.info("Application startup complete")
    yield
    
    # Shutdown
    logger.info("Application shutdown started")
    await rate_limit.rate_limit_store.stop_cleanup()
    await db_manager.close()
    logger.info("Application shutdown complete")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    docs_url="/docs" if settings.ENVIRONMENT == "development" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT == "development" else None,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting middleware
if settings.RATE_LIMIT_ENABLED:
    app.add_middleware(
        BaseHTTPMiddleware,
        dispatch=rate_limit.create_rate_limit_middleware(
            max_requests=settings.RATE_LIMIT_REQUESTS,
            window_seconds=settings.RATE_LIMIT_WINDOW,
            paths=["/api/"],
            exclude_paths=["/api/v1/auth/login", "/api/v1/auth/register"]
        )
    )

# Setup logging
setup_uvicorn_logging()
setup_logging_middleware(app)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(oauth.router, prefix="/api/v1/oauth", tags=["oauth"])
app.include_router(two_factor_auth.router, prefix="/api/v1/2fa", tags=["2fa"])
app.include_router(devices.router, prefix="/api/v1/devices", tags=["devices"])


@app.get("/")
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/login.html")


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/api/v1/demo-mode")
async def get_demo_mode():
    return {
        "is_demo": settings.IS_DEMO_MODE,
        "demo_credentials": {
            "email": "demo@example.com",
            "password": "demo123"
        } if settings.IS_DEMO_MODE else None
    }
