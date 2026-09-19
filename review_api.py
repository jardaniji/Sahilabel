"""HTTP API for persisted inspector reviews."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from auth import require_role
from inspector_review import create_inspector_review
from review_store import final_decision, list_reviews, save_review

review_router = APIRouter(prefix="/api/v1/inspections", tags=["inspector-review"])


class ReviewRequest(BaseModel):
    automated_decision: Any
    inspector_decision: str = Field(..., pattern="^(CONFIRMED|OVERRIDDEN|PENDING)$")
    reason: str | None = None
    field_confirmations: dict[str, Any] | None = None


@review_router.post("/{inspection_id}/reviews", status_code=status.HTTP_201_CREATED)
def create_review(inspection_id: str, request: ReviewRequest, user: dict[str, Any] = Depends(require_role("admin", "inspector"))) -> dict[str, Any]:
    try:
        review = create_inspector_review(
            reviewer=user["username"], automated_decision=request.automated_decision,
            inspector_decision=request.inspector_decision, reason=request.reason,
            field_confirmations=request.field_confirmations,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return save_review(inspection_id, review)


@review_router.get("/{inspection_id}/reviews")
def get_reviews(inspection_id: str, user: dict[str, Any] = Depends(require_role("admin", "inspector", "viewer"))) -> list[dict[str, Any]]:
    return list_reviews(inspection_id)


@review_router.get("/{inspection_id}/final-decision")
def get_final_decision(inspection_id: str, user: dict[str, Any] = Depends(require_role("admin", "inspector", "viewer"))) -> dict[str, Any]:
    result = final_decision(inspection_id)
    if result is None:
        raise HTTPException(status_code=404, detail="No review exists for this inspection")
    return result
