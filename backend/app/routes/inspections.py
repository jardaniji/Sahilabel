from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.services.inspection_store import create_demo_record, get_inspection_record
from app.services.workflow_service import WorkflowService

router = APIRouter(tags=["inspections"])
UPLOAD_DIR = Path("uploads") / "architecture"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


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


@router.get("/inspections")
def list_inspections() -> list[dict]:
    return [
        {
            "inspection_id": "demo-001",
            "product_name": "Sample label",
            "status": "READY_FOR_REVIEW",
            "image_count": 2,
        }
    ]


@router.post("/inspections", response_model=InspectionResult, status_code=status.HTTP_201_CREATED)
def create_inspection(payload: InspectionCreate) -> InspectionResult:
    if not payload.product_name.strip():
        raise HTTPException(status_code=400, detail="Product name is required")

    inspection_id = f"insp-{uuid.uuid4().hex[:10]}"
    create_demo_record(inspection_id, payload.product_name, payload.image_count)
    return InspectionResult(
        inspection_id=inspection_id,
        status="QUEUED",
        product_name=payload.product_name,
        image_count=payload.image_count,
    )


@router.post("/inspections/analyze")
async def analyze_inspection(
    file: UploadFile = File(...),
    product_name: str = Form(default="Uploaded label"),
):
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload an image file")

    inspection_id = f"insp-{uuid.uuid4().hex[:10]}"
    suffix = Path(file.filename or "label.jpg").suffix.lower() or ".jpg"
    image_path = UPLOAD_DIR / f"{inspection_id}{suffix}"
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded image is empty")
    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image must be smaller than 15 MB")

    image_path.write_bytes(content)
    create_demo_record(inspection_id, product_name.strip() or "Uploaded label", 1)
    result = WorkflowService.process_image(str(image_path), inspection_id)
    result.update({
        "product_name": product_name.strip() or "Uploaded label",
        "filename": os.path.basename(image_path),
    })
    return result


@router.get("/inspections/{inspection_id}")
def get_inspection(inspection_id: str) -> dict:
    record = get_inspection_record(inspection_id)
    if not record:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return record
