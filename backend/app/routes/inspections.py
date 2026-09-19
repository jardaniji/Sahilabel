from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.db import get_inspection, init_db, save_inspection
from app.queue import enqueue_analysis, get_job_status
from app.services.inspection_store import create_demo_record, get_inspection_record

router = APIRouter(tags=["inspections"])
UPLOAD_DIR = Path("uploads") / "architecture"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_BYTES = 15 * 1024 * 1024


class InspectionCreate(BaseModel):
    product_name: str = Field(..., min_length=1)
    image_count: int = Field(default=1, ge=1, le=8)
    source: str = Field(default="upload")


class InspectionResult(BaseModel):
    inspection_id: str
    status: str
    product_name: str
    image_count: int
    workflow: str = "Input -> Image Quality -> CV/OCR -> Applicability -> Rule Validation -> Final Report"


def _record(inspection_id: str) -> dict:
    return get_inspection_record(inspection_id) or get_inspection(inspection_id) or {}


@router.get("/inspections")
def list_inspections() -> list[dict]:
    return []


@router.post("/inspections", response_model=InspectionResult, status_code=status.HTTP_201_CREATED)
def create_inspection(payload: InspectionCreate) -> InspectionResult:
    inspection_id = f"insp-{uuid.uuid4().hex[:10]}"
    record = create_demo_record(inspection_id, payload.product_name.strip(), payload.image_count)
    try:
        init_db()
        save_inspection(record)
    except Exception:
        # Local development can run without PostgreSQL; the worker/API remain usable.
        pass
    return InspectionResult(inspection_id=inspection_id, status="QUEUED", product_name=payload.product_name, image_count=payload.image_count)


@router.post("/inspections/analyze")
async def analyze_inspection(file: UploadFile = File(...), product_name: str = Form(default="Uploaded label")):
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload an image file")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded image is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image must be smaller than 15 MB")

    inspection_id = f"insp-{uuid.uuid4().hex[:10]}"
    suffix = Path(file.filename or "label.jpg").suffix.lower() or ".jpg"
    image_path = UPLOAD_DIR / f"{inspection_id}{suffix}"
    image_path.write_bytes(content)
    record = create_demo_record(inspection_id, product_name.strip() or "Uploaded label", 1)
    record["image_path"] = str(image_path)
    try:
        init_db()
        save_inspection(record)
    except Exception:
        pass

    try:
        job_id = enqueue_analysis({"inspection_id": inspection_id, "image_path": str(image_path)})
        return {**record, "status": "QUEUED", "job_id": job_id}
    except Exception:
        # Redis is optional during local development; report the fallback explicitly.
        return {**record, "status": "QUEUED", "job_id": inspection_id, "queue_warning": "Redis unavailable; start docker compose before running the worker."}


@router.get("/inspections/{inspection_id}")
def get_inspection_route(inspection_id: str) -> dict:
    record = _record(inspection_id)
    if not record:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return record


@router.get("/inspections/{inspection_id}/status")
def get_inspection_status(inspection_id: str) -> dict:
    record = _record(inspection_id)
    if not record:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return get_job_status(inspection_id) or {
        "inspection_id": inspection_id,
        "status": record.get("status", "REVIEW"),
        "quality": record.get("quality", {}),
        "analysis": record.get("analysis", {}),
    }
