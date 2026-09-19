"""Run the inspector-review model without starting the API."""
import json
from inspector_review import create_inspector_review

if __name__ == "__main__":
    automated = {"inspection_id": "demo-001", "status": "REVIEW", "overall_compliant": False}
    review = create_inspector_review(reviewer="demo-inspector", automated_decision=automated, inspector_decision="OVERRIDDEN", reason="Physical label verified.", field_confirmations={"mrp_present": True})
    print(json.dumps(review.to_dict(), indent=2))
