from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

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

    return InspectionResult(
        inspection_id="insp-demo-001",
        status="QUEUED",
        product_name=payload.product_name,
        image_count=payload.image_count,
    )


@router.get("/inspections/{inspection_id}")
def get_inspection(inspection_id: str) -> dict:
    return {
        "inspection_id": inspection_id,
        "status": "PROCESSING",
        "workflow": "Input -> Image Quality -> CV/OCR -> Applicability -> Rule Validation -> Final Report",
        "notes": "This route is scaffolded for the phase-1 architecture alignment pass.",
    }
