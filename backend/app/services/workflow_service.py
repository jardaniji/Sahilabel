from __future__ import annotations

from typing import Any

from app.services.applicability_service import ApplicabilityService
from app.services.compliance_service import ComplianceService
from app.services.image_quality_service import ImageQualityService


class WorkflowService:
    """Coordinates the target Input -> Quality -> OCR -> Rules workflow."""

    @staticmethod
    def process_image(image_path: str, inspection_id: str) -> dict[str, Any]:
        quality = ImageQualityService.assess_image_quality(image_path)
        if not quality.get("is_acceptable"):
            return {
                "inspection_id": inspection_id,
                "status": "IMAGE_REVIEW_REQUIRED",
                "quality": quality,
                "applicability": None,
                "analysis": None,
            }

        ocr_result = __import__("ocr_pipeline").extract_text(image_path, processed_path=None)
        applicability = ApplicabilityService.classify(ocr_result.get("full_text", ""))
        analysis = ComplianceService.analyze_image(image_path)
        status = analysis.get("overall_status", "REVIEW")
        if applicability.get("requires_human_confirmation") and status == "PASS":
            status = "REVIEW"

        return {
            "inspection_id": inspection_id,
            "status": status,
            "quality": quality,
            "applicability": applicability,
            "analysis": analysis,
            "ocr": {
                "full_text": ocr_result.get("full_text", ""),
                "word_count": len(ocr_result.get("words", [])),
                "preprocessing": ocr_result.get("preprocessing", {}),
            },
        }
