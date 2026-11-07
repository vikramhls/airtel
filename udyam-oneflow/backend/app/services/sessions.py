"""Sessions, stored business profiles and advisor handoffs."""
from __future__ import annotations

import json
import uuid

from app import db
from app.schemas import BusinessProfile
from app.utils.mask import mask_payload


def create(lang: str = "en", partner_token: str | None = None, source: str = "direct") -> dict:
    session_id = f"S-{uuid.uuid4().hex[:10].upper()}"
    partner_id = None
    if partner_token:
        link = db.one("SELECT * FROM partner_links WHERE token = ?", (partner_token,))
        if link:
            partner_id, source = link["partner_id"], "partner_link"
    db.execute("INSERT INTO sessions(id, created_at, lang, partner_id, source) VALUES(?,?,?,?,?)",
               (session_id, db.now(), lang, partner_id, source))
    save_profile(session_id, BusinessProfile())
    return {"session_id": session_id, "lang": lang, "partner_id": partner_id, "source": source}


def get(session_id: str) -> dict | None:
    return db.one("SELECT * FROM sessions WHERE id = ?", (session_id,))


def set_lang(session_id: str, lang: str) -> None:
    db.execute("UPDATE sessions SET lang = ? WHERE id = ?", (lang, session_id))


def load_profile(session_id: str) -> BusinessProfile:
    row = db.one("SELECT profile_json FROM business_profiles WHERE session_id = ?", (session_id,))
    return BusinessProfile(**json.loads(row["profile_json"])) if row else BusinessProfile()


def save_profile(session_id: str, profile: BusinessProfile) -> None:
    db.execute(
        "INSERT INTO business_profiles(session_id, profile_json, updated_at) VALUES(?,?,?) "
        "ON CONFLICT(session_id) DO UPDATE SET profile_json = excluded.profile_json, updated_at = excluded.updated_at",
        (session_id, profile.model_dump_json(), db.now()),
    )


def add_handoff(session_id: str, reason: str, context: dict) -> None:
    """Advisor -> human (docs/08 section 5). Context is masked before it is stored."""
    existing = db.one("SELECT id FROM handoffs WHERE session_id = ? AND reason = ? AND status = 'open'",
                      (session_id, reason))
    if existing:
        return
    db.execute("INSERT INTO handoffs(session_id, reason, context_json, created_at) VALUES(?,?,?,?)",
               (session_id, reason, json.dumps(mask_payload(context)), db.now()))


def handoffs(status: str = "open") -> list[dict]:
    rows = db.query("SELECT * FROM handoffs WHERE status = ? ORDER BY created_at DESC", (status,))
    return [{**r, "context": json.loads(r.pop("context_json"))} for r in rows]
