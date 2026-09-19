from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes.auth import router as auth_router
from app.routes.inspections import router as inspections_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Database initialization is deliberately best-effort for local development.
    try:
        from app.db import init_db
        init_db()
    except Exception:
        pass
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(inspections_router, prefix="/api/v1")


@app.get("/health")
def healthcheck() -> dict:
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment, "version": settings.app_version}


@app.get("/api/v1/config")
def public_config() -> dict:
    return {
        "app_name": settings.app_name,
        "environment": settings.environment,
        "max_upload_mb": 15,
        "workflow": "Input -> Image Quality -> CV/OCR -> Applicability -> Rule Validation -> Final Report",
    }


@app.get("/api/v1/status")
def status_summary() -> dict:
    return {"status": "ok", "architecture_phase": "phase-2-production-backend", "workflow": "Input -> Image Quality -> CV/OCR -> Applicability -> Rule Validation -> Final Report"}
