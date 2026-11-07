"""Central configuration.

Every date in business logic comes from REFERENCE_DATE (the dataset's "today").
`datetime.now()` is never used for business rules - only for audit timestamps.
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _load_env_file(path: Path) -> None:
    """Minimal .env reader (no extra dependency). Real env vars win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file(BACKEND_DIR / ".env")
APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
DOCS_DIR = DATA_DIR / "kyc_documents"
REPORTS_DIR = BACKEND_DIR.parent / "reports"
MODELS_DIR = BACKEND_DIR.parent / "models"

DB_PATH = Path(os.getenv("ONEFLOW_DB", str(BACKEND_DIR / "oneflow.db")))

# The dataset's "today". All date rules (address proof <= 90 days, ID validity,
# demo clock) are relative to this. Never replace with date.today().
REFERENCE_DATE = date.fromisoformat(os.getenv("REFERENCE_DATE", "2026-07-15"))

DOC_RETENTION_DAYS = int(os.getenv("DOC_RETENTION_DAYS", "7"))
ADDRESS_PROOF_MAX_AGE_DAYS = 90

# Pricing policy (docs/04 section 6). Shown on the plan screen and in reports.
PRICING_POLICY = {
    "short_term_months": 12,   # < 12 -> top of band
    "mid_term_months": 12,     # 12 -> midpoint of band
    "long_term_months": 24,    # >= 24 -> bottom of band
    "default_term_months": 12,
}

# LLM (language only - never prices or eligibility). Tried in order; if every
# provider fails the scripted advisor answers (AGENTS.md invariant 7).
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini,openrouter")  # or "none"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODELS = [m.strip() for m in os.getenv(
    "OPENROUTER_MODELS",
    "nvidia/nemotron-3.5-lightning:free,google/gemma-4-31b-it:free,google/gemma-4-26b-a4b-it:free",
).split(",") if m.strip()]
LLM_TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_S", "12"))
OCR_FALLBACK_LLM = os.getenv("OCR_FALLBACK_LLM", "0") == "1"

# Demo/admin endpoints (advance the order clock, inject a block).
ADMIN_ENABLED = os.getenv("ADMIN_ENABLED", "1") == "1"
# Partner cockpit static token (hackathon shortcut, see docs/10).
PARTNER_TOKEN = os.getenv("PARTNER_TOKEN", "partner-demo")

CONSENT_TEXT_VERSION = "v1"

# Install/KYC SLAs (explicit design assumptions, configurable).
KYC_SLA_DAYS_INSTANT = 0   # every check passed when the documents were read: verified at once
KYC_SLA_DAYS_AUTO = 1      # automated re-check after the owner fixes a blocker
KYC_SLA_DAYS_MANUAL = 2    # warnings (name/address mismatch, inactive GSTIN) need a person to review
ORDER_PROCESSING_DAYS = 1
