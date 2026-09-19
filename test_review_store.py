import os
import tempfile
import unittest
from datetime import datetime, timezone

import review_store
from inspector_review import create_inspector_review


class ReviewStoreTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        review_store.DB_PATH = os.path.join(self.tempdir.name, "reviews.sqlite3")

    def tearDown(self):
        self.tempdir.cleanup()

    def test_review_history_and_final_decision(self):
        review = create_inspector_review(
            reviewer="inspector", automated_decision={"status": "REVIEW"},
            inspector_decision="CONFIRMED", reason="Verified against package.",
            reviewed_at=datetime(2026, 9, 19, tzinfo=timezone.utc),
        )
        saved = review_store.save_review("demo-001", review)
        self.assertEqual("CONFIRMED", saved["inspector_decision"])
        self.assertEqual(1, len(review_store.list_reviews("demo-001")))
        self.assertTrue(review_store.final_decision("demo-001")["finalized"])


if __name__ == "__main__":
    unittest.main()
