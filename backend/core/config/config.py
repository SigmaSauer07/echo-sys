"""Configuration management for Alsania MCP"""
import os
from typing import Optional

class Config:
    """Application configuration with environment variable support"""
    
    # API Configuration
    API_TOKEN: str = os.getenv("API_TOKEN", "alsania-dev")
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8050"))
    RELOAD: bool = os.getenv("RELOAD", "true").lower() == "true"
    
    # Database Configuration
    MCP_URL: str = os.getenv("MCP_URL", "http://localhost:8050")
    POSTGRES_URL: str = os.getenv("POSTGRES_URL", "postgresql://postgres:mem0pass@localhost:5432/mem0")
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    
    # Embedding Configuration
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://host.docker.internal:11435")
    OLLAMA_IMAGE: str = os.getenv("OLLAMA_IMAGE", "mistralai/stablelm-tuned-alpha-7b")
    OPENROUTER_API_KEY: Optional[str] = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "mistral:7b-instruct-q4")
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Security Configuration
    ENABLE_CHAOS_MODE: bool = os.getenv("ENABLE_CHAOS_MODE", "true").lower() == "true"
    ENABLE_SENTINEL: bool = os.getenv("ENABLE_SENTINEL", "true").lower() == "true"
    
    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration"""
        if not cls.OPENROUTER_API_KEY:
            print("⚠️  Warning: OPENROUTER_API_KEY not set. Embedding functionality may fail.")
            return False
        return True
    
    @classmethod
    def print_config(cls):
        """Print current configuration (excluding sensitive data)"""
        print("🔧 Configuration:")
        print(f"  Host: {cls.HOST}:{cls.PORT}")
        print(f"  Postgres: {cls.POSTGRES_URL.split('@')[1] if '@' in cls.POSTGRES_URL else cls.POSTGRES_URL}")
        print(f"  Qdrant: {cls.QDRANT_URL}")
        print(f"  Model: {cls.OPENROUTER_MODEL}")
        print(f"  Log Level: {cls.LOG_LEVEL}")
        print(f"  Chaos Mode: {cls.ENABLE_CHAOS_MODE}")
        print(f"  Sentinel: {cls.ENABLE_SENTINEL}")

config = Config()
