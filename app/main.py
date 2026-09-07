from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.session import init_db
from app.api.v1.router import api_router
from app.services.history_store import history_store

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes database extensions and tables on application startup."""
    await init_db()
    await history_store.init_db()
    yield


app = FastAPI(
    title="Movie Crossword Game API",
    description="Adaptive, AI-powered movie crossword puzzle generator & telemetry service.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configure CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from pathlib import Path
from fastapi.responses import FileResponse

# Mount API v1 Routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["Health Check"])
async def root():
    """Health check endpoint."""
    return {
        "status": "online",
        "service": "Movie Crossword Game Backend",
        "version": "1.0.0",
        "docs_url": "/docs",
        "test_ui": "/test"
    }


@app.get("/test", tags=["Test UI"])
async def test_ui():
    """Serves the pure testing web client for crossword gameplay."""
    test_html = Path(__file__).parent / "static" / "test_game.html"
    return FileResponse(test_html)

