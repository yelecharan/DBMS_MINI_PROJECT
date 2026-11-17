from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.database.session import Base, engine, SessionLocal, activate_database_role
from app.models.models import User, Employee, Site, Gate
from app.api.routes import (
    auth, employees, gates, access_events, ingest, 
    gate_sessions, incidents, investigations, vector, 
    analytics, demo, audit, users
)
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("gatesentry")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Explainable, Privacy-First Office Tailgating Detection and Incident Intelligence System",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS configuration for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(auth.router, prefix="/api")
app.include_router(employees.router, prefix="/api")
app.include_router(gates.router, prefix="/api")
app.include_router(access_events.router, prefix="/api")
app.include_router(ingest.router, prefix="/api")
app.include_router(gate_sessions.router, prefix="/api")
app.include_router(incidents.router, prefix="/api")
app.include_router(investigations.router, prefix="/api")
app.include_router(vector.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(demo.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(users.router, prefix="/api")

@app.on_event("startup")
def on_startup():
    logger.info("Initializing GateSentry database schema...")
    Base.metadata.create_all(bind=engine)
    if settings.ENVIRONMENT == "development":
        with SessionLocal() as db:
            activate_database_role(db, "ADMIN")
            empty_demo_store = not any(db.query(model).first() for model in (User, Employee, Site, Gate))
        if empty_demo_store:
            logger.info("Empty development database detected; loading demo seed data.")
            from app.seed.seed_data import seed_database
            seed_database()
    logger.info("Database schema initialized.")

@app.get("/")
def root():
    return {
        "project": "GateSentry",
        "tagline": "Explainable Office Tailgating Detection and Incident Intelligence Platform",
        "version": settings.VERSION,
        "docs": "/docs",
        "status": "OPERATIONAL"
    }

@app.get("/health")
def health():
    return {"status": "HEALTHY"}
