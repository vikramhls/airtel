"""Simulated checkout rails: e-sign (Aadhaar-OTP style), AutoPay mandate, DigiLocker fetch.

Nothing here talks to a real provider. Every response says "simulated" so the UI can
label it, and the shapes mirror what a real integration would return.
"""
from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache

from app import config, db
from app.services import quotes, sessions
from app.utils import gstin as gstin_util
from app.utils.mask import mask_gstin

DEMO_OTP = "123456"


def _state(quote_id: str) -> dict:
    return db.get_state(f"checkout:{quote_id}") or {}


def _save(quote_id: str, value: dict) -> None:
    db.set_state(f"checkout:{quote_id}", value)


def esign(session_id: str, quote_id: str, otp: str) -> dict:
    quote = quotes.get(quote_id)
    if not quote or quote["session_id"] != session_id:
        raise KeyError("quote")
    if otp.strip() != DEMO_OTP:
        raise ValueError("bad_otp")
    summary = {"quote_id": quote_id, "monthly": quote["total_monthly"], "setup": quote["total_setup"],
               "contract_months": quote["contract_months"], "items": [i["product_id"] for i in quote["items"]]}
    digest = hashlib.sha256(json.dumps(summary, sort_keys=True).encode()).hexdigest()[:16]
    record = {"signed": True, "signed_on": config.REFERENCE_DATE.isoformat(), "document_hash": digest,
              "method": "Aadhaar OTP e-sign", "simulated": True, "agreement": summary}
    state = _state(quote_id)
    state["esign"] = record
    _save(quote_id, state)
    db.execute("INSERT INTO audit_log(at, actor, action, session_id, detail_masked) VALUES(?,?,?,?,?)",
               (db.now(), "owner", "agreement_esigned", session_id, f"quote={quote_id} hash={digest}"))
    return record


def mandate(session_id: str, quote_id: str, method: str, handle: str | None) -> dict:
    quote = quotes.get(quote_id)
    if not quote or quote["session_id"] != session_id:
        raise KeyError("quote")
    if method not in ("upi_autopay", "nach"):
        raise ValueError("bad_method")
    if method == "upi_autopay" and not re.fullmatch(r"[\w.\-]{2,64}@[a-zA-Z]{2,32}", (handle or "").strip()):
        raise ValueError("bad_upi")
    masked = None
    if handle:
        name, _, bank = handle.strip().partition("@")
        masked = (name[:2] + "•" * max(len(name) - 2, 1) + "@" + bank) if bank else "••••" + handle.strip()[-4:]
    record = {"mandate_id": "MDT-" + hashlib.sha256(f"{quote_id}{method}".encode()).hexdigest()[:8].upper(),
              "method": "UPI AutoPay" if method == "upi_autopay" else "e-NACH (bank account)",
              "handle_masked": masked, "max_amount": quote["total_monthly"] + quote["total_setup"],
              "frequency": "monthly", "status": "approved", "simulated": True}
    state = _state(quote_id)
    state["mandate"] = record
    _save(quote_id, state)
    db.execute("INSERT INTO audit_log(at, actor, action, session_id, detail_masked) VALUES(?,?,?,?,?)",
               (db.now(), "owner", "mandate_approved", session_id, f"quote={quote_id} {record['mandate_id']}"))
    return record


def status(quote_id: str) -> dict:
    state = _state(quote_id)
    return {"esign": state.get("esign"), "mandate": state.get("mandate"),
            "complete": bool(state.get("esign") and state.get("mandate"))}


@lru_cache(maxsize=1)
def _applicants_by_gstin() -> dict[str, str]:
    """GSTIN -> specimen applicant (K01..K12), read from the OCR cache of the data pack."""
    path = config.REPORTS_DIR / "kyc_extractions.json"
    if not path.exists():
        return {}
    from app.dataio import gstin_frame

    out: dict[str, str] = {}
    names: dict[str, str] = {}   # business name on any document -> applicant
    for key, value in json.loads(path.read_text()).items():
        applicant, fields = key.split("_")[0], value["fields"]
        if "_gst_certificate" in key and fields.get("gstin"):
            out[gstin_util.normalise(fields["gstin"])] = applicant
        for field in ("enterprise_name", "for_business", "billed_to", "trade_name"):
            if fields.get(field):
                names.setdefault(fields[field].strip().lower(), applicant)
    # A blurred GST certificate can't be read, so also match the name on the other documents.
    for row in gstin_frame().itertuples():
        for name in (row.trade_name, row.legal_name):
            applicant = names.get(str(name).strip().lower())
            if applicant and row.gstin not in out:
                out[row.gstin] = applicant
    return out


def digilocker_fetch(session_id: str, otp: str, applicant: str | None = None) -> dict:
    """Simulated DigiLocker pull: documents issued to this business's GSTIN."""
    from app.services.kyc import service as kyc_service

    if otp.strip() != DEMO_OTP:
        raise ValueError("bad_otp")
    profile = sessions.load_profile(session_id)
    found = _applicants_by_gstin().get(gstin_util.normalise(profile.gstin or "")) if profile.gstin else None
    source = found or applicant
    if not source:
        raise LookupError("no_documents")
    fetched, last = [], None
    for doc_type in ("gst", "udyam", "address", "signatory_id"):
        try:
            last = kyc_service.upload_sample(session_id, doc_type, source)
            fetched.append(doc_type)
        except FileNotFoundError:
            continue
    return {"fetched": fetched, "missing": [d for d in ("gst", "udyam", "address", "signatory_id") if d not in fetched],
            "issued_to": mask_gstin(profile.gstin) if profile.gstin else None, "simulated": True,
            "readiness": (last or {}).get("readiness")}
