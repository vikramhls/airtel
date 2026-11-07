"""Simulated e-sign, AutoPay mandate and DigiLocker endpoints (clearly labelled in the UI)."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.routers.common import problem, require_session
from app.services import checkout, consent

router = APIRouter(tags=["checkout"])


class EsignIn(BaseModel):
    session_id: str
    quote_id: str
    otp: str


class MandateIn(BaseModel):
    session_id: str
    quote_id: str
    method: str = "upi_autopay"
    handle: str | None = None


class DigiLockerIn(BaseModel):
    session_id: str
    otp: str
    applicant: str | None = None


OTP_HINT = "Simulated: the OTP is 123456."


@router.post("/checkout/esign")
def esign(body: EsignIn):
    require_session(body.session_id)
    try:
        return checkout.esign(body.session_id, body.quote_id, body.otp)
    except KeyError:
        raise problem(404, "QUOTE_NOT_FOUND", "Quote not found.", "Build a quote first.")
    except ValueError:
        raise problem(422, "BAD_OTP", "That OTP didn't match.", OTP_HINT)


@router.post("/checkout/mandate")
def mandate(body: MandateIn):
    require_session(body.session_id)
    try:
        return checkout.mandate(body.session_id, body.quote_id, body.method, body.handle)
    except KeyError:
        raise problem(404, "QUOTE_NOT_FOUND", "Quote not found.", "Build a quote first.")
    except ValueError as exc:
        hint = {"bad_upi": "Enter a UPI ID like name@bank.", "bad_method": "Choose UPI AutoPay or e-NACH."}
        raise problem(422, str(exc).upper(), "We couldn't set up the mandate.", hint.get(str(exc)))


@router.get("/checkout/{quote_id}")
def status(quote_id: str):
    return checkout.status(quote_id)


@router.post("/kyc/digilocker")
def digilocker(body: DigiLockerIn):
    require_session(body.session_id)
    if not consent.require(body.session_id):
        raise problem(403, "CONSENT_REQUIRED", "We need your consent before we fetch any document.",
                      "Read the consent notice and tap Agree.")
    try:
        return checkout.digilocker_fetch(body.session_id, body.otp, body.applicant)
    except ValueError:
        raise problem(422, "BAD_OTP", "That OTP didn't match.", OTP_HINT)
    except LookupError:
        raise problem(404, "NO_DIGILOCKER_DOCS", "No documents found in DigiLocker for this business.",
                      "Start with your GSTIN on the home screen so we know whose documents to fetch, or upload photos instead.")
