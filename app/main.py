"""
AI Presentation Generator — Gamma-style backend with SSE streaming.

Architecture:
  • POST /api/v1/generate        → start a generation (returns stream URL)
  • GET  /api/v1/generate/{id}/stream  → SSE event stream
  • GET  /api/v1/generate/{id}   → poll generation status
  • DELETE /api/v1/generate/{id} → cancel/remove a generation
  • GET  /api/v1/health          → health check
  • GET  /api/v1/status          → operational status
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging

from app.api.endpoints.presentations import router as presentations_router
from app.api.endpoints.health import router as health_router
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifecycle (startup / shutdown) ─────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager."""
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"LLM provider: {settings.llm_provider} / {settings.llm_model}")
    logger.info(f"Redis: {'enabled' if settings.use_redis else 'disabled (in-memory)'}")
    logger.info(f"Image generation: {settings.image_provider}")
    yield
    logger.info("Shutting down…")


# ── App factory ────────────────────────────────

app = FastAPI(
    title="AI Presentation Generator",
    description=(
        "Gamma-style presentation generation backend with SSE streaming, "
        "parallel slide generation, dynamic layouts, and image generation."
    ),
    version=settings.app_version,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(presentations_router, prefix="/api/v1", tags=["presentations"])
app.include_router(health_router, prefix="/api/v1", tags=["health"])


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "redoc": "/redoc",
        "endpoints": {
            "generate": "POST /api/v1/generate",
            "stream": "GET  /api/v1/generate/{id}/stream",
            "status": "GET  /api/v1/generate/{id}",
            "health": "GET  /api/v1/health",
        },
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
    )
