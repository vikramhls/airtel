"""OCR result cache for the specimen pack.

The batch script fills it once; the "use sample document" demo button and the
tests read it so they do not wait for OCR. Uploaded owner files are never cached.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache

from app import config

CACHE_PATH = config.REPORTS_DIR / "kyc_extractions.json"


def cache_key(filename: str, content: bytes) -> str:
    return f"{filename}:{hashlib.sha256(content).hexdigest()[:16]}"


@lru_cache(maxsize=1)
def _load() -> dict:
    if not CACHE_PATH.exists():
        return {}
    return json.loads(CACHE_PATH.read_text())


def lookup(filename: str, content: bytes) -> dict | None:
    return _load().get(cache_key(filename, content))
