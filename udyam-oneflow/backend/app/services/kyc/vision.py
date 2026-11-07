"""Optional vision-LLM second reader (docs/06: OCR_FALLBACK_LLM flag, off by default).

Local OCR always runs first. The vision model only fills or corrects fields,
and every value it returns goes through the same post-processing and the same
validators. Privacy: enabling this sends the document image to the LLM
provider, which is why it is a flag and disclosed in the privacy note.
"""
from __future__ import annotations

import re

from app.services import llm
from app.services.kyc.extract import DOC_FIELDS, _postprocess, field_labels
from app.utils import gstin as gstin_util

DOC_TITLE = {"gst": "GST registration certificate", "udyam": "Udyam registration certificate",
             "address": "electricity bill (address proof)", "signatory_id": "authorised signatory ID card"}
SYSTEM = (
    "You transcribe Indian business KYC documents into JSON. Copy each value exactly as printed. "
    "If a field is printed but its value is blank, return an empty string - never guess or invent a value. "
    "Ignore the diagonal watermark text. Dates as YYYY-MM-DD. Return only JSON."
)
VISION_CONFIDENCE = 0.55   # below the 0.6 bar on purpose: the owner is asked to confirm

FORMAT_CHECK = {
    "gstin": gstin_util.checksum_ok,
    "udyam_number": lambda v: bool(re.match(r"^UDYAM-[A-Z]{2}-00-\d{7}$", v or "")),
    "id_no": lambda v: bool(re.match(r"^SYN-ID-\d{6}$", v or "")),
}


def read(image: bytes, doc_type: str) -> dict[str, str] | None:
    specs = DOC_FIELDS.get(doc_type, [])
    labels = field_labels(doc_type)
    keys = ", ".join(f'"{s.key}" ({labels[s.key]})' for s in specs)
    prompt = f"This is a {DOC_TITLE.get(doc_type, doc_type)}. Return a JSON object with exactly these keys: {keys}."
    data = llm.complete_json(SYSTEM, prompt, image=image, max_tokens=800)
    if not data:
        return None
    out = {}
    for spec in specs:
        raw = data.get(spec.key)
        out[spec.key] = _postprocess(str(raw), spec.kind) if raw not in (None, "") else ""
    return out


def merge(ocr_fields: dict, ocr_conf: dict, vision_fields: dict | None) -> tuple[dict, dict, dict]:
    """Returns (fields, confidence, source). A vision value wins only when it is
    the one that passes the format check, or OCR found nothing."""
    if not vision_fields:
        return ocr_fields, ocr_conf, {k: "ocr" for k in ocr_fields}
    fields, conf, source = dict(ocr_fields), dict(ocr_conf), {k: "ocr" for k in ocr_fields}
    for key, vision_value in vision_fields.items():
        ocr_value = ocr_fields.get(key, "")
        if not vision_value or vision_value == ocr_value:
            continue
        check = FORMAT_CHECK.get(key)
        if check:
            if check(vision_value) and not check(ocr_value):
                fields[key], conf[key], source[key] = vision_value, VISION_CONFIDENCE, "vision"
            continue
        if not ocr_value:
            fields[key], conf[key], source[key] = vision_value, VISION_CONFIDENCE, "vision"
    return fields, conf, source
