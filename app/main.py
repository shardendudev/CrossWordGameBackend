import time
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.db.session import init_db
from app.api.v1.router import api_router

APP_VERSION = "1.0.0"

setup_logging()
logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes database extensions, tables, and logging on application startup."""
    logger.info("Initializing application startup sequence...")
    logger.info("DB host resolved as: %r", settings.POSTGRES_SERVER)
    try:
        await init_db()
        logger.info("PostgreSQL database & extensions initialized successfully.")
    except Exception as e:
        logger.error(f"Database initialization failed during startup: {e}")
    yield
    logger.info("Application shutdown completed.")



app = FastAPI(
    title="Movie Crossword Game API",
    description="Adaptive, AI-powered movie crossword puzzle generator & telemetry service.",
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()] if settings.ALLOWED_ORIGINS else ["*"]

# Configure CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Logs incoming HTTP requests, response status codes, and latency."""
    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000
    logger.info(
        f"{request.method} {request.url.path} -> status={response.status_code} ({duration_ms:.1f}ms)"
    )
    return response


# Mount API v1 Routes
app.include_router(api_router, prefix="/api/v1")



@app.get("/", tags=["Health Check"])
async def root():
    """Health check endpoint."""
    return {
        "status": "online",
        "service": "Movie Crossword Game Backend",
        "version": APP_VERSION,
        "docs_url": "/docs",
        "test_ui": "/test"
    }


@app.get("/test", tags=["Test UI"])
async def test_ui():
    """Serves the pure testing web client for crossword gameplay."""
    test_html = Path(__file__).parent / "static" / "test_game.html"
    return FileResponse(test_html)
