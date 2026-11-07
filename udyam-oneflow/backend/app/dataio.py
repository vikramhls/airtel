"""CSV data pack access. Loaded once, cached, never mutated.

Sources: product_catalogue (25), smb_leads (5,000), mock_gstin_registry (3,534),
mock_udyam_registry (2,723). All synthetic (see data/README.md).
"""
from __future__ import annotations

from functools import lru_cache

import pandas as pd

from app import config


@lru_cache(maxsize=1)
def catalogue_frame() -> pd.DataFrame:
    df = pd.read_csv(config.DATA_DIR / "product_catalogue.csv", dtype=str).fillna("")
    return df


@lru_cache(maxsize=1)
def leads_frame() -> pd.DataFrame:
    df = pd.read_csv(config.DATA_DIR / "smb_leads.csv", dtype=str).fillna("")
    return df


@lru_cache(maxsize=1)
def gstin_frame() -> pd.DataFrame:
    df = pd.read_csv(config.DATA_DIR / "mock_gstin_registry.csv", dtype=str).fillna("")
    df["gstin"] = df["gstin"].str.strip().str.upper()
    return df


@lru_cache(maxsize=1)
def udyam_frame() -> pd.DataFrame:
    df = pd.read_csv(config.DATA_DIR / "mock_udyam_registry.csv", dtype=str).fillna("")
    df["udyam_number"] = df["udyam_number"].str.strip().str.upper()
    return df


@lru_cache(maxsize=1)
def gstin_lookup() -> dict[str, dict]:
    return {row["gstin"]: row.to_dict() for _, row in gstin_frame().iterrows()}


@lru_cache(maxsize=1)
def udyam_lookup() -> dict[str, dict]:
    return {row["udyam_number"]: row.to_dict() for _, row in udyam_frame().iterrows()}


@lru_cache(maxsize=1)
def city_tiers() -> dict[str, int]:
    """city (lowercase) -> tier, from the lead data (22 cities, tiers 1-2)."""
    df = leads_frame()[["city", "city_tier"]].drop_duplicates()
    return {r.city.strip().lower(): int(r.city_tier) for r in df.itertuples()}


def city_tier(city: str | None) -> int | None:
    if not city:
        return None
    return city_tiers().get(city.strip().lower())


@lru_cache(maxsize=1)
def cities() -> list[dict]:
    df = leads_frame()["city"].drop_duplicates().sort_values()
    return [{"name": c, "tier": city_tier(c)} for c in df]


SEGMENT_KEY = {
    "Micro retail & services": "micro",
    "Professional offices": "prof",
    "Small multi-site businesses": "multi",
    "Small manufacturers": "mfg",
}
SEGMENT_NAME = {v: k for k, v in SEGMENT_KEY.items()}


@lru_cache(maxsize=1)
def segment_spend_median() -> dict[str, int]:
    """Median telecom spend of *activated* leads per segment - the fallback anchor."""
    df = leads_frame()
    act = df[df["outcome"] == "Activated"].copy()
    act["spend"] = pd.to_numeric(act["monthly_telecom_spend_inr"], errors="coerce")
    out: dict[str, int] = {}
    for seg, grp in act.groupby("segment"):
        val = grp["spend"].median()
        out[SEGMENT_KEY.get(seg, seg)] = int(val) if pd.notna(val) else 1000
    return out


def data_counts() -> dict[str, int]:
    return {
        "catalogue": len(catalogue_frame()),
        "leads": len(leads_frame()),
        "gstin_registry": len(gstin_frame()),
        "udyam_registry": len(udyam_frame()),
    }
