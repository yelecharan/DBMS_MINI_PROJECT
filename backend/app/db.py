"""Connections to the two real database servers.

PostgreSQL : SQLAlchemy engine logged in as the low-privilege `gatesentry_app` role.
             Every request opens a transaction and runs `SET LOCAL ROLE gs_admin`
             or `SET LOCAL ROLE gs_security`, so the GRANTs in 03_roles.sql are
             what really decides what a user may do.
MongoDB    : PyMongo client (local Community Server, or Atlas via MONGO_URI).
"""
from contextlib import contextmanager
from typing import Iterator

from pymongo import MongoClient
from pymongo.database import Database
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from .config import settings

ROLE_TO_PG = {"admin": "gs_admin", "security": "gs_security"}

engine = create_engine(
    settings.pg_url(settings.PG_APP_USER, settings.PG_APP_PASSWORD),
    pool_pre_ping=True,
    pool_size=5,
)

_mongo_client = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=4000, tz_aware=True)
mongo_db: Database = _mongo_client[settings.MONGO_DB]


@contextmanager
def pg_session(role: str) -> Iterator[Connection]:
    """Transaction that runs with the privileges of the application role."""
    pg_role = ROLE_TO_PG[role]                      # whitelist -> safe to inline
    with engine.begin() as conn:
        conn.execute(text(f"SET LOCAL ROLE {pg_role}"))
        yield conn


def ping_postgres() -> str:
    with engine.connect() as conn:
        return conn.execute(text("SELECT version()")).scalar_one()


def ping_mongo() -> dict:
    return _mongo_client.admin.command("ping")


def rows(result) -> list[dict]:
    return [dict(r._mapping) for r in result]
