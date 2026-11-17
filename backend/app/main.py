"""GateSentry API - FastAPI application.

    uvicorn app.main:app --reload --port 8000     (from backend/)
"""
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import DuplicateKeyError, PyMongoError, ServerSelectionTimeoutError, WriteError
from sqlalchemy.exc import DBAPIError, OperationalError

from .auth import CurrentUser, create_token, get_current_user, verify_credentials
from .config import settings
from .db import ping_mongo, ping_postgres
from .routers import (access_logs, alerts, analytics, cards, employees, gates, incidents,
                      observations, reports)
from .schemas import LoginIn

app = FastAPI(title="GateSentry API", version="1.0.0",
              description="Tailgating detection DBMS project - PostgreSQL + MongoDB")

app.add_middleware(CORSMiddleware, allow_origins=[settings.FRONTEND_ORIGIN],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ------------------------- error handling -------------------------
SQLSTATE_HTTP = {
    "23505": (409, "Duplicate value"),             # unique_violation
    "23503": (409, "Referenced record problem"),   # foreign_key_violation
    "23001": (409, "Record is still referenced (audit trail kept) - deactivate it instead"),
    "23514": (400, "Constraint violated"),         # check_violation (CHECKs + our triggers)
    "23502": (400, "Missing required value"),      # not_null_violation
    "42501": (403, "Permission denied by database role"),
    "22007": (400, "Invalid date/time"),
    "22008": (400, "Date/time out of range"),
}


@app.exception_handler(OperationalError)
async def pg_down(_: Request, exc: OperationalError):
    return JSONResponse(status_code=503, content={"detail": "PostgreSQL unavailable: "
                                                  + str(exc.orig).splitlines()[0]})


@app.exception_handler(DBAPIError)
async def pg_error(_: Request, exc: DBAPIError):
    orig = exc.orig
    code = getattr(orig, "sqlstate", None)
    status, label = SQLSTATE_HTTP.get(code, (400, "Database error"))
    diag = getattr(orig, "diag", None)
    msg = (diag.message_primary if diag and diag.message_primary else str(orig)).strip()
    detail = getattr(diag, "message_detail", None) if diag else None
    text_ = f"{label}: {msg}" + (f" ({detail})" if detail else "")
    return JSONResponse(status_code=status, content={"detail": text_, "sqlstate": code})


@app.exception_handler(DuplicateKeyError)
async def mongo_dup(_: Request, exc: DuplicateKeyError):
    return JSONResponse(status_code=409, content={"detail": "Duplicate document id"})


@app.exception_handler(WriteError)
async def mongo_write(_: Request, exc: WriteError):
    return JSONResponse(status_code=400, content={"detail": f"MongoDB validation failed: {exc.details.get('errmsg', exc)}"})


@app.exception_handler(ServerSelectionTimeoutError)
async def mongo_down(_: Request, exc: ServerSelectionTimeoutError):
    return JSONResponse(status_code=503, content={"detail": "MongoDB unavailable"})


@app.exception_handler(PyMongoError)
async def mongo_error(_: Request, exc: PyMongoError):
    return JSONResponse(status_code=500, content={"detail": f"MongoDB error: {exc}"})


# ------------------------- auth -------------------------
@app.post("/api/auth/login", tags=["Auth"])
def login(body: LoginIn):
    user = verify_credentials(body.username.strip(), body.password)
    if user is None:
        raise HTTPException(401, "Invalid username or password")
    return {"access_token": create_token(user), "token_type": "bearer", "user": user}


@app.get("/api/auth/me", tags=["Auth"])
def me(user: CurrentUser = Depends(get_current_user)):
    return user


@app.post("/api/auth/logout", tags=["Auth"])
def logout(user: CurrentUser = Depends(get_current_user)):
    # JWTs are stateless: the client deletes its token. Endpoint kept for symmetry/audit.
    return {"detail": f"{user.username} logged out"}


@app.get("/api/health", tags=["Health"])
def health():
    status = {}
    try:
        status["postgres"] = ping_postgres()
    except Exception as exc:  # noqa: BLE001
        status["postgres"] = f"DOWN: {exc.__class__.__name__}"
    try:
        ping_mongo()
        status["mongodb"] = f"UP ({settings.MONGO_URI.split('@')[-1]})"
    except Exception as exc:  # noqa: BLE001
        status["mongodb"] = f"DOWN: {exc.__class__.__name__}"
    return status


for r in (employees, cards, gates, access_logs, incidents, observations, reports, alerts,
          analytics):
    app.include_router(r.router)
