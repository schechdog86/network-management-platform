"""
Configuration settings for the Network Management Platform
"""

import os
from typing import List, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    APP_NAME: str = "Network Management Platform"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-super-secret-key-change-in-production")
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql+asyncpg://netmgmt:secure_password_123@localhost:5432/network_mgmt"
    )
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # Ray Cluster
    RAY_ADDRESS: Optional[str] = os.getenv("RAY_ADDRESS", None)
    RAY_DASHBOARD_PORT: int = int(os.getenv("RAY_DASHBOARD_PORT", "8265"))
    
    # Security
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ALGORITHM: str = "HS256"
    
    # CORS
    ALLOWED_HOSTS: List[str] = ["*"]  # Configure properly for production
    
    # GPU Configuration
    CUDA_VISIBLE_DEVICES: str = os.getenv("CUDA_VISIBLE_DEVICES", "0,1,2,3")
    GPU_MEMORY_FRACTION: float = 0.8
    
    # AI Configuration
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    AI_MODEL: str = "gpt-3.5-turbo"
    
    # Network Scanning
    DEFAULT_SCAN_TIMEOUT: int = 30
    MAX_CONCURRENT_SCANS: int = 100
    
    # Backup Configuration
    BACKUP_STORAGE_PATH: str = os.getenv("BACKUP_STORAGE_PATH", "/app/backups")
    BACKUP_RETENTION_DAYS: int = 90
    
    # Monitoring
    METRICS_ENABLED: bool = True
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    @field_validator("ALLOWED_HOSTS", mode='before')
    @classmethod
    def assemble_cors_origins(cls, v):
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    model_config = {
        "case_sensitive": True
    }


# Global settings instance
settings = Settings()

# Ray cluster configuration
RAY_CLUSTER_CONFIG = {
    "num_cpus": 16,
    "num_gpus": 4,
    "resources": {
        "NetworkScanner": 4,
        "BackupProcessor": 4, 
        "AIInference": 4
    },
    "runtime_env": {
        "pip": [
            "cupy-cuda12x",
            "torch",
            "transformers",
            "accelerate"
        ]
    }
}