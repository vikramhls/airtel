"""KYC service: upload -> OCR -> extract -> validate -> readiness, all consent-gated."""
from __future__ import annotations

import shutil
import uuid
from datetime import timedelta
from pathlib import Path

from app import config, db
from app.services import consent, registry
from app.services.kyc import extract as extract_service
from app.services.kyc import cache as kyc_cache
from app.services.kyc import ocr, score, validate
from app.utils.mask import mask_gstin, mask_id, mask_udyam

UPLOAD_DIR = config.BACKEND_DIR / "uploads"
MAX_BYTES = 5 * 1024 * 1024
ALLOWED = {".png", ".jpg", ".jpeg", ".webp"}   # photos/scans; PDFs are not read yet
DOC_LABEL = validate.DOC_LABEL


def _mask_field(key: str, value: str) -> str:
    if not value:
        return value
    if key == "gstin":
        return mask_gstin(value) or value
    if key == "udyam_number":
        return mask_udyam(value) or value
    if key == "id_no":
        return mask_id(value) or value
    return value


def _display(doc_type: str, fields: dict, confidence: dict) -> dict:
    labels = extract_service.field_labels(doc_type)
    out = {}
    for key, value in fields.items():
        out[key] = {
            "value": value,
            "masked_value": _mask_field(key, value),
            "confidence": confidence.get(key, 0.0),
            "label": labels.get(key, key),
        }
    return out


def session_documents(session_id: str) -> list[dict]:
    rows = db.query(
        "SELECT * FROM documents WHERE session_id = ? AND deleted_at IS NULL ORDER BY uploaded_at DESC",
        (session_id,),
    )
    out = []
    for row in rows:
        extraction = db.one("SELECT * FROM kyc_extractions WHERE document_id = ?", (row["id"],))
        import json

        fields = json.loads(extraction["fields_json"]) if extraction else {}
        confidence = json.loads(extraction["confidence_json"]) if extraction else {}
        quality = json.loads(extraction["quality_json"] or "{}") if extraction else {}
        out.append({**row, "fields": fields, "confidence": confidence, "quality": quality})
    return out


def latest_by_type(session_id: str) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for row in session_documents(session_id):
        if row["doc_type"] not in latest:
            latest[row["doc_type"]] = row
    return latest


def run_checks(session_id: str) -> dict:
    docs = {doc_type: {"fields": row["fields"], "confidence": row["confidence"], "quality": row["quality"]}
            for doc_type, row in latest_by_type(session_id).items()}
    from app.services import sessions   # local import: sessions imports nothing from kyc

    profile = sessions.load_profile(session_id).model_dump()
    checks = validate.validate(docs, consent_recorded=consent.require(session_id), profile=profile)
    missing = [doc for doc in validate.DOC_TYPES if doc not in docs]
    readiness = score.readiness(checks, missing)
    db.execute("DELETE FROM kyc_checks WHERE session_id = ?", (session_id,))
    import json

    for check in checks:
        db.insert(
            "INSERT INTO kyc_checks(session_id, check_code, status, detail, evidence_json, created_at) "
            "VALUES(?,?,?,?,?,?)",
            (session_id, check["code"], check["status"], check["detail"],
             json.dumps({"severity": check["severity"], "fix_hint": check["fix_hint"]}), db.now()),
        )
    db.set_state(f"kyc_report:{session_id}", {"checks": checks, "readiness": readiness})
    return {"checks": checks, **readiness}


def upload(session_id: str, doc_type: str, filename: str, content: bytes) -> dict:
    """Caller must verify consent first (403 otherwise)."""
    if doc_type not in validate.DOC_TYPES:
        raise ValueError("bad_doc_type")
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED:
        raise ValueError("bad_file_type")
    if len(content) > MAX_BYTES:
        raise ValueError("file_too_large")
    try:   # reject files that are not a real image before storing them
        from io import BytesIO

        from PIL import Image

        Image.open(BytesIO(content)).verify()
    except Exception:
        raise ValueError("unreadable_image")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    doc_id = f"DOC-{uuid.uuid4().hex[:10].upper()}"
    stored = UPLOAD_DIR / f"{doc_id}{suffix}"
    stored.write_bytes(content)

    cached = kyc_cache.lookup(Path(filename).name, content)
    if cached:
        extraction = {
            "engine": f"{cached['engine']} (cached specimen)",
            "fields": dict(cached["fields"]),
            "confidence": dict(cached["confidence"]),
            "low_confidence": [k for k, v in cached["confidence"].items() if v and v < 0.6],
            "quality": cached.get("quality", {}),
        }
    else:
        extraction = extract_service.extract(content, doc_type)
    fields = extraction["fields"]
    confidence = extraction["confidence"]
    delete_after = (config.REFERENCE_DATE + timedelta(days=config.DOC_RETENTION_DAYS)).isoformat()

    db.execute("DELETE FROM documents WHERE session_id = ? AND doc_type = ? AND deleted_at IS NULL",
               (session_id, doc_type))
    db.execute(
        "INSERT INTO documents(id, session_id, doc_type, filename, stored_path, uploaded_at, delete_after) "
        "VALUES(?,?,?,?,?,?,?)",
        (doc_id, session_id, doc_type, filename, str(stored), db.now(), delete_after),
    )
    import json

    db.execute(
        "INSERT INTO kyc_extractions(document_id, fields_json, confidence_json, quality_json) VALUES(?,?,?,?)",
        (doc_id, json.dumps(fields), json.dumps(confidence), json.dumps(extraction.get("quality", {}))),
    )
    db.execute(
        "INSERT INTO audit_log(at, actor, action, session_id, detail_masked) VALUES(?,?,?,?,?)",
        (db.now(), "owner", f"kyc_upload_{doc_type}", session_id, f"doc={doc_id}"),
    )
    report = run_checks(session_id)
    return {
        "document_id": doc_id,
        "doc_type": doc_type,
        "engine": extraction["engine"],
        "extracted": _display(doc_type, fields, confidence),
        "low_confidence": extraction["low_confidence"],
        "quality": extraction.get("quality", {}),
        "delete_after": delete_after,
        "checks": report["checks"],
        "score": report["score"],
        "state": report["state"],
        "readiness": report,
    }


