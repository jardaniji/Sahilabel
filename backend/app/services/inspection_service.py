from dataclasses import dataclass


@dataclass
class InspectionService:
    def create_inspection(self, product_name: str, image_count: int = 1, source: str = "upload") -> dict:
        return {
            "inspection_id": "insp-demo-001",
            "product_name": product_name,
            "status": "QUEUED",
            "image_count": image_count,
            "source": source,
            "workflow": "Input -> Image Quality -> CV/OCR -> Applicability -> Rule Validation -> Final Report",
        }


inspection_service = InspectionService()
