"""Segment inference from business type (35 types mapped in smb_leads.csv)."""
from __future__ import annotations

from app.dataio import leads_frame, city_tier
from app.schemas import BusinessProfile

TYPE_TO_SEGMENT: dict[str, str] = {
    # micro
    "bakery": "micro", "stationery shop": "micro", "optician": "micro",
    "kirana store": "micro", "salon": "micro", "hardware store": "micro",
    "boutique": "micro", "sweet shop": "micro", "pharmacy": "micro",
    "mobile repair shop": "micro",
    # professional
    "dental clinic": "prof", "diagnostic lab": "prof", "physiotherapy clinic": "prof",
    "real estate agency": "prof", "law office": "prof", "coaching centre": "prof",
    "ca firm": "prof", "architecture studio": "prof", "travel agency": "prof",
    "insurance agency": "prof",
    # manufacturing
    "auto-parts unit": "mfg", "textile unit": "mfg", "plastic moulding unit": "mfg",
    "packaging unit": "mfg", "food processing unit": "mfg", "furniture workshop": "mfg",
    "printing press": "mfg",
    # multi-site chains
    "electronics retail chain": "multi", "apparel retail chain": "multi",
    "bakery chain": "multi", "restaurant chain": "multi", "pharmacy chain": "multi",
    "pre-school chain": "multi", "budget hotel group": "multi", "gym chain": "multi",
}

_KEYWORDS = {
    "prof": ("clinic", "office", "firm", "agency", "lab", "studio", "coaching", "consult"),
    "mfg": ("unit", "factory", "workshop", "manufactur", "plant", "mill", "press"),
    "multi": ("chain", "group", "stores", "branches", "outlets"),
    "micro": ("shop", "store", "salon", "bakery", "kirana", "boutique", "repair", "optician",
              "restaurant", "cafe", "dhaba", "hotel", "gym", "school", "parlour", "dukan"),
}


def known_types() -> list[str]:
    return sorted(TYPE_TO_SEGMENT)


def infer_segment(business_type: str | None, sites: int | None = None) -> str | None:
    """Deterministic fallback chain: exact type -> keyword -> size."""
    if business_type:
        key = business_type.strip().lower()
        if key in TYPE_TO_SEGMENT:
            seg = TYPE_TO_SEGMENT[key]
        else:
            seg = None
            for name, s in TYPE_TO_SEGMENT.items():
                if name in key or key in name:
                    seg = s
                    break
            if seg is None:
                for s, words in _KEYWORDS.items():
                    if any(w in key for w in words):
                        seg = s
                        break
        if seg == "mfg":
            return "mfg"  # sites>=3 does not turn a factory into a chain
        if sites is not None and sites >= 3:
            return "multi"
        if seg:
            return seg
    if sites is not None and sites >= 3:
        return "multi"
    return None


def canonical_type(text: str | None) -> str | None:
    """Map a free-text business type onto the catalogue's 35 names."""
    if not text:
        return None
    low = text.strip().lower()
    if low in TYPE_TO_SEGMENT:
        return low.title()
    for name in TYPE_TO_SEGMENT:
        if name in low or low in name:
            return name.title()
    return None


def profile_segment(profile: BusinessProfile) -> str | None:
    if profile.segment:
        return profile.segment
    return infer_segment(profile.business_type, profile.sites)


def resolve_tier(profile: BusinessProfile) -> int | None:
    if profile.city_tier:
        return profile.city_tier
    return city_tier(profile.city)


def lead_segment_types() -> dict[str, list[str]]:
    df = leads_frame()[["business_type", "segment"]]
    out: dict[str, list[str]] = {}
    for r in df.itertuples(index=False):
        out.setdefault(r.segment, set()).add(r.business_type)  # type: ignore[arg-type]
    return {k: sorted(v) for k, v in out.items()}
