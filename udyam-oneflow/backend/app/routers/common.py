"""Shared helpers for routers: typed problem errors and session/profile lookup."""
from __future__ import annotations

from fastapi import HTTPException

from app.dataio import city_tier
from app.schemas import BusinessProfile
from app.services import sessions
from app.services.segmenter import infer_segment


def problem(status: int, code: str, message: str, fix_hint: str | None = None) -> HTTPException:
    """All errors are {code, message, fix_hint} (AGENTS.md); the UI shows fix_hint."""
    return HTTPException(status_code=status, detail={"code": code, "message": message, "fix_hint": fix_hint})


def require_session(session_id: str) -> dict:
    session = sessions.get(session_id)
    if not session:
        raise problem(404, "SESSION_NOT_FOUND", "That session does not exist.", "Start again from the home screen.")
    return session


def resolved_profile(session_id: str) -> BusinessProfile:
    """Stored profile with segment + city tier filled in for the engine."""
    profile = sessions.load_profile(session_id)
    return profile.model_copy(update={
        "segment": profile.segment or infer_segment(profile.business_type, profile.sites) or "micro",
        "city_tier": profile.city_tier or city_tier(profile.city),
    })
