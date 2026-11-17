"""Central configuration loaded from backend/.env (never hard-coded)."""
import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent          # backend/
PROJECT_DIR = BASE_DIR.parent                              # repo root
load_dotenv(BASE_DIR / ".env")


def _req(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable {name} (see backend/.env.example)")
    return value


class Settings:
    PG_HOST = os.getenv("PG_HOST", "localhost")
    PG_PORT = int(os.getenv("PG_PORT", "5432"))
    PG_DATABASE = os.getenv("PG_DATABASE", "gatesentry")
    PG_SUPERUSER = os.getenv("PG_SUPERUSER", "postgres")
    PG_SUPERUSER_PASSWORD = os.getenv("PG_SUPERUSER_PASSWORD", "")
    PG_APP_USER = os.getenv("PG_APP_USER", "gatesentry_app")
    PG_APP_PASSWORD = _req("PG_APP_PASSWORD")

    DEMO_ADMIN_USER = os.getenv("DEMO_ADMIN_USER", "admin")
    DEMO_ADMIN_PASSWORD = os.getenv("DEMO_ADMIN_PASSWORD", "")
    DEMO_SECURITY_USER = os.getenv("DEMO_SECURITY_USER", "guard")
    DEMO_SECURITY_PASSWORD = os.getenv("DEMO_SECURITY_PASSWORD", "")

    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB = os.getenv("MONGO_DB", "gatesentry")

    JWT_SECRET = _req("JWT_SECRET")
    JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))
    FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")

    @classmethod
    def pg_url(cls, user: str, password: str, database: str | None = None) -> str:
        return (f"postgresql+psycopg://{quote_plus(user)}:{quote_plus(password)}"
                f"@{cls.PG_HOST}:{cls.PG_PORT}/{database or cls.PG_DATABASE}")


settings = Settings()
