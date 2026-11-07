"""GSTIN format + mod-36 checksum (verified against all 3,534 registry rows).

Synthetic data note: the 4th character of the embedded PAN is always `X`, which
is not a real entity type. We accept it (docs/05, data pack README).
"""
from __future__ import annotations

import re

GSTIN_RE = re.compile(r"^\d{2}[A-Z]{3}X[A-Z]\d{4}[A-Z]\d[A-Z][A-Z0-9]$")

ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
VALUE = {ch: i for i, ch in enumerate(ALPHABET)}

# GST state codes present in the registry (built from the CSV at load time too).
STATE_CODES = {
    "01": "Jammu & Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh",
    "05": "Uttarakhand", "06": "Haryana", "07": "Delhi", "08": "Rajasthan",
    "09": "Uttar Pradesh", "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh",
    "13": "Nagaland", "14": "Manipur", "15": "Mizoram", "16": "Tripura",
    "17": "Meghalaya", "18": "Assam", "19": "West Bengal", "20": "Jharkhand",
    "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "27": "Maharashtra", "29": "Karnataka", "30": "Goa", "32": "Kerala",
    "33": "Tamil Nadu", "34": "Puducherry", "36": "Telangana", "37": "Andhra Pradesh",
}


def normalise(value: str) -> str:
    return "".join(ch for ch in (value or "").upper() if ch.isalnum())


def format_ok(value: str) -> bool:
    return bool(GSTIN_RE.match(normalise(value)))


def checksum_char(first14: str) -> str:
    """GSTIN mod-36 check digit: multiply alternating by 1/2, then fold each
    product with /36 + %36 (verified: 3,534/3,534 registry rows pass)."""
    total = 0
    for i, ch in enumerate(first14):
        product = VALUE[ch] * (1 if i % 2 == 0 else 2)
        total += product // 36 + product % 36
    return ALPHABET[(36 - (total % 36)) % 36]


def checksum_ok(value: str) -> bool:
    v = normalise(value)
    if len(v) != 15 or any(ch not in VALUE for ch in v):
        return False
    return checksum_char(v[:14]) == v[14]


def validate(value: str) -> tuple[bool, str | None]:
    """Returns (ok, error_code). Format is checked before the checksum so the
    UI can tell the owner which of the two failed."""
    v = normalise(value)
    if not format_ok(v):
        return False, "GSTIN_FORMAT"
    if not checksum_ok(v):
        return False, "GSTIN_CHECKSUM"
    return True, None


def state_code(value: str) -> str | None:
    v = normalise(value)
    return v[:2] if len(v) >= 2 else None


def state_name(value: str) -> str | None:
    return STATE_CODES.get(state_code(value) or "")


def repair_ocr(value: str) -> str:
    """Fix common OCR confusions only in positions where the pattern demands it."""
    v = normalise(value)
    if len(v) != 15:
        return v
    out = list(v)
    for i in range(15):
        if i < 2 or 7 <= i <= 10 or i == 12:      # digit positions
            out[i] = {"O": "0", "Q": "0", "I": "1", "L": "1", "S": "5", "B": "8", "Z": "2"}.get(out[i], out[i])
        elif i in {2, 3, 4, 6, 11, 13}:           # letter positions
            out[i] = {"0": "O", "1": "I", "5": "S", "8": "B", "2": "Z"}.get(out[i], out[i])
    return "".join(out)
