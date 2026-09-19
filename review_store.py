"""SQLite-backed persistence for inspector review audit records."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from inspector_review import InspectorReview, create_inspector_review

DB_PATH = Path("data") / "sahilabel_reviews.sqlite3"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS inspector_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inspection_id TEXT NOT NULL,
            reviewer TEXT NOT NULL,
            reviewed_at TEXT NOT NULL,
            automated_decision TEXT NOT NULL,
            inspector_decision TEXT NOT NULL,
            reason TEXT,
            field_confirmations TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_reviews_inspection ON inspector_reviews(inspection_id)"
    )
    connection.commit()
    return connection


def save_review(inspection_id: str, review: InspectorReview) -> dict[str, Any]:
    payload = review.to_dict()
    with _connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO inspector_reviews
            (inspection_id, reviewer, reviewed_at, automated_decision,
             inspector_decision, reason, field_confirmations)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                inspection_id,
                payload["reviewer"],
                payload["reviewed_at"],
                json.dumps(payload["automated_decision"]),
                payload["inspector_decision"],
                payload["reason"],
                json.dumps(payload["field_confirmations"]),
            ),
        )
        connection.commit()
        payload["id"] = cursor.lastrowid
        payload["inspection_id"] = inspection_id
    return payload


def list_reviews(inspection_id: str) -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            "SELECT * FROM inspector_reviews WHERE inspection_id = ? ORDER BY id",
            (inspection_id,),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def final_decision(inspection_id: str) -> dict[str, Any] | None:
    reviews = list_reviews(inspection_id)
    if not reviews:
        return None
    latest = reviews[-1]
    return {
        "inspection_id": inspection_id,
        "automated_decision": latest["automated_decision"],
        "inspector_decision": latest["inspector_decision"],
        "finalized": latest["inspector_decision"] in {"CONFIRMED", "OVERRIDDEN"},
        "review": latest,
    }


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "inspection_id": row["inspection_id"],
        "reviewer": row["reviewer"],
        "reviewed_at": row["reviewed_at"],
        "automated_decision": json.loads(row["automated_decision"]),
        "inspector_decision": row["inspector_decision"],
        "reason": row["reason"],
        "field_confirmations": json.loads(row["field_confirmations"])
        if row["field_confirmations"] else None,
    }
