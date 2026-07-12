import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Application configuration schema representing verified env bindings."""

    # Environment Context
    ENV: str = "development"
    DEBUG: bool = True

    # Backend Ports & Gateway Configurations
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Adaptive Memory Engine (AME)"

    # Database Configuration settings
    # Default to a local postgres server name for local installations
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ame"
    
    # Synchronous DB URL needed by Alembic migrations configuration
    SYNC_DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/ame"

    # Cryptography / Cryptographic keys
    # Cryptographic secret key used to sign Auth payloads (must be overridden in production)
    JWT_SECRET_KEY: str = "secret-tokens-change-on-production-environments-310aefb"
    ACCESSO_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 Days session

    # Third Party Provider Keys
    OPENAI_API_KEY: Optional[str] = None
    LLM_MODEL: str = "gpt-4o"
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Adaptive Memory Engine configuration parameters
    W_SEMANTIC: float = 0.40
    W_IMPORTANCE: float = 0.15
    W_RECENCY: float = 0.15
    W_FREQUENCY: float = 0.10
    W_DECAY: float = 0.10
    W_CONFIDENCE: float = 0.10
    RECENCY_HALF_LIFE_HOURS: float = 168.0  # 7 days
    FREQUENCY_THRESHOLD: int = 50
    DECAY_RATE: float = 0.004  # standard exponential decay constant

    # Hybrid Memory System (Milestone 7)
    DEFAULT_MEMORY_SYSTEM: str = "Semantic"
    WORKING_MEMORY_TTL_HOURS: float = 24.0

    # Settings config path mapping to .env file if available
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Globally shared configuration context instance
settings = AppSettings()
