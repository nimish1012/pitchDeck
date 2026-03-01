from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.api.endpoints.presentations import router as presentations_router
from app.api.endpoints.health import router as health_router
from app.core.config import settings

# Create FastAPI application
app = FastAPI(
    title="AI Presentation Generator",
    description="Generate presentations from documents, prompts, or outlines",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(presentations_router, prefix="/api/v1", tags=["presentations"])
app.include_router(health_router, prefix="/api/v1", tags=["health"])

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "AI Presentation Generator API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc"
    }

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )