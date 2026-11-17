from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker, declarative_base
from app.core.config import settings
import logging

logger = logging.getLogger("gatesentry.db")

DATABASE_URL = settings.DATABASE_URL

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True
)

_DB_ROLE_INFO_KEY = "gatesentry_database_role"
_APPLICATION_DATABASE_ROLES = {
    "ADMIN": "gg_admin",
    "SECURITY_OFFICER": "gg_security",
    "AUDITOR": "gg_auditor",
}


@event.listens_for(engine, "begin")
def _apply_transaction_role(connection):
    role = connection.info.get(_DB_ROLE_INFO_KEY)
    if role:
        connection.exec_driver_sql(f"SET LOCAL ROLE {role}")


@event.listens_for(engine.pool, "checkin")
def _clear_pooled_transaction_role(dbapi_connection, connection_record):
    connection_record.info.pop(_DB_ROLE_INFO_KEY, None)


def activate_database_role(db: Session, application_role: str) -> None:
    """Apply the mapped PostgreSQL role for this request's transaction."""
    if not DATABASE_URL.startswith(("postgresql://", "postgresql+")):
        return

    database_role = _APPLICATION_DATABASE_ROLES.get(application_role)
    if database_role is None:
        raise ValueError(f"Unsupported application role: {application_role}")

    connection = db.connection()
    connection.info[_DB_ROLE_INFO_KEY] = database_role
    connection.exec_driver_sql(f"SET LOCAL ROLE {database_role}")


# Enable foreign keys for SQLite
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Dependency for obtaining database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
