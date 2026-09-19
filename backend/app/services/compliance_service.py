from __future__ import annotations

import json
from typing import Any

from compliance_checker import check_fields
from ocr_pipeline import extract_text


class ComplianceService:
    """Thin adapter around the existing SAHILABEL OCR + rule engine."""

    @staticmethod
    def analyze_image(image_path: str) -> dict[str, Any]:
        ocr_result = extract_text(image_path, processed_path=None)
        report = check_fields({"full_text": ocr_result.get("full_text", ""), "words": ocr_result.get("words", [])})

        return {
            "overall_status": report.get("overall_status", "REVIEW"),
            "overall_compliant": bool(report.get("overall_compliant", False)),
            "automated_score": report.get("automated_score"),
            "rules": report.get("rules", []),
            "structured_fields": report.get("structured_fields", {}),
            "notes": report.get("notes", []),
            "readability_flags": report.get("readability_flags", []),
        }

    @staticmethod
    def analyze_payload(payload: dict[str, Any]) -> dict[str, Any]:
        result = {
            "inspection_id": payload.get("inspection_id", "demo-inspection"),
            "overall_status": "REVIEW",
            "overall_compliant": False,
            "rules": [],
            "notes": ["This was created using the architecture-alignment compatibility layer."],
            "workflow": "Input -> Image Quality -> CV/OCR -> Applicability -> Rule Validation -> Final Report",
        }

        image_paths = payload.get("image_paths") or []
        if image_paths:
            analysis = ComplianceService.analyze_image(image_paths[0])
            result.update(analysis)
            result["image_count"] = len(image_paths)
        else:
            result["image_count"] = 0

        return result
