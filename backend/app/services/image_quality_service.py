from __future__ import annotations

import os
from typing import Any

from PIL import Image, ImageStat


class ImageQualityService:
    """Simple quality gate aligned to the target workflow phase."""

    @staticmethod
    def assess_image_quality(image_path: str) -> dict[str, Any]:
        if not os.path.exists(image_path):
            return {
                "quality_score": 0,
                "is_acceptable": False,
                "warnings": ["Image file not found."],
            }

        try:
            with Image.open(image_path) as img:
                img = img.convert("RGB")
                stat = ImageStat.Stat(img)
                mean = sum(stat.mean) / len(stat.mean)
                brightness = max(0, min(100, (mean / 255.0) * 100))
                variance = sum(stat.var) / len(stat.var)
                quality_score = int(max(0, min(100, round((brightness * 0.6) + (variance / 32.0) * 0.4))))

                warnings = []
                if brightness < 20:
                    warnings.append("Image is very dark; OCR may fail.")
                if brightness > 85:
                    warnings.append("Image is extremely bright; glare may reduce readability.")
                if variance < 12:
                    warnings.append("Image may be blurred or low contrast.")

                return {
                    "quality_score": quality_score,
                    "brightness": round(brightness, 1),
                    "contrast": round(variance, 1),
                    "is_acceptable": quality_score >= 45 and not warnings,
                    "warnings": warnings,
                }
        except Exception as exc:  # pragma: no cover
            return {
                "quality_score": 0,
                "is_acceptable": False,
                "warnings": [f"Unable to assess image quality: {exc.__class__.__name__}"],
            }
