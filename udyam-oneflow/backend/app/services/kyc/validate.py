"""KYC validation checks (docs/06 section 3).

Each check returns a dict: code, status (pass|fail), severity (ok|blocker|warning),
detail (plain words) and fix_hint. Everything is derived from the extracted
fields + the mock registries + the reference date.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from app import config
from app.dataio import city_tiers
from app.services import registry
from app.utils import dates as date_utils
from app.utils import gstin as gstin_util
from app.utils.mask import mask_gstin, mask_id, mask_udyam

DOC_TYPES = ["gst", "udyam", "address", "signatory_id"]
DOC_LABEL = {
    "gst": "GST certificate",
    "udyam": "Udyam certificate",
    "address": "address proof",
    "signatory_id": "signatory ID",
}
DOC_CHECK = {
    "gst": "DOC_PRESENT_GST",
    "udyam": "DOC_PRESENT_UDYAM",
    "address": "DOC_PRESENT_ADDR",
    "signatory_id": "DOC_PRESENT_ID",
}

# Priority for "what should the owner do next" (docs/06 section 4).
NEXT_ACTION_ORDER = [
    "DOC_PRESENT_GST", "DOC_PRESENT_UDYAM", "DOC_PRESENT_ADDR", "DOC_PRESENT_ID",
    "DOC_QUALITY", "PROFILE_MATCH", "GSTIN_FORMAT", "GSTIN_CHECKSUM", "GSTIN_REGISTRY", "UDYAM_FORMAT",
    "ADDR_DATE_FRESH", "ID_NOT_EXPIRED", "ID_FORMAT",
    "GSTIN_ACTIVE", "UDYAM_REGISTRY", "GST_NAME_MATCH", "GST_ADDR_MATCH",
    "UDYAM_NAME_MATCH", "UDYAM_LOCATION", "ADDR_MATCHES_BUSINESS", "ID_NAME_BUSINESS",
]

STATE_NAMES = sorted(set(gstin_util.STATE_CODES.values()) | {
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa",
    "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala",
    "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland",
    "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
    "Uttar Pradesh", "Uttarakhand", "West Bengal", "Delhi", "Puducherry", "Chandigarh",
}, key=len, reverse=True)


def normalise(value: str | None) -> str:
    text = (value or "").lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def similarity(a: str | None, b: str | None) -> float:
    na, nb = normalise(a), normalise(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def best_similarity(left: list[str | None], right: list[str | None]) -> float:
    scores = [similarity(a, b) for a in left if a for b in right if b]
    return max(scores) if scores else 0.0


def state_in_text(text: str | None) -> str | None:
    low = (text or "").lower()
    for name in STATE_NAMES:
        if name.lower() in low:
            return name
    return None


def _check(code: str, ok: bool, detail: str, fix_hint: str | None = None,
           severity: str = "blocker") -> dict:
    return {
        "code": code,
        "status": "pass" if ok else "fail",
        "severity": "ok" if ok else severity,
        "detail": detail,
        "fix_hint": None if ok else (fix_hint or detail),
    }


def validate(docs: dict[str, dict], consent_recorded: bool = True, profile: dict | None = None) -> list[dict]:
    """docs: doc_type -> {'fields': {...}, 'confidence': {...}}; profile: the chat profile, if any."""
    checks: list[dict] = []
    fields = {doc: (info.get("fields") or {}) for doc, info in docs.items()}

    checks.append(_check(
        "CONSENT_RECORDED", consent_recorded,
        "Consent recorded for KYC verification." if consent_recorded else "Consent is required before documents are read.",
        "Review and accept the consent notice first.",
    ))

    for doc in DOC_TYPES:
        present = doc in docs and bool(fields.get(doc))
        checks.append(_check(
            DOC_CHECK[doc], present,
            f"{DOC_LABEL[doc].capitalize()} received." if present else f"{DOC_LABEL[doc].capitalize()} not uploaded.",
            f"Upload your {DOC_LABEL[doc]}.",
        ))

    unreadable = [doc for doc in DOC_TYPES
                  if doc in docs and (docs[doc].get("quality") or {}).get("readable") is False]
    if docs:
        checks.append(_check(
            "DOC_QUALITY", not unreadable,
            "All document images are sharp enough to read." if not unreadable
            else "Too blurry to read: " + ", ".join(DOC_LABEL[d] for d in unreadable) + ".",
            "Retake the photo of your " + " and ".join(DOC_LABEL[d] for d in unreadable)
            + " in good light, or type the details in yourself.",
        ))
    for doc in unreadable:
        fields[doc] = {}   # nothing trustworthy to check until it is re-uploaded

    gst = fields.get("gst", {})
    udyam = fields.get("udyam", {})
    addr = fields.get("address", {})
    ident = fields.get("signatory_id", {})

    gst_record = None
    gstin_value = gst.get("gstin")
    if gstin_value:
        ok_format = gstin_util.format_ok(gstin_value)
        checks.append(_check(
            "GSTIN_FORMAT", ok_format,
            f"GSTIN {mask_gstin(gstin_value)} has the right 15-character structure." if ok_format
            else "The GSTIN we read does not have a valid 15-character structure.",
            "GSTIN looks wrong: check the digits on your certificate.",
        ))
        ok_checksum = gstin_util.checksum_ok(gstin_value)
        checks.append(_check(
            "GSTIN_CHECKSUM", ok_checksum,
            "GSTIN checksum verified." if ok_checksum else "The GSTIN checksum does not match.",
            "One character is probably misread - check the GSTIN and correct it.",
        ))
        record, problem = registry.find_gstin(gstin_value)
        gst_record = record
        checks.append(_check(
            "GSTIN_REGISTRY", record is not None,
            f"Found {mask_gstin(gstin_value)} in the mock GST registry." if record
            else (problem or {}).get("message", "GSTIN not found in the registry."),
            (problem or {}).get("fix_hint", "Check the number or upload the latest certificate."),
        ))
        if record:
            status = record.get("status", "")
            active = status == "Active"
            checks.append(_check(
                "GSTIN_ACTIVE", active,
                f"GSTIN status is {status}." if active
                else f"Your GSTIN shows as {status}. You can still buy products that do not need a GSTIN.",
                "Reactivate on the GST portal - a partner can help. Until then we sell you non-GSTIN products.",
                severity="warning",
            ))
            name_score = best_similarity(
                [gst.get("legal_name"), gst.get("trade_name")],
                [record.get("legal_name"), record.get("trade_name")],
            )
            checks.append(_check(
                "GST_NAME_MATCH", name_score >= 0.9,
                f"Name on the certificate matches the registry ({name_score:.0%} similar)." if name_score >= 0.9
                else f"Name on the certificate differs from the registry ({name_score:.0%} similar).",
                "Name on certificate differs from the registry - check the spelling or update your GST details.",
                severity="warning",
            ))
            addr_score = similarity(gst.get("address"), record.get("principal_place_of_business"))
            checks.append(_check(
                "GST_ADDR_MATCH", addr_score >= 0.85,
                f"Address matches the registry ({addr_score:.0%})." if addr_score >= 0.85
                else f"Address differs from the registry ({addr_score:.0%}).",
                "Address differs - correct it or update the address on the GST portal.",
                severity="warning",
            ))
    else:
        if "gst" in docs and "gst" not in unreadable:
            checks.append(_check("GSTIN_FORMAT", False, "We could not read a GSTIN on the certificate.",
                                 "Check the GSTIN field, or type it in."))
            checks.append(_check("GSTIN_CHECKSUM", False, "No GSTIN to verify.",
                                 "Correct the GSTIN field."))
            checks.append(_check("GSTIN_REGISTRY", False, "No GSTIN to look up.",
                                 "Correct the GSTIN field."))

    udyam_number = udyam.get("udyam_number")
    if "udyam" in docs and "udyam" not in unreadable:
        ok_format = bool(re.match(r"^UDYAM-[A-Z]{2}-00-\d{7}$", (udyam_number or "").upper()))
        checks.append(_check(
            "UDYAM_FORMAT", ok_format,
            f"Udyam number {mask_udyam(udyam_number)} looks valid." if ok_format
            else "The Udyam number on the certificate is missing or invalid.",
            "Udyam number is missing or invalid - re-enter it from the certificate (UDYAM-XX-00-0000000).",
        ))
        if ok_format:
            record, problem = registry.find_udyam(udyam_number)
            checks.append(_check(
                "UDYAM_REGISTRY", record is not None,
                "Found in the mock Udyam registry." if record
                else (problem or {}).get("message", "Udyam number not found."),
                (problem or {}).get("fix_hint", "Check the number on your certificate."),
            ))
            if record:
                gst_names = [gst.get("legal_name"), gst.get("trade_name"),
                             (gst_record or {}).get("legal_name"), (gst_record or {}).get("trade_name")]
                name_score = best_similarity([udyam.get("enterprise_name"), record.get("enterprise_name")],
                                             gst_names + [record.get("enterprise_name")])
                checks.append(_check(
                    "UDYAM_NAME_MATCH", name_score >= 0.9,
                    f"Enterprise name matches your other documents ({name_score:.0%})." if name_score >= 0.9
                    else f"Enterprise name differs between Udyam and GST ({name_score:.0%}).",
                    "Name differs between Udyam and GST - correct the enterprise name.",
                    severity="warning",
                ))
                city_ok = similarity(udyam.get("city"), record.get("city")) >= 0.9
                state_ok = similarity(udyam.get("state"), record.get("state")) >= 0.9
                state_code = gstin_util.state_name(gstin_value or "")
                code_ok = (state_code is None) or (state_code == record.get("state"))
                checks.append(_check(
                    "UDYAM_LOCATION", city_ok and state_ok and code_ok,
                    "Udyam city and state match the registry and your GSTIN." if (city_ok and state_ok and code_ok)
                    else "Udyam city/state does not line up with the registry or your GSTIN.",
                    "City or state differs from your GSTIN - check the Udyam details.",
                    severity="warning",
                ))

    if addr:
        bill_date = date_utils.parse(addr.get("bill_date"))
        age = date_utils.age_days(bill_date)
        fresh = bill_date is not None and 0 <= (age or 0) <= config.ADDRESS_PROOF_MAX_AGE_DAYS
        if bill_date and age is not None and age < 0:
            detail = "The bill date is in the future."
            hint = "Check the bill date; it cannot be after today."
        elif fresh:
            detail = f"Bill is {age} days old (limit {config.ADDRESS_PROOF_MAX_AGE_DAYS})."
            hint = None
        else:
            detail = (f"Address proof is {age} days old (limit {config.ADDRESS_PROOF_MAX_AGE_DAYS})."
                      if age is not None else "We could not read the bill date.")
            hint = "Upload a newer electricity bill (under 90 days old)."
        checks.append(_check("ADDR_DATE_FRESH", fresh, detail, hint))

        gst_address = gst.get("address") or (gst_record or {}).get("principal_place_of_business")
        addr_score = similarity(addr.get("supply_address"), gst_address)
        name_score = best_similarity(
            [addr.get("billed_to")],
            [gst.get("trade_name"), gst.get("legal_name"),
             (gst_record or {}).get("trade_name"), (gst_record or {}).get("legal_name"),
             udyam.get("enterprise_name")],
        )
        if not gst_address:   # GST unreadable: judge the bill on the name alone
            addr_score = 1.0
        ok = addr_score >= 0.85 and name_score >= 0.8
        checks.append(_check(
            "ADDR_MATCHES_BUSINESS", ok,
            f"Bill address and name match your business ({addr_score:.0%}, {name_score:.0%})." if ok
            else f"Bill address/name differs from your GST details ({addr_score:.0%}, {name_score:.0%}).",
            "Bill address differs from your GST address - upload a bill for this address.",
            severity="warning",
        ))

    if ident:
        id_no = (ident.get("id_no") or "").upper()
        ok_format = bool(re.match(r"^SYN-ID-\d{6}$", id_no))
        checks.append(_check(
            "ID_FORMAT", ok_format,
            f"ID number {mask_id(id_no)} has the expected format." if ok_format
            else "The signatory ID number could not be read.",
            "Check the ID number printed on the card.",
        ))
        valid_till = date_utils.parse(ident.get("valid_till"))
        ok_valid = date_utils.not_expired(valid_till)
        checks.append(_check(
            "ID_NOT_EXPIRED", ok_valid,
            f"ID valid till {valid_till}." if ok_valid and valid_till
            else "The signatory ID has expired.",
            "Upload a valid signatory ID.",
        ))
        udyam_record = registry.find_udyam(udyam_number)[0] if udyam_number else None
        business_names = [gst.get("trade_name"), gst.get("legal_name"),
                          (gst_record or {}).get("trade_name"), (gst_record or {}).get("legal_name"),
                          udyam.get("enterprise_name"), (udyam_record or {}).get("enterprise_name")]
        for_biz_score = best_similarity([ident.get("for_business")], business_names)
        legal = gst.get("legal_name") or (gst_record or {}).get("legal_name") or ""
        # Only a proprietorship names a person in its legal name ("Asha Rao (Prop. X)").
        # For an LLP / company the signatory is a partner or director, so only the
        # business on the ID can be matched (docs/06 section 3).
        if "(prop" in legal.lower():
            proprietor = legal.split("(")[0].strip()
            name_score = similarity(ident.get("name"), proprietor)
            ok_id = for_biz_score >= 0.9 and name_score >= 0.8
            detail_ok = f"Signatory is the proprietor of this business ({for_biz_score:.0%} business, {name_score:.0%} name)."
            detail_bad = f"Signatory does not match the proprietor on your GST details ({for_biz_score:.0%} business, {name_score:.0%} name)."
        else:
            ok_id = for_biz_score >= 0.9
            detail_ok = f"Signatory ID is issued for this business ({for_biz_score:.0%})."
            detail_bad = f"The business on the signatory ID differs from your registration ({for_biz_score:.0%})."
        checks.append(_check(
            "ID_NAME_BUSINESS", ok_id, detail_ok if ok_id else detail_bad,
            "The ID holder does not match the business - upload the authorised signatory's ID.",
            severity="warning",
        ))

    if profile:
        match = _profile_match(profile, gst, udyam, gst_record, gstin_value)
        if match:
            checks.append(match)
    return checks


def _doc_city(gst: dict, udyam: dict, gst_record: dict | None) -> str | None:
    if udyam.get("city"):
        return udyam["city"]
    address = (gst.get("address") or (gst_record or {}).get("principal_place_of_business") or "").lower()
    hits = [c for c in city_tiers() if c in address]
    return max(hits, key=len).title() if hits else None


def _profile_match(profile: dict, gst: dict, udyam: dict, gst_record: dict | None,
                   gstin_value: str | None) -> dict | None:
    """Do the documents belong to the business the owner described in the chat?"""
    doc_gstin = gstin_util.normalise(gstin_value or "") if gstin_value else None
    own_gstin = gstin_util.normalise(profile.get("gstin") or "") or None
    if own_gstin and doc_gstin:
        same = doc_gstin == own_gstin
        return _check(
            "PROFILE_MATCH", same,
            "Documents are for the GSTIN you gave us." if same
            else f"These documents are for GSTIN {mask_gstin(doc_gstin)}, not the one you gave ({mask_gstin(own_gstin)}).",
            "Upload your own business's documents, or start again with the GSTIN on these documents.",
        )

    doc_city = _doc_city(gst, udyam, gst_record)
    doc_name = gst.get("trade_name") or gst.get("legal_name") or udyam.get("enterprise_name") \
        or (gst_record or {}).get("trade_name")
    problems = []
    if profile.get("city") and doc_city and similarity(profile["city"], doc_city) < 0.85:
        problems.append(f"they are for a business in {doc_city}, but you told us {profile['city']}")
    if profile.get("business_name") and doc_name and \
            best_similarity([profile["business_name"]], [doc_name, udyam.get("enterprise_name")]) < 0.8:
        problems.append(f"they name {doc_name}, not {profile['business_name']}")
    if not (doc_city or doc_name) or not (profile.get("city") or profile.get("business_name")):
        return None   # nothing to compare yet
    ok = not problems
    return _check(
        "PROFILE_MATCH", ok,
        "Documents match the business you described." if ok
        else "These documents may be for a different business: " + "; ".join(problems) + ".",
        "Upload your own business's documents, or correct your city in the advisor.",
        severity="warning",
    )


def summary(checks: list[dict], readiness: dict) -> str:
    fails = [c for c in checks if c["status"] == "fail"]
    if not fails:
        return "All checks passed. This application is ready."
    parts = []
    for check in fails:
        parts.append(f"{check['code'].replace('_', ' ').title()}: {check['detail']}")
    return " ".join(parts[:3])
