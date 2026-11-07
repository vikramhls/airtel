"""Readiness score: checks passed / checks applicable, plus the next action."""
from __future__ import annotations

from app.services.kyc.validate import NEXT_ACTION_ORDER, summary as summarise


def priority(code: str) -> int:
    return NEXT_ACTION_ORDER.index(code) if code in NEXT_ACTION_ORDER else len(NEXT_ACTION_ORDER)


def readiness(checks: list[dict], missing_docs: list[str] | None = None) -> dict:
    total = len(checks)
    passed = sum(1 for c in checks if c["status"] == "pass")
    failures = [c for c in checks if c["status"] == "fail"]
    blockers = [c for c in failures if c["severity"] == "blocker"]
    warnings = [c for c in failures if c["severity"] == "warning"]

    ordered = sorted(failures, key=lambda c: (0 if c["severity"] == "blocker" else 1, priority(c["code"])))
    next_check = ordered[0] if ordered else None

    if not failures:
        state = "green"
    elif blockers:
        state = "red"
    else:
        state = "amber"

    return {
        "score": {"passed": passed, "total": total, "ratio": round(passed / total, 3) if total else 0.0},
        "state": state,
        "blockers": [c["code"] for c in blockers],
        "warnings": [c["code"] for c in warnings],
        "next_action": (
            {
                "code": next_check["code"],
                "label": next_check.get("fix_hint") or next_check["detail"],
                "severity": next_check["severity"],
            }
            if next_check else None
        ),
        "missing_docs": missing_docs or [],
        "summary": summarise(checks, {}),
        "ready_for_order": not blockers,
    }
