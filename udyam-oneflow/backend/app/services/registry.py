"""Mock registry lookups (CSV-backed). Never calls a government API."""
from __future__ import annotations

from app.dataio import gstin_lookup, udyam_lookup
from app.utils import gstin as gstin_util
from app.utils.mask import mask_gstin, mask_udyam

UDYAM_RE = r"^UDYAM-[A-Z]{2}-00-\d{7}$"

GSTIN_NOT_FOUND = {
    "code": "GSTIN_NOT_FOUND",
    "message": "That GSTIN is not in the mock registry.",
    "fix_hint": "Check the number on your GST certificate, or upload the certificate and we will read it for you.",
}
GSTIN_INVALID = {
    "code": "GSTIN_INVALID",
    "message": "That does not look like a valid GSTIN.",
    "fix_hint": "A GSTIN is 15 characters. Check the digits and letters and try again.",
}
UDYAM_NOT_FOUND = {
    "code": "UDYAM_NOT_FOUND",
    "message": "That Udyam number is not in the mock registry.",
    "fix_hint": "Check the number on your Udyam certificate, or upload it instead.",
}
UDYAM_INVALID = {
    "code": "UDYAM_INVALID",
    "message": "That does not look like a valid Udyam number.",
    "fix_hint": "Udyam numbers look like UDYAM-KL-00-3078801.",
}


def find_gstin(number: str) -> tuple[dict | None, dict | None]:
    """Returns (record, problem). Format/checksum errors are 422, unknown is 404."""
    ok, err = gstin_util.validate(number)
    if err == "GSTIN_FORMAT":
        return None, GSTIN_INVALID
    if err == "GSTIN_CHECKSUM":
        return None, {
            "code": "GSTIN_CHECKSUM",
            "message": "The last character of this GSTIN does not match its checksum.",
            "fix_hint": "One digit is probably wrong. Check the number on the certificate.",
        }
    record = gstin_lookup().get(gstin_util.normalise(number))
    if not record:
        return None, GSTIN_NOT_FOUND
    return record, None


def public_gstin(record: dict) -> dict:
    out = dict(record)
    out["gstin_masked"] = mask_gstin(record.get("gstin"))
    out["checksum_ok"] = gstin_util.checksum_ok(record.get("gstin", ""))
    return out


def find_udyam(number: str) -> tuple[dict | None, dict | None]:
    import re

    value = (number or "").strip().upper()
    if not re.match(UDYAM_RE, value):
        return None, UDYAM_INVALID
    record = udyam_lookup().get(value)
    if not record:
        return None, UDYAM_NOT_FOUND
    return record, None


def public_udyam(record: dict) -> dict:
    out = dict(record)
    out["udyam_masked"] = mask_udyam(record.get("udyam_number"))
    return out
