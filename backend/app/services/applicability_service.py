from __future__ import annotations

from typing import Any


class ApplicabilityService:
    """Conservative first-pass applicability classification.

    The result is deliberately reviewable: uncertain categories never silently
    become compliant or not-applicable.
    """

    KEYWORDS = {
        "food": {"food", "ingredients", "nutrition", "fssai", "packed"},
        "cosmetic": {"cosmetic", "shampoo", "cream", "lotion", "soap"},
        "drug": {"tablet", "capsule", "syrup", "medicine", "drug"},
        "liquid": {"ml", "litre", "liter"},
        "textile": {"cotton", "fabric", "textile", "towel", "saree"},
    }

    @classmethod
    def classify(cls, text: str) -> dict[str, Any]:
        normalized = (text or "").lower()
        scores = {
            category: sum(1 for keyword in keywords if keyword in normalized)
            for category, keywords in cls.KEYWORDS.items()
        }
        product_type, score = max(scores.items(), key=lambda item: item[1])
        if score == 0:
            return {
                "product_type": "unknown",
                "confidence": 0.0,
                "requires_human_confirmation": True,
                "reason": "No product category was reliably identified from OCR text.",
            }

        confidence = min(0.95, 0.55 + (score * 0.1))
        return {
            "product_type": product_type,
            "confidence": round(confidence, 2),
            "requires_human_confirmation": confidence < 0.75,
            "reason": "Category inferred from OCR keywords; inspector confirmation remains available.",
        }
