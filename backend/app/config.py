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

    # Settings config path mapping to .env file if available
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Globally shared configuration context instance
settings = AppSettings()
