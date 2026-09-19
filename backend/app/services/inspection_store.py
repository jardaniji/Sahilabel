from __future__ import annotations

from typing import Any

from app.services.compliance_service import ComplianceService
from app.services.image_quality_service import ImageQualityService


_INSPECTION_STORE: dict[str, dict[str, Any]] = {}


def create_demo_record(inspection_id: str, product_name: str, image_count: int = 1) -> dict[str, Any]:
    record = {
        "inspection_id": inspection_id,
        "product_name": product_name,
        "image_count": image_count,
        "status": "QUEUED",
        "workflow": "Input -> Image Quality -> CV/OCR -> Applicability -> Rule Validation -> Final Report",
        "quality": {"quality_score": 0, "is_acceptable": False, "warnings": ["No image uploaded in demo mode."]},
        "analysis": {"overall_status": "REVIEW", "overall_compliant": False, "rules": []},
    }
    _INSPECTION_STORE[inspection_id] = record
    return record


def get_inspection_record(inspection_id: str) -> dict[str, Any]:
    return _INSPECTION_STORE.get(inspection_id, {})


def update_quality(inspection_id: str, image_path: str) -> dict[str, Any]:
    quality = ImageQualityService.assess_image_quality(image_path)
    record = _INSPECTION_STORE.setdefault(inspection_id, {"inspection_id": inspection_id})
    record["quality"] = quality
    return quality


def update_analysis(inspection_id: str, image_path: str) -> dict[str, Any]:
    analysis = ComplianceService.analyze_image(image_path)
    record = _INSPECTION_STORE.setdefault(inspection_id, {"inspection_id": inspection_id})
    record["analysis"] = analysis
    record["status"] = analysis.get("overall_status", "REVIEW")
    return analysis
