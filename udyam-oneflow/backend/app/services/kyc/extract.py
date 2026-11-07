"""Label-anchored field extraction from OCR tokens.

Layouts in the specimen pack:
  * inline  - label on the left, value on the right (GST, Udyam, address proof)
  * stacked - small label, value on the line below (signatory ID)

Rows are rebuilt from token coordinates, so it does not matter whether the OCR
engine returns words or whole lines. Wrapped values (addresses split across two
lines, sometimes mid-word) are joined back together.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.kyc.ocr import Token
from app.utils import gstin as gstin_util

JUNK = re.compile(r"synthetic|specimen|not a valid document|accel ytl|format for hackathon", re.I)
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
UDYAM_RE = re.compile(r"^UDYAM-([A-Z]{2})-(\d{2})-(\d{7})$")


def _repair_udyam(value: str) -> str:
    """Normalise OCR noise in a Udyam number, keeping the fixed district 00."""
    match = UDYAM_RE.match(value)
    if match:
        return value
    parts = value.split("-")
    if len(parts) >= 4:
        digits = re.sub(r"\D", "", parts[-1])
        return f"UDYAM-{parts[1]}-00-{digits[:7]}" if len(digits) >= 7 else value
    return value


@dataclass(frozen=True)
class FieldSpec:
    key: str
    labels: tuple[str, ...]
    kind: str = "text"          # text | date | id | amount | number
    continuation: bool = False


DOC_FIELDS: dict[str, list[FieldSpec]] = {
    "gst": [
        FieldSpec("gstin", ("GSTIN",), "id"),
        FieldSpec("legal_name", ("Legal name",)),
        FieldSpec("trade_name", ("Trade name",)),
        FieldSpec("constitution", ("Constitution",)),
        FieldSpec("address", ("Address of principal place of business", "Address of principal",
                              "place of business"), continuation=True),
        FieldSpec("date_of_liability", ("Date of liability",), "date"),
        FieldSpec("registration_type", ("Type of registration",)),
    ],
    "udyam": [
        FieldSpec("udyam_number", ("Udyam reg. number", "Udyam registration number",
                                   "Udyam reg number"), "id"),
        FieldSpec("enterprise_name", ("Enterprise name",)),
        FieldSpec("major_activity", ("Major activity",)),
        FieldSpec("city", ("City",)),
        FieldSpec("state", ("State",)),
        FieldSpec("date_of_registration", ("Date of registration",), "date"),
    ],
    "address": [
        FieldSpec("consumer_no", ("Consumer no.", "Consumer no"), "number"),
        FieldSpec("billed_to", ("Billed to",)),
        FieldSpec("supply_address", ("Supply address",), continuation=True),
        FieldSpec("bill_date", ("Bill date",), "date"),
        FieldSpec("units", ("Units consumed",), "number"),
        FieldSpec("amount_due", ("Amount due (INR)", "Amount due"), "amount"),
    ],
    "signatory_id": [
        FieldSpec("name", ("Name",)),
        FieldSpec("designation", ("Designation",)),
        FieldSpec("for_business", ("For business",)),
        FieldSpec("id_no", ("ID no.", "ID no"), "id"),
        FieldSpec("valid_till", ("Valid till",), "date"),
    ],
}

STACKED = {"signatory_id"}

# Longest labels first so "Address of principal place of business" wins.
for _specs in DOC_FIELDS.values():
    _specs.sort(key=lambda s: max(len(label) for label in s.labels), reverse=True)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\u2013", "-").replace("\u2014", "-")).strip()


def group_rows(tokens: list[Token], tolerance: float | None = None) -> list[list[Token]]:
    if not tokens:
        return []
    heights = [max(t.y1 - t.y0, 1) for t in tokens]
    tol = tolerance if tolerance is not None else max(sum(heights) / len(heights) * 0.6, 12)
    # A tilted scan pushes right-hand values onto the next label's row. Undo the
    # tilt using the median slope of the wider text lines before grouping.
    slopes = sorted(t.slope for t in tokens if t.x1 - t.x0 > 80)
    skew = slopes[len(slopes) // 2] if slopes else 0.0

    def level(t: Token) -> float:
        return t.cy - skew * t.cx

    ordered = sorted(tokens, key=lambda t: (level(t), t.x0))
    rows: list[list[Token]] = []
    for token in ordered:
        if rows and abs(level(token) - (sum(level(t) for t in rows[-1]) / len(rows[-1]))) <= tol:
            rows[-1].append(token)
        else:
            rows.append([token])
    for row in rows:
        row.sort(key=lambda t: t.x0)
    return rows


def _join(existing: str, addition: str) -> str:
    addition = addition.strip()
    if not addition:
        return existing
    if not existing:
        return addition
    if re.search(r"[A-Za-z0-9]$", existing) and re.match(r"^[a-z]", addition):
        return existing + addition           # mid-word wrap ("A" + "ndhra")
    if existing.endswith("-"):
        return existing + addition
    return f"{existing} {addition}"


def _postprocess(value: str, kind: str) -> str:
    value = _clean_text(value)
    if kind == "date":
        match = DATE_RE.search(value)
        return match.group(0) if match else ""
    if kind == "id":
        upper = value.upper().replace(" ", "")
        if re.match(r"^[0-9A-Z]{15}$", upper):
            return gstin_util.repair_ocr(upper)
        if upper.startswith("SYN") or re.match(r"^SYN.?\w?-\d{6}$", upper):
            # OCR often drops the I in SYN-ID-xxxxxx
            digits = re.sub(r"\D", "", upper)
            return f"SYN-ID-{digits}" if len(digits) >= 6 else upper
        if upper.startswith("UDYAM"):
            return _repair_udyam(upper)
        return upper
    if kind == "amount":
        digits = re.sub(r"[^0-9]", "", value)
        return str(int(digits)) if digits else ""
    if kind == "number":
        digits = re.sub(r"[^0-9]", "", value)
        return digits
    return value


def match_label(row_text: str, specs: list[FieldSpec]) -> tuple[FieldSpec, str] | None:
    norm = _norm(row_text)
    for spec in specs:
        for label in spec.labels:
            nlabel = _norm(label)
            if norm == nlabel or norm.startswith(nlabel + " "):
                return spec, row_text.strip()[len(label):].strip()
            # OCR may merge label and value with no space, e.g. "GSTIN37IHKX..."
            if norm.startswith(nlabel) and len(row_text) > len(label):
                rest = row_text.strip()[len(label):].strip(" :")
                if rest:
                    return spec, rest
    return None


def extract_fields(tokens: list[Token], doc_type: str) -> tuple[dict[str, str], dict[str, float]]:
    specs = DOC_FIELDS.get(doc_type, [])
    rows = group_rows(tokens)
    stacked = doc_type in STACKED
    values: dict[str, str] = {}
    confs: dict[str, list[float]] = {}
    current: FieldSpec | None = None

    for row in rows:
        text = _clean_text(" ".join(t.text for t in row))
        if not text or JUNK.search(text):
            continue
        match = match_label(text, specs)
        if match:
            spec, rest = match
            current = spec
            if rest:
                values[spec.key] = _join(values.get(spec.key, ""), rest)
                confs.setdefault(spec.key, []).extend(t.conf for t in row)
            continue
        # Not a label row: continuation of the previous field (wrapped address,
        # or the value line under a stacked label).
        if current is not None and (stacked or current.continuation or current.key not in values):
            values[current.key] = _join(values.get(current.key, ""), text)
            confs.setdefault(current.key, []).extend(t.conf for t in row)

    fields: dict[str, str] = {}
    confidence: dict[str, float] = {}
    for spec in specs:
        raw = values.get(spec.key, "")
        cleaned = _postprocess(raw, spec.kind)
        fields[spec.key] = cleaned
        vals = confs.get(spec.key, [])
        confidence[spec.key] = round(sum(vals) / len(vals), 3) if vals else 0.0
    return fields, confidence


def field_labels(doc_type: str) -> dict[str, str]:
    pretty = {
        "gstin": "GSTIN", "legal_name": "Legal name", "trade_name": "Trade name",
        "constitution": "Constitution", "address": "Principal place of business",
        "date_of_liability": "Date of liability", "registration_type": "Registration type",
        "udyam_number": "Udyam number", "enterprise_name": "Enterprise name",
        "major_activity": "Major activity", "city": "City", "state": "State",
        "date_of_registration": "Date of registration", "consumer_no": "Consumer no.",
        "billed_to": "Billed to", "supply_address": "Supply address",
        "bill_date": "Bill date", "units": "Units consumed", "amount_due": "Amount due",
        "name": "Name", "designation": "Designation", "for_business": "For business",
        "id_no": "ID number", "valid_till": "Valid till",
    }
    return {spec.key: pretty.get(spec.key, spec.key.replace("_", " ").title())
            for spec in DOC_FIELDS.get(doc_type, [])}


def extract(source, doc_type: str) -> dict:
    """Full OCR -> fields pipeline for one document."""
    from app.services.kyc import ocr, preprocess

    blur = round(preprocess.blur_score(source), 1)
    image = preprocess.prepare_for_ocr(source)
    tokens = ocr.read(image)
    fields, confidence = extract_fields(tokens, doc_type)
    return {
        "quality": {"blur": blur, "readable": blur >= preprocess.BLUR_MIN},
        "doc_type": doc_type,
        "engine": ocr.engine(),
        "fields": fields,
        "confidence": confidence,
        "labels": field_labels(doc_type),
        "token_count": len(tokens),
        "low_confidence": [k for k, v in confidence.items() if v and v < 0.6],
    }
