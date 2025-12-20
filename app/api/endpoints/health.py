from fastapi import APIRouter
from datetime import datetime

router = APIRouter()

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "AI Presentation Generator API",
        "version": "1.0.0"
    }

@router.get("/status")
async def get_status():
    """Detailed status endpoint"""
    return {
        "status": "operational",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": {
            "document_presentation": "available",
            "prompt_presentation": "available", 
            "outline_presentation": "available"
        },
        "features": {
            "file_upload": "available",
            "ai_generation": "available",
            "multiple_formats": "available"
        }
    }