import unittest
from datetime import datetime, timezone

from inspector_review import InspectorReviewError, create_inspector_review


class InspectorReviewTests(unittest.TestCase):
    def test_confirmation_preserves_automated_decision(self):
        automated = {"overall": "PASS", "status": "PASS"}
        review = create_inspector_review(
            reviewer="insp-42", automated_decision=automated, inspector_decision="confirmed",
            reason="Label matches checklist.", field_confirmations={"mrp": True},
        )
        automated["overall"] = "FAIL"
        payload = review.to_dict()
        self.assertEqual("PASS", payload["automated_decision"]["overall"])
        self.assertEqual("CONFIRMED", payload["inspector_decision"])

    def test_override_keeps_original_automated_result(self):
        reviewed_at = datetime(2026, 9, 19, 1, 0, tzinfo=timezone.utc)
        payload = create_inspector_review(
            reviewer="Jay", automated_decision="FAIL", inspector_decision="OVERRIDDEN",
            reason="Physical package confirms the declaration.", reviewed_at=reviewed_at,
        ).to_dict()
        self.assertEqual("FAIL", payload["automated_decision"])
        self.assertEqual("2026-09-19T01:00:00+00:00", payload["reviewed_at"])

    def test_pending_review_allows_missing_reason(self):
        payload = create_inspector_review(
            reviewer="insp-7", automated_decision={"status": "REVIEW"}, inspector_decision="PENDING",
        ).to_dict()
        self.assertIsNone(payload["reason"])

    def test_final_decisions_require_reason(self):
        for decision in ("CONFIRMED", "OVERRIDDEN"):
            with self.assertRaises(InspectorReviewError):
                create_inspector_review(reviewer="insp-1", automated_decision="PASS", inspector_decision=decision)

    def test_invalid_status_is_rejected(self):
        with self.assertRaises(InspectorReviewError):
            create_inspector_review(reviewer="insp-1", automated_decision="PASS", inspector_decision="APPROVED")


if __name__ == "__main__":
    unittest.main()
