"""Authentication + role-based access control.

* Users are PostgreSQL LOGIN roles. PostgreSQL stores their passwords as
  SCRAM-SHA-256 hashes, and login is verified by PostgreSQL itself: we try to
  open a connection with the supplied credentials.
* The user's application role comes from role membership
  (member of gs_admin -> "admin", member of gs_security -> "security").
* A signed JWT carries {sub, role}. Every protected endpoint checks it, and the
  database session then runs `SET LOCAL ROLE gs_admin|gs_security`, so the same
  rule is enforced twice: in the API and inside PostgreSQL.
"""
from datetime import datetime, timedelta, timezone

import jwt
import psycopg
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from .config import settings

ALGORITHM = "HS256"
bearer = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    username: str
    role: str          # "admin" | "security"


def verify_credentials(username: str, password: str) -> CurrentUser | None:
    try:
        with psycopg.connect(host=settings.PG_HOST, port=settings.PG_PORT,
                             dbname=settings.PG_DATABASE, user=username, password=password,
                             connect_timeout=5) as conn:
            row = conn.execute("""
                SELECT pg_has_role(current_user, 'gs_admin', 'MEMBER'),
                       pg_has_role(current_user, 'gs_security', 'MEMBER')""").fetchone()
    except psycopg.OperationalError as exc:
        msg = str(exc).lower()
        if "password authentication failed" in msg or "does not exist" in msg \
                or "permission denied" in msg:
            return None
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "PostgreSQL server unavailable") from exc
    if username == settings.PG_APP_USER:      # the service account is not a person
        return None
    if row[0]:
        return CurrentUser(username=username, role="admin")
    if row[1]:
        return CurrentUser(username=username, role="security")
    return None


def create_token(user: CurrentUser) -> str:
    payload = {
        "sub": user.username,
        "role": user.role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> CurrentUser:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        data = jwt.decode(creds.credentials, settings.JWT_SECRET, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired") from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from exc
    if data.get("role") not in ("admin", "security"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    return CurrentUser(username=data["sub"], role=data["role"])


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return user
