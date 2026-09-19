"""Run a dependency-free inspector-review dummy workflow.

Run from the repository root:
    python run_dummy_review.py
"""

import json

from inspector_review import create_inspector_review


if __name__ == "__main__":
    automated = {
        "inspection_id": "demo-001",
        "status": "REVIEW",
        "overall_compliant": False,
        "failed_rules": ["mrp_present"],
    }
    review = create_inspector_review(
        reviewer="demo-inspector",
        automated_decision=automated,
        inspector_decision="OVERRIDDEN",
        reason="Dummy run: physical label confirms the MRP declaration.",
        field_confirmations={"mrp_present": True},
    )
    print(json.dumps(review.to_dict(), indent=2))
    print("\nAutomated result remains:", automated["overall_compliant"])
    print("Inspector result is:", review.inspector_decision)
