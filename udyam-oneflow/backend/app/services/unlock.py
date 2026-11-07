"""Unlock paths: never a bare "not eligible".

Every blocked product says why, what unlocks it, and what it would add per month.
"""
from __future__ import annotations

from app.schemas import BusinessProfile, UnlockPath
from app.services import catalogue
from app.services.catalogue import Product
from app.services.eligibility import check

# Natural "closest fit today" overrides where price-distance alone is misleading.
ALTERNATIVE_OVERRIDE = {"P10": "P09", "P12": "P07", "P06": "P05", "P05": "P03", "P03": "P01"}

UNLOCK_ACTION = {
    "gstin_missing": "Get a GSTIN (a partner can help you register)",
    "gstin_cancelled": "Reactivate your GSTIN on the GST portal (ask a partner for help)",
    "gstin_suspended": "Reactivate your GSTIN on the GST portal (ask a partner for help)",
    "employees": "Grow the team, or ask a partner for a custom plan",
    "sites": "Add locations, or ask a partner for a custom plan",
    "city_tier": "We will tell you when it launches in your city",
    "dependency": "Add a base internet plan first",
}


REASON_TEXT = {
    "city_tier": lambda p: "a city where it is sold (tier " + "/".join(map(str, p.tiers)) + ")",
    "employees": lambda p: f"{p.min_employees}+ people",
    "sites": lambda p: f"{p.min_sites}+ locations",
    "gstin_missing": lambda p: "an active GSTIN",
    "gstin_cancelled": lambda p: "an active GSTIN",
    "gstin_suspended": lambda p: "an active GSTIN",
}


def rupees(value: int) -> str:
    return f"\u20b9{value:,}"


def _eligible_products(profile: BusinessProfile, tier: int | None) -> list[Product]:
    return [p for p in catalogue.all_products() if not check(p, profile, tier)["failed"]]


def alternative_for(product: Product, profile: BusinessProfile, tier: int | None) -> Product | None:
    override = ALTERNATIVE_OVERRIDE.get(product.id)
    if override:
        alt = catalogue.get(override)
        if alt and not check(alt, profile, tier)["failed"]:
            return alt
    options = [
        p for p in _eligible_products(profile, tier)
        if p.id != product.id and p.category == product.category
    ]
    if not options:
        options = [p for p in _eligible_products(profile, tier) if p.id != product.id]
    if not options:
        return None
    target = product.mid_price
    return min(options, key=lambda p: (abs(p.mid_price - target), p.mid_price))


def build(
    product: Product,
    result: dict,
    profile: BusinessProfile,
    tier: int | None,
    *,
    needed: bool = False,
    related_blocked: int = 0,
) -> UnlockPath:
    failed = result["failed"]
    # Primary reason: the most actionable / first in rule order.
    priority = ["city_tier", "employees", "sites", "gstin_missing", "gstin_cancelled", "gstin_suspended"]
    blocked_by = next((r for r in priority if r in failed), failed[0] if failed else "dependency")

    alt = alternative_for(product, profile, tier)
    if alt and blocked_by.startswith("gstin_") and alt.category != product.category:
        alt = None  # "WhatsApp -> Fibre" is not an alternative; the unlock is the GSTIN
    alt_name = alt.name if alt else None
    band = (product.price_min, product.price_max)

    if blocked_by == "gstin_missing":
        message = (
            f"{product.name} needs a GSTIN. With one you unlock it for "
            f"{rupees(product.price_min)}-{rupees(product.price_max)}/month. "
            "A partner can help you register."
        )
    elif blocked_by in {"gstin_cancelled", "gstin_suspended"}:
        status = "Cancelled" if blocked_by == "gstin_cancelled" else "Suspended"
        extra = f" (and {related_blocked} other products)" if related_blocked else ""
        message = (
            f"Your GSTIN shows as {status}. Reactivate it to unlock {product.name}{extra}. "
            "You can still buy products that do not need a GSTIN."
        )
    elif blocked_by == "employees":
        message = (
            f"{product.name} is for businesses with {product.min_employees}+ people. "
            f"Closest fit today: {alt_name or 'a smaller plan'}."
        )
    elif blocked_by == "sites":
        message = (
            f"{product.name} is built for {product.min_sites}+ locations. "
            f"Closest fit today: {alt_name or 'a single-site plan'}."
        )
    elif blocked_by == "city_tier":
        city = profile.city or "your city"
        message = f"{product.name} is not available in {city} yet."
    else:
        message = f"{product.name} needs a base internet plan first."

    others = [REASON_TEXT[r](product) for r in failed if r != blocked_by and r in REASON_TEXT]
    if others:
        message += " It also needs " + " and ".join(others) + "."

    return UnlockPath(
        product_id=product.id,
        name=product.name,
        category=product.category,
        blocked_by=blocked_by,  # type: ignore[arg-type]
        failed_rules=failed,
        message=message,
        unlock_action=UNLOCK_ACTION[blocked_by],
        adds_per_month=band,
        alternative_product_id=alt.id if alt else None,
        alternative_name=alt_name,
        needed=needed,
    )


def summary(profile: BusinessProfile, tier: int | None, segment: str) -> dict:
    """Headline: 'A GSTIN would unlock K products worth Rs X-Y/month'."""
    gated = [
        p for p in catalogue.all_products()
        if p.requires_gstin and (segment in p.segments or not p.segments)
        and (tier in p.tiers if tier else True)
    ]
    lo = sum(p.price_min for p in gated)
    hi = sum(p.price_max for p in gated)
    block = "gstin_cancelled" if (profile.gstin_status or "").lower() == "cancelled" else (
        "gstin_suspended" if (profile.gstin_status or "").lower() == "suspended" else "gstin_missing"
    )
    status = (profile.gstin_status or "").lower()
    needs_gstin = profile.has_gstin is not True or status in {"cancelled", "suspended"}
    headline = None
    if gated and needs_gstin:
        headline = (
            f"A GSTIN would unlock {len(gated)} products worth "
            f"{rupees(lo)}-{rupees(hi)}/month for your business."
        )
    return {
        "blocked_by": block,
        "product_count": len(gated),
        "products": [p.id for p in gated],
        "value_per_month": [lo, hi],
        "headline": headline,
    }
