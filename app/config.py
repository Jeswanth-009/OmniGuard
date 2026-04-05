"""
OmniGuard Configuration Module
Pydantic-based environment configuration with validation
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    app_name: str = Field(default="OmniGuard", description="Application name")
    app_version: str = Field(default="1.0.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode")
    environment: str = Field(default="production", description="Environment name")
    
    # Redis Configuration
    redis_host: str = Field(default="redis", description="Redis host")
    redis_port: int = Field(default=6379, ge=1, le=65535, description="Redis port")
    redis_db: int = Field(default=0, ge=0, le=15, description="Redis database number")
    redis_password: Optional[str] = Field(default=None, description="Redis password")
    redis_timeout: int = Field(default=5, ge=1, le=30, description="Redis connection timeout")
    
    # Cache Configuration
    cache_ttl: int = Field(default=60, ge=1, le=3600, description="Cache TTL in seconds")
    cache_prefix: str = Field(default="omniguard:", description="Cache key prefix")
    
    # Upstream API Configuration
    upstream_url: str = Field(
        default="https://jsonplaceholder.typicode.com",
        description="Upstream API base URL"
    )
    upstream_timeout: int = Field(default=10, ge=1, le=60, description="Upstream request timeout")
    
    # Server Configuration
    server_host: str = Field(default="0.0.0.0", description="Server host")
    server_port: int = Field(default=8000, ge=1, le=65535, description="Server port")
    
    # Metrics
    metrics_enabled: bool = Field(default=True, description="Enable Prometheus metrics")
    
    # Testing
    testing: bool = Field(default=False, description="Test mode flag - skips Redis init")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