def upload_sample(session_id: str, doc_type: str, applicant: str = "K01") -> dict:
    suffix = validate.DOC_CHECK[doc_type]
    name = {
        "gst": "gst_certificate",
        "udyam": "udyam_certificate",
        "address": "address_proof",
        "signatory_id": "signatory_id",
    }[doc_type]
    path = config.DOCS_DIR / f"{applicant.upper()}_{name}.png"
    if not path.exists():
        raise FileNotFoundError(f"{applicant} has no {DOC_LABEL[doc_type]} image in the pack")
    return upload(session_id, doc_type, path.name, path.read_bytes())


def report(session_id: str) -> dict:
    cached = db.get_state(f"kyc_report:{session_id}")
    if not cached:
        cached = run_checks(session_id)
    docs = []
    for doc_type, row in latest_by_type(session_id).items():
        docs.append({
            "document_id": row["id"],
            "doc_type": doc_type,
            "filename": row["filename"],
            "uploaded_at": row["uploaded_at"],
            "delete_after": row["delete_after"],
            "extracted": _display(doc_type, row["fields"], row["confidence"]),
            "low_confidence": [k for k, v in row["confidence"].items() if v and v < 0.6],
            "quality": row["quality"],
        })
    readiness = cached["readiness"]
    return {
        "session_id": session_id,
        "consent": consent.active(session_id) is not None,
        "documents": docs,
        "checks": cached["checks"],
        **readiness,
    }


def correct_fields(document_id: str, fields: dict) -> dict:
    row = db.one("SELECT * FROM documents WHERE id = ? AND deleted_at IS NULL", (document_id,))
    if not row:
        return {}
    import json

    extraction = db.one("SELECT * FROM kyc_extractions WHERE document_id = ?", (document_id,))
    current = json.loads(extraction["fields_json"]) if extraction else {}
    allowed = set(extract_service.field_labels(row["doc_type"]))
    for key, value in fields.items():
        if key in allowed:
            current[key] = str(value).strip()
    db.execute("UPDATE kyc_extractions SET fields_json = ? WHERE document_id = ?",
               (json.dumps(current), document_id))
    # confidence is the owner's now - it was confirmed by a human
    confidence = {k: 1.0 for k in current}
    db.execute("UPDATE kyc_extractions SET confidence_json = ?, quality_json = ? WHERE document_id = ?",
               (json.dumps(confidence), json.dumps({"readable": True, "owner_confirmed": True}), document_id))
    db.execute(
        "INSERT INTO audit_log(at, actor, action, session_id, detail_masked) VALUES(?,?,?,?,?)",
        (db.now(), "owner", "kyc_field_corrected", row["session_id"], f"doc={document_id}"),
    )
    run_checks(row["session_id"])
    return report(row["session_id"])


def delete_documents(session_id: str) -> int:
    rows = session_documents(session_id)
    for row in rows:
        path = Path(row.get("stored_path") or "")
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass
    db.execute("UPDATE documents SET deleted_at = ? WHERE session_id = ? AND deleted_at IS NULL",
               (db.now(), session_id))
    db.execute("DELETE FROM kyc_checks WHERE session_id = ?", (session_id,))
    db.set_state(f"kyc_report:{session_id}", None)
    db.execute(
        "INSERT INTO audit_log(at, actor, action, session_id, detail_masked) VALUES(?,?,?,?,?)",
        (db.now(), "owner", "kyc_documents_deleted", session_id, f"count={len(rows)}"),
    )
    return len(rows)


def status() -> dict:
    return ocr.status()
