import os
from typing import List
from pydantic import BaseSettings

class Settings(BaseSettings):
    """Application settings"""
    app_name: str = "AI Presentation Generator"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # CORS Settings
    allowed_origins: List[str] = ["*"]
    
    # File Upload Settings
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_file_types: List[str] = [".pdf", ".docx", ".txt", ".md"]
    
    # AI Service Configuration (replace with your actual AI service)
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    
    # Presentation Templates
    template_dir: str = "app/static/templates"
    
    # Database (if needed later)
    database_url: str = ""
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Create settings instance
settings = Settings()