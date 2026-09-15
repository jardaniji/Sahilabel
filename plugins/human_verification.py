"""Validation and read-only projection helpers for human rule verification."""

from __future__ import annotations

from copy import deepcopy


VALID_HUMAN_STATUSES = {"PASS", "FAIL", "UNABLE_TO_VERIFY"}


def validate_human_status(status: str) -> str:
    if status not in VALID_HUMAN_STATUSES:
        raise ValueError("human_status must be PASS, FAIL, or UNABLE_TO_VERIFY")
    return status


def materialize_report(report: dict, human_verifications: dict[str, dict] | None = None) -> dict:
    """Project final statuses without mutating the original automated report."""
    view = deepcopy(report)
    verifications = human_verifications or {}
    for rule in view.get("rules", []):
        automated_status = rule.get("automated_status", rule.get("status"))
        verification = verifications.get(rule.get("rule_id"))
        human_status = verification.get("human_status") if verification else None
        rule["automated_status"] = automated_status
        rule["human_status"] = human_status
        rule["final_status"] = human_status or automated_status
        rule["status"] = automated_status
        if verification:
            rule["human_verification"] = deepcopy(verification)

    final_statuses = [r.get("final_status") for r in view.get("rules", [])]
    if "FAIL" in final_statuses:
        final_overall_status = "FAIL"
    elif "REVIEW" in final_statuses or "UNABLE_TO_VERIFY" in final_statuses:
        final_overall_status = "REVIEW"
    else:
        final_overall_status = "PASS"
    view["final_overall_status"] = final_overall_status
    view["final_overall_compliant"] = final_overall_status == "PASS"
    return view
