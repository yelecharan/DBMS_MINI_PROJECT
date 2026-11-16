import os
import secrets
from typing import Optional


def _secret(name: str, environment: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    if environment == "development":
        return secrets.token_urlsafe(32)
    raise RuntimeError(f"{name} is required outside development.")


class Settings:
    PROJECT_NAME: str = "GateSentry"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # Security
    SECRET_KEY: str = _secret("SECRET_KEY", ENVIRONMENT)
    DETECTOR_API_KEY: str = _secret("DETECTOR_API_KEY", ENVIRONMENT)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "sqlite:///./gatesentry.db"
    )
    
    # Qdrant Vector Database
    QDRANT_URL: Optional[str] = os.getenv("QDRANT_URL", None)
    QDRANT_API_KEY: Optional[str] = os.getenv("QDRANT_API_KEY", None)
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "incident_embeddings")
    QDRANT_STORAGE_PATH: str = os.getenv("QDRANT_STORAGE_PATH", "./qdrant_storage")
    EMBEDDING_DIMENSION: int = 384
    OUTBOX_MAX_ATTEMPTS: int = int(os.getenv("OUTBOX_MAX_ATTEMPTS", "8"))
    OUTBOX_RETRY_BASE_SECONDS: int = int(os.getenv("OUTBOX_RETRY_BASE_SECONDS", "2"))
    OUTBOX_RETRY_MAX_SECONDS: int = int(os.getenv("OUTBOX_RETRY_MAX_SECONDS", "300"))
    OUTBOX_LOCK_TIMEOUT_SECONDS: int = int(os.getenv("OUTBOX_LOCK_TIMEOUT_SECONDS", "600"))
    OUTBOX_POLL_INTERVAL_SECONDS: float = float(os.getenv("OUTBOX_POLL_INTERVAL_SECONDS", "2"))
    OUTBOX_BATCH_SIZE: int = int(os.getenv("OUTBOX_BATCH_SIZE", "20"))
    
    # Business Logic Defaults
    DEFAULT_SESSION_WINDOW_SECONDS: int = 8
    DEFAULT_MIN_DETECTION_CONFIDENCE: float = 0.65
    DEFAULT_ZONE_SENSITIVITY_BONUS: int = 15

settings = Settings()
