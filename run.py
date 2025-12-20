#!/usr/bin/env python3
"""
Alternative entry point for running the presentation generator application
"""

import uvicorn
from app.main import app

if __name__ == "__main__":
    print("🚀 Starting AI Presentation Generator...")
    print("📖 API Documentation: http://localhost:8000/docs")
    print("🔍 ReDoc Documentation: http://localhost:8000/redoc")
    print("❤️  Health Check: http://localhost:8000/api/v1/health")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )