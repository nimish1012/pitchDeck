import os
from typing import List

try:
    from pydantic_settings import BaseSettings
except ImportError:
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
    
    # AI Service Configuration
    openai_api_key: str = ""
    google_api_key: str = ""
    vllm_api_base: str = "http://localhost:8000/v1"
    
    # LLM Pipeline Configuration
    llm_provider: str = "openai"  # Options: openai, google, vllm
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 2000
    
    # Presentation Templates
    template_dir: str = "app/static/templates"
    
    # Database (if needed later)
    database_url: str = ""
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Create settings instance
settings = Settings()