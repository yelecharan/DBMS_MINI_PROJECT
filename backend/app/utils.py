import uuid
from datetime import datetime, timezone


def new_id(prefix: str) -> str:
    """Readable unique id for MongoDB documents, e.g. OBS-3F9A1C2B."""
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
