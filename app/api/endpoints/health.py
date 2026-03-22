from fastapi import APIRouter
from datetime import datetime, timezone

from app.core.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": settings.app_name,
        "version": settings.app_version,
    }


@router.get("/status")
async def get_status():
    """Detailed operational status."""
    return {
        "status": "operational",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {
            "llm_provider": settings.llm_provider,
            "llm_model": settings.llm_model,
            "redis": "enabled" if settings.use_redis else "in-memory",
            "image_provider": settings.image_provider,
        },
        "endpoints": {
            "generate": "POST /api/v1/generate",
            "stream": "GET /api/v1/generate/{id}/stream",
            "poll": "GET /api/v1/generate/{id}",
            "delete": "DELETE /api/v1/generate/{id}",
            "list": "GET /api/v1/generations",
        },
        "features": {
            "sse_streaming": True,
            "parallel_slide_gen": True,
            "image_generation": settings.image_provider != "none",
            "dynamic_layouts": True,
            "token_budgeting": True,
            "retry_mechanism": True,
        },
    }
