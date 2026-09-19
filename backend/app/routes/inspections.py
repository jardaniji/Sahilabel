from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.auth import DEMO_USERS, create_access_token, get_current_user, require_roles
from app.db import get_inspection, init_db, save_inspection
from app.queue import enqueue_analysis, get_job_status
from app.services.inspection_store import create_demo_record, get_inspection_record

router = APIRouter(tags=["inspections"])
UPLOAD_DIR = Path("uploads") / "inspection"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_BYTES = 15 * 1024 * 1024


class InspectionCreate(BaseModel):
    product_name: str
    image_count: int = 1
    source: str = "upload"


class InspectionResult(BaseModel):
    inspection_id: str
    status: str
    product_name: str
    image_count: int
    workflow: str = "Input -> Image Quality -> CV/OCR -> Applicability -> Rule Validation -> Final Report"


def _record(inspection_id: str) -> dict:
    return get_inspection_record(inspection_id) or get_inspection(inspection_id) or {}


@router.get("/inspections")
def list_inspections(user: dict[str, Any] = Depends(require_roles("admin", "inspector", "viewer"))) -> list[dict]:
    records = [
        {"inspection_id": "demo-001", "product_name": "Sample label", "status": "READY_FOR_REVIEW", "image_count": 2},
    ]
    return records


@router.post("/inspections", response_model=InspectionResult, status_code=status.HTTP_201_CREATED)
def create_inspection(payload: InspectionCreate, user: dict[str, Any] = Depends(require_roles("admin", "inspector"))) -> InspectionResult:
    inspection_id = f"insp-{payload.product_name.lower().replace(' ', '-')[:12]}-{abs(hash(payload.product_name + user['username'])) % 10000:04d}"
    record = create_demo_record(inspection_id, payload.product_name.strip(), payload.image_count)
    try:
        init_db()
        save_inspection(record)
    except Exception:
        pass
    return InspectionResult(inspection_id=inspection_id, status="QUEUED", product_name=payload.product_name, image_count=payload.image_count)


@router.get("/inspections/{inspection_id}")
def get_inspection_route(inspection_id: str, user: dict[str, Any] = Depends(require_roles("admin", "inspector", "viewer"))) -> dict:
    record = _record(inspection_id)
    if not record:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return record


@router.get("/inspections/{inspection_id}/status")
def get_inspection_status(inspection_id: str, user: dict[str, Any] = Depends(require_roles("admin", "inspector", "viewer"))) -> dict:
    record = _record(inspection_id)
    if not record:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return get_job_status(inspection_id) or {
        "inspection_id": inspection_id,
        "status": record.get("status", "REVIEW"),
        "quality": record.get("quality", {}),
        "analysis": record.get("analysis", {}),
    }


@router.post("/inspections/{inspection_id}/queue")
def queue_inspection(inspection_id: str, image_path: str, user: dict[str, Any] = Depends(require_roles("admin", "inspector"))) -> dict:
    payload = {"inspection_id": inspection_id, "image_path": image_path}
    job_id = enqueue_analysis(payload)
    return {"inspection_id": inspection_id, "job_id": job_id, "status": "QUEUED"}


@router.post("/inspections/analyze")
async def analyze_inspection(
    file: UploadFile = File(...),
    product_name: str = Form("Uploaded label"),
    user: dict[str, Any] = Depends(require_roles("admin", "inspector")),
) -> dict:
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
        return {**record, "status": "QUEUED", "job_id": inspection_id, "queue_warning": "Redis not available; start Redis before running the worker."}
