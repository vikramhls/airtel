"""Consent gate. No document is collected without a recorded purpose-scoped consent."""
from __future__ import annotations

import uuid

from app import db, config

PURPOSE_KYC = "kyc_verification"

CONSENT_TEXT = (
    "To verify your business, Accel Business will read your GST certificate, Udyam certificate, "
    "address proof and signatory ID that you upload. We use them only to check your details and set up "
    "your order. We keep the image for up to 7 days or until verification is done, whichever is first, "
    "then delete it. We store only the fields we need (names, numbers, addresses, dates). You can view, "
    "correct or delete your data, or withdraw consent, at any time in this app."
)


def grant(session_id: str, purpose: str = PURPOSE_KYC, accepted: bool = True) -> str | None:
    if not accepted:
        return None
    consent_id = f"CON-{uuid.uuid4().hex[:8].upper()}"
    db.execute(
        "INSERT INTO consents(id, session_id, purpose, text_version, granted_at) VALUES(?,?,?,?,?)",
        (consent_id, session_id, purpose, config.CONSENT_TEXT_VERSION, db.now()),
    )
    db.execute(
        "INSERT INTO audit_log(at, actor, action, session_id, detail_masked) VALUES(?,?,?,?,?)",
        (db.now(), "owner", "consent_granted", session_id, f"purpose={purpose} version={config.CONSENT_TEXT_VERSION}"),
    )
    return consent_id


def active(session_id: str, purpose: str = PURPOSE_KYC) -> dict | None:
    return db.one(
        "SELECT * FROM consents WHERE session_id = ? AND purpose = ? AND withdrawn_at IS NULL "
        "ORDER BY granted_at DESC LIMIT 1",
        (session_id, purpose),
    )


def withdraw(session_id: str, purpose: str = PURPOSE_KYC) -> int:
    db.execute(
        "UPDATE consents SET withdrawn_at = ? WHERE session_id = ? AND purpose = ? AND withdrawn_at IS NULL",
        (db.now(), session_id, purpose),
    )
    rows = db.query(
        "UPDATE documents SET deleted_at = ? WHERE session_id = ? AND deleted_at IS NULL RETURNING id",
        (db.now(), session_id),
    ) if False else None
    db.execute(
        "UPDATE documents SET deleted_at = ? WHERE session_id = ? AND deleted_at IS NULL",
        (db.now(), session_id),
    )
    db.execute("DELETE FROM kyc_checks WHERE session_id = ?", (session_id,))
    db.execute(
        "INSERT INTO audit_log(at, actor, action, session_id, detail_masked) VALUES(?,?,?,?,?)",
        (db.now(), "owner", "consent_withdrawn_documents_deleted", session_id, "purpose=" + purpose),
    )
    return 1


def require(session_id: str) -> bool:
    return active(session_id) is not None


def text() -> dict:
    return {
        "purpose": PURPOSE_KYC,
        "version": config.CONSENT_TEXT_VERSION,
        "text": CONSENT_TEXT,
        "retention_days": config.DOC_RETENTION_DAYS,
    }
