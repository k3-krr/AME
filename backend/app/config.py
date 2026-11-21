import os
from typing import Optional
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict



class AppSettings(BaseSettings):
    """Application configuration schema representing verified env bindings."""

    # Environment Context
    ENV: str = "development"
    DEBUG: bool = True
    TESTING: bool = False  # Set to true in test environments to suppress live network calls

    # Backend Ports & Gateway Configurations
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Adaptive Memory Engine (AME)"
    CORS_ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

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
    LLM_PROVIDER: str = "openrouter"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "gpt-4o"
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # OpenRouter Config
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "meta-llama/llama-3.1-8b-instruct"
    OPENROUTER_SITE_URL: str = "http://localhost:3000"
    OPENROUTER_APP_NAME: str = "AME"

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

    # Configurable Hybrid system ranking weights
    SEMANTIC_WEIGHT: float = 1.0
    EPISODIC_WEIGHT: float = 1.0
    PROCEDURAL_WEIGHT: float = 1.0
    WORKING_WEIGHT: float = 1.0

    SEMANTIC_MEMORY_WEIGHT: float = 1.0
    EPISODIC_MEMORY_WEIGHT: float = 1.0
    PROCEDURAL_MEMORY_WEIGHT: float = 1.0
    WORKING_MEMORY_WEIGHT: float = 1.0

    # Configurable inner-attributes weights
    SEMANTIC_SIMILARITY_WEIGHT: float = 0.5
    SEMANTIC_IMPORTANCE_WEIGHT: float = 0.3
    SEMANTIC_FREQUENCY_WEIGHT: float = 0.2

    EPISODIC_SIMILARITY_WEIGHT: float = 0.4
    EPISODIC_RECENCY_WEIGHT: float = 0.4
    EPISODIC_IMPORTANCE_WEIGHT: float = 0.2

    PROCEDURAL_SIMILARITY_WEIGHT: float = 0.4
    PROCEDURAL_FREQUENCY_WEIGHT: float = 0.3
    PROCEDURAL_SUCCESS_WEIGHT: float = 0.3

    WORKING_PRIORITY_WEIGHT: float = 0.4
    WORKING_RECENCY_WEIGHT: float = 0.4
    WORKING_ACTIVE_WEIGHT: float = 0.2

    # Mix factors
    W_HYBRID_ADAPTIVE: float = 0.5
    W_HYBRID_SYSTEM: float = 0.5

    # Knowledge Graph Settings
    GRAPH_MAX_TRAVERSAL_DEPTH: int = 5
    GRAPH_EXPANSION_ENABLED: bool = True
    GRAPH_EXPANSION_MAX_DEPTH: int = 2
    GRAPH_EXPANSION_MAX_MEMORIES: int = 50
    GRAPH_EXPANSION_MAX_NODES: int = 20
    GRAPH_EXPANSION_DECAY: float = 0.9
    GRAPH_EXPANSION_STRATEGY: str = "BFS"

    @field_validator("GRAPH_EXPANSION_DECAY")
    @classmethod
    def validate_decay(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("GRAPH_EXPANSION_DECAY must be between 0.0 and 1.0 inclusive")
        return v

    @field_validator("GRAPH_EXPANSION_STRATEGY")
    @classmethod
    def validate_strategy(cls, v: str) -> str:
        v_upper = v.upper()
        if v_upper not in ("BFS", "DFS"):
            raise ValueError("GRAPH_EXPANSION_STRATEGY must be either 'BFS' or 'DFS'")
        return v_upper

    @field_validator(
        "GRAPH_EXPANSION_MAX_DEPTH",
        "GRAPH_EXPANSION_MAX_MEMORIES",
        "GRAPH_EXPANSION_MAX_NODES",
        "GRAPH_MAX_TRAVERSAL_DEPTH"
    )
    @classmethod
    def validate_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Graph limit setting must be non-negative")
        return v




    # Retrieval Platform Configurations (Milestone 9)
    RETRIEVAL_DEFAULT_STRATEGY: str = "standard_rag"
    RETRIEVAL_MAX_ELEMENTS: int = 20
    RETRIEVAL_TIMEOUT_SECONDS: float = 5.0
    RETRIEVAL_MAX_QUERY_LENGTH: int = 1000


    @model_validator(mode="after")
    def validate_jwt_secret_safety(self) -> "AppSettings":
        is_production = self.ENV.lower() == "production" or not self.DEBUG
        default_secret = "secret-tokens-change-on-production-environments-310aefb"
        if is_production and self.JWT_SECRET_KEY == default_secret:
            raise ValueError(
                "Production environment detected but default/insecure JWT_SECRET_KEY is being used. "
                "The application cannot start under an insecure configuration."
            )
        return self

    # Settings config path mapping to .env file if available
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Globally shared configuration context instance
settings = AppSettings()
