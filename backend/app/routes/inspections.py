from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services.inspection_store import create_demo_record, get_inspection_record
from app.services.workflow_service import WorkflowService

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

    inspection_id = f"insp-{abs(hash(payload.product_name)) % 100000:05d}"
    create_demo_record(inspection_id, payload.product_name, payload.image_count)

    return InspectionResult(
        inspection_id=inspection_id,
        status="QUEUED",
        product_name=payload.product_name,
        image_count=payload.image_count,
    )


@router.get("/inspections/{inspection_id}")
def get_inspection(inspection_id: str) -> dict:
    record = get_inspection_record(inspection_id)
    if not record:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return record


@router.get("/inspections/{inspection_id}/status")
def get_inspection_status(inspection_id: str) -> dict:
    record = get_inspection_record(inspection_id)
    if not record:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return {
        "inspection_id": inspection_id,
        "status": record.get("status", "REVIEW"),
        "workflow": record.get("workflow", "Input -> Image Quality -> CV/OCR -> Applicability -> Rule Validation -> Final Report"),
        "quality": record.get("quality", {}),
        "analysis": record.get("analysis", {}),
    }


@router.post("/inspections/analyze")
async def analyze_inspection(file: object = None, product_name: str = "Uploaded label"):
    """Compatibility endpoint for browser upload testing.

    This route intentionally keeps the working Fashion/UX flow while keeping the
    underlying OCR/compliance engine intact.
    """
    if file is None:
        raise HTTPException(status_code=400, detail="Please upload an image")

    inspection_id = f"insp-{abs(hash(product_name + str(file))) % 100000:05d}"
    create_demo_record(inspection_id, product_name, 1)
    result = WorkflowService.process_image(getattr(file, "filename", "demo.jpg"), inspection_id)
    result.update({
        "product_name": product_name,
        "filename": getattr(file, "filename", "demo.jpg"),
    })
    return result
