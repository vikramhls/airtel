from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.dataio import city_tier
from app.routers.common import problem, require_session, resolved_profile
from app.schemas import BusinessProfile
from app.services import advisor, bundler, propensity, sessions

router = APIRouter(tags=["advisor"])


class SessionIn(BaseModel):
    lang: str = "en"
    partner_token: str | None = None


class MessageIn(BaseModel):
    session_id: str
    text: str
    lang: str | None = None


class GstinFirstIn(BaseModel):
    session_id: str
    gstin: str


@router.post("/session")
def create_session(body: SessionIn):
    lang = body.lang if body.lang in ("en", "hi", "ta") else "en"
    out = sessions.create(lang, body.partner_token)
    return {**out, **advisor.greeting(lang)}


@router.post("/advisor/message")
def message(body: MessageIn):
    require_session(body.session_id)
    text = body.text.strip()[:600]
    if not text:
        raise problem(422, "EMPTY_MESSAGE", "Message is empty.", "Type a message or tap a chip.")
    return advisor.handle_message(body.session_id, text, body.lang)


@router.get("/session/{session_id}/profile")
def get_profile(session_id: str):
    require_session(session_id)
    return sessions.load_profile(session_id).model_dump()


@router.patch("/session/{session_id}/profile")
def patch_profile(session_id: str, patch: dict):
    """Owner edits a profile chip; the engine recomputes the plan."""
    require_session(session_id)
    profile = sessions.load_profile(session_id)
    allowed = set(BusinessProfile.model_fields) - {"gstin_status", "segment", "city_tier", "gstin"}
    update = {k: v for k, v in patch.items() if k in allowed}
    if update.get("has_gstin") is False:
        update.update({"gstin": None, "gstin_status": None})
    try:
        profile = BusinessProfile(**{**profile.model_dump(), **update, "segment": None})
    except Exception as exc:  # pydantic validation
        raise problem(422, "BAD_PROFILE", "Some of those values are not valid.", str(exc)[:200])
    profile = profile.model_copy(update={"city_tier": city_tier(profile.city)})
    sessions.save_profile(session_id, profile)
    rec = bundler.recommend(profile, patch.get("term_months"))
    return {"profile": profile.model_dump(), "recommendation": rec.model_dump()}


@router.post("/gstin-first")
def gstin_first(body: GstinFirstIn):
    require_session(body.session_id)
    profile = sessions.load_profile(body.session_id)
    profile, result = advisor.apply_gstin(profile, body.gstin)
    if not result["ok"]:
        status = 404 if result["code"] == "GSTIN_NOT_FOUND" else 422
        raise problem(status, result["code"], result["message"], result["fix_hint"])
    sessions.save_profile(body.session_id, profile)
    state = advisor._state(body.session_id)
    missing = advisor.missing_slots(profile, state)
    record = dict(result["record"])
    warning = None
    if record["status"] != "Active":
        warning = (f"Your GSTIN shows as {record['status']}. You can still buy products that don't need a GSTIN; "
                   "a partner can help you reactivate it.")
    record.pop("gstin", None)   # only the masked form leaves the server
    slot = missing[0] if missing else None
    lang = (require_session(body.session_id).get("lang") or "en")
    state["last_slot"] = slot
    advisor._save_state(body.session_id, state)
    return {"profile": {**profile.model_dump(), "gstin": record["gstin_masked"]}, "registry": record,
            "missing_slots": missing, "warning": warning, "next_slot": slot,
            "question": advisor.Q[slot][lang] if slot else None, "chips": advisor.chips_for(slot, lang) if slot else []}


@router.post("/recommend")
def recommend(body: dict):
    """Either {session_id, term_months?} or {profile: {...}, term_months?}."""
    term = body.get("term_months")
    if body.get("session_id"):
        require_session(body["session_id"])
        profile = sessions.load_profile(body["session_id"])
    else:
        profile = BusinessProfile(**(body.get("profile") or {}))
    return bundler.recommend(profile, term).model_dump()


@router.get("/session/{session_id}/score")
def session_score(session_id: str):
    """Live propensity for this advisor session (trained model), shown in the cockpit."""
    session = require_session(session_id)
    source = "Channel partner" if session.get("partner_id") else "Website form"
    return propensity.score_profile(resolved_profile(session_id), source, session.get("lang") or "en")
