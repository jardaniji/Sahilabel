"""Reusable inspector-review record that preserves automated decisions."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

VALID_INSPECTOR_DECISIONS = frozenset({"CONFIRMED", "OVERRIDDEN", "PENDING"})


class InspectorReviewError(ValueError):
    pass


class InspectorReview:
    def __init__(self, *, reviewer: str, automated_decision: Any, inspector_decision: str, reason: str | None = None, field_confirmations: dict[str, Any] | None = None, reviewed_at: datetime | None = None) -> None:
        reviewer_id = "" if reviewer is None else str(reviewer).strip()
        if not reviewer_id:
            raise InspectorReviewError("reviewer name or ID is required")
        decision = str(inspector_decision or "").strip().upper()
        if decision not in VALID_INSPECTOR_DECISIONS:
            raise InspectorReviewError("inspector_decision must be CONFIRMED, OVERRIDDEN, or PENDING")
        reason = reason.strip() if isinstance(reason, str) else reason
        if decision in {"CONFIRMED", "OVERRIDDEN"} and not reason:
            raise InspectorReviewError("reviewer reason is required")
        if field_confirmations is not None and not isinstance(field_confirmations, dict):
            raise InspectorReviewError("field_confirmations must be a dictionary")
        self.reviewer = reviewer_id
        self.reviewed_at = reviewed_at or datetime.now(timezone.utc)
        self.automated_decision = deepcopy(automated_decision)
        self.inspector_decision = decision
        self.reason = reason or None
        self.field_confirmations = deepcopy(field_confirmations) if field_confirmations else None

    def to_dict(self) -> dict[str, Any]:
        return {"reviewer": self.reviewer, "reviewed_at": self.reviewed_at.isoformat(), "automated_decision": deepcopy(self.automated_decision), "inspector_decision": self.inspector_decision, "reason": self.reason, "field_confirmations": deepcopy(self.field_confirmations)}


def create_inspector_review(**kwargs: Any) -> InspectorReview:
    return InspectorReview(**kwargs)
