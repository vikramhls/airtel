"""Identifier masking. Nothing that leaves the engine for a log or a UI label
carries a full GSTIN / Udyam number / signatory ID / phone."""
from __future__ import annotations

MASK = "\u2022"


def mask_gstin(value: str | None) -> str | None:
    if not value:
        return value
    v = value.strip().upper()
    if len(v) != 15:
        return v[:2] + MASK * max(len(v) - 5, 0) + v[-3:]
    return f"{v[:2]}{MASK * 10}{v[-3:]}"


def mask_udyam(value: str | None) -> str | None:
    if not value:
        return value
    parts = value.split("-")
    if len(parts) == 4:
        return f"{parts[0]}-{parts[1]}-{parts[2]}-{MASK * 3}{parts[3][-4:]}"
    return value[:8] + MASK * max(len(value) - 11, 0) + value[-3:]


def mask_id(value: str | None) -> str | None:
    if not value:
        return value
    digits = value.replace("SYN-ID-", "")
    return f"SYN-ID-{MASK * 3}{digits[-4:]}" if len(digits) > 4 else value


def mask_phone(value: str | None) -> str | None:
    if not value:
        return value
    digits = "".join(c for c in value if c.isdigit())
    return MASK * max(len(digits) - 3, 0) + digits[-3:]


def mask_address(value: str | None) -> str | None:
    """Logs keep only the city + PIN, never the street address."""
    if not value:
        return value
    parts = [p.strip() for p in value.split(",") if p.strip()]
    city = parts[-2] if len(parts) >= 2 else parts[0] if parts else ""
    pin = ""
    tail = parts[-1] if parts else ""
    if "-" in tail:
        pin = tail.split("-")[-1].strip()
    return f"{city} {pin}".strip()


def mask_payload(value):
    """Recursively mask identifiers in a dict/list before logging."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            key = k.lower()
            if isinstance(v, str):
                if "gstin" in key:
                    out[k] = mask_gstin(v)
                elif "udyam" in key:
                    out[k] = mask_udyam(v)
                elif key in {"id_no", "signatory_id"}:
                    out[k] = mask_id(v)
                elif key in {"phone", "mobile"}:
                    out[k] = mask_phone(v)
                elif key == "address":
                    out[k] = mask_address(v)
                else:
                    out[k] = v
            else:
                out[k] = mask_payload(v)
        return out
    if isinstance(value, list):
        return [mask_payload(v) for v in value]
    return value
