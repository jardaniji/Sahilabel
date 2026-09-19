from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth import require_roles
from app.db import get_inspection, init_db, save_inspection
from app.queue import enqueue_analysis, get_job_status
from app.services.inspection_store import create_demo_record, get_inspection_record

router = APIRouter(tags=["inspections"])


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
