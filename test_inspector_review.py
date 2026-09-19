import unittest
from inspector_review import InspectorReviewError, create_inspector_review


class InspectorReviewTests(unittest.TestCase):
    def test_automated_decision_is_copied(self):
        automated = {"status": "PASS"}
        review = create_inspector_review(reviewer="inspector", automated_decision=automated, inspector_decision="CONFIRMED", reason="Verified")
        automated["status"] = "FAIL"
        self.assertEqual("PASS", review.to_dict()["automated_decision"]["status"])

    def test_pending_needs_no_reason(self):
        self.assertEqual("PENDING", create_inspector_review(reviewer="i", automated_decision="REVIEW", inspector_decision="pending").inspector_decision)

    def test_final_decision_needs_reason(self):
        with self.assertRaises(InspectorReviewError):
            create_inspector_review(reviewer="i", automated_decision="PASS", inspector_decision="CONFIRMED")


if __name__ == "__main__":
    unittest.main()
