from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel

from app.routers.common import problem, require_session
from app.services import consent, registry
from app.services.kyc import service as kyc_service
from app.services.kyc.validate import DOC_TYPES

router = APIRouter(tags=["kyc"])


class ConsentIn(BaseModel):
    session_id: str
    purpose: str = consent.PURPOSE_KYC
    accepted: bool = True


class SampleIn(BaseModel):
    session_id: str
    doc_type: str
    applicant: str = "K03"


def _gate(session_id: str) -> None:
    require_session(session_id)
    if not consent.require(session_id):
        raise problem(403, "CONSENT_REQUIRED", "We need your consent before we read any document.",
                      "Read the consent notice and tap Agree, or skip KYC for now.")


@router.get("/consent/text")
def consent_text():
    return consent.text()


@router.post("/consent")
def give_consent(body: ConsentIn):
    require_session(body.session_id)
    if body.purpose != consent.PURPOSE_KYC:
        raise problem(422, "BAD_PURPOSE", "Unknown consent purpose.", None)
    consent_id = consent.grant(body.session_id, body.purpose, body.accepted)
    return {"consent_id": consent_id, "accepted": body.accepted}


@router.post("/consent/withdraw")
def withdraw(body: ConsentIn):
    require_session(body.session_id)
    deleted = kyc_service.delete_documents(body.session_id)
    consent.withdraw(body.session_id, body.purpose)
    return {"withdrawn": True, "documents_deleted": deleted}


@router.post("/kyc/upload")
async def upload(session_id: str = Form(...), doc_type: str = Form(...), file: UploadFile = File(...)):
    _gate(session_id)
    if doc_type not in DOC_TYPES:
        raise problem(422, "BAD_DOC_TYPE", "Unknown document type.", "Use gst, udyam, address or signatory_id.")
    content = await file.read()
    try:
        return kyc_service.upload(session_id, doc_type, file.filename or "upload.png", content)
    except ValueError as exc:
        hint = {"bad_file_type": "Upload a photo or scan (JPG or PNG). For a PDF, take a screenshot of the page.",
                "unreadable_image": "We couldn't open that file as an image. Take a new photo and try again.",
                "file_too_large": "Files must be under 5 MB. Take the photo at a lower resolution."}.get(str(exc))
        raise problem(422, str(exc).upper(), "We could not use that file.", hint)


@router.post("/kyc/sample")
def upload_sample(body: SampleIn):
    """Demo helper: 'use sample document' (specimen pack K01-K12), same pipeline as a real upload."""
    _gate(body.session_id)
    if body.doc_type not in DOC_TYPES:
        raise problem(422, "BAD_DOC_TYPE", "Unknown document type.", None)
    try:
        return kyc_service.upload_sample(body.session_id, body.doc_type, body.applicant)
    except FileNotFoundError as exc:
        raise problem(404, "SAMPLE_MISSING", str(exc), "This applicant has no such document in the pack.")


@router.patch("/kyc/extraction/{document_id}")
def correct(document_id: str, fields: dict):
    report = kyc_service.correct_fields(document_id, fields)
    if not report:
        raise problem(404, "DOCUMENT_NOT_FOUND", "Document not found.", "Upload the document again.")
    return report


@router.get("/kyc/{session_id}/report")
def report(session_id: str):
    require_session(session_id)
    if not consent.require(session_id):
        return {"session_id": session_id, "consent": False, "documents": [], "checks": [],
                "score": {"passed": 0, "total": 0, "ratio": 0}, "state": "none", "next_action": None,
                "missing_docs": DOC_TYPES, "ready_for_order": False}
    return kyc_service.report(session_id)


@router.delete("/kyc/{session_id}/documents")
def delete_docs(session_id: str):
    require_session(session_id)
    return {"deleted": kyc_service.delete_documents(session_id)}


@router.get("/gstin/{number}")
def gstin_lookup(number: str):
    record, prob = registry.find_gstin(number)
    if prob:
        raise problem(404 if prob["code"] == "GSTIN_NOT_FOUND" else 422, prob["code"], prob["message"], prob["fix_hint"])
    out = registry.public_gstin(record)
    out.pop("gstin", None)
    return out


@router.get("/udyam/{number}")
def udyam_lookup(number: str):
    record, prob = registry.find_udyam(number)
    if prob:
        raise problem(404 if prob["code"] == "UDYAM_NOT_FOUND" else 422, prob["code"], prob["message"], prob["fix_hint"])
    out = registry.public_udyam(record)
    out.pop("udyam_number", None)
    return out
