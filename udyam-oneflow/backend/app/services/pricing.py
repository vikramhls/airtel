"""Pricing policy + quantities.

Policy (docs/04 section 6, configurable via config.PRICING_POLICY):
  line term < 12  -> top of band
  line term = 12  -> midpoint of band
  line term >= 24 -> bottom of band
Each line's term is max(product.min_contract_months, chosen term), so a
24-month-minimum product is always priced at the bottom of its band.
"""
from __future__ import annotations

from app.config import PRICING_POLICY
from app.schemas import BusinessProfile, LineItem
from app.services.catalogue import Product

SETUP_MULTIPLIED_UNITS = {
    "per site", "per line", "per counter", "per camera", "per user", "per device",
    "per channel", "per vehicle",
}


def line_term(product: Product, chosen_term: int) -> int:
    return max(product.min_contract, chosen_term)


def unit_price(product: Product, chosen_term: int) -> int:
    lt = line_term(product, chosen_term)
    if lt >= PRICING_POLICY["long_term_months"]:
        return product.price_min
    if lt >= PRICING_POLICY["mid_term_months"]:
        return product.mid_price
    return product.price_max


def policy_label(product: Product, chosen_term: int) -> str:
    lt = line_term(product, chosen_term)
    if lt >= PRICING_POLICY["long_term_months"]:
        return "24m = min"
    if lt >= PRICING_POLICY["mid_term_months"]:
        return "12m = mid"
    return "<12m = max"


def default_qty(product: Product, profile: BusinessProfile, segment: str) -> int:
    sites = profile.sites or 1
    emp = profile.employees or 1
    unit = product.unit.lower()
    if unit == "per site":
        return sites
    if unit == "per line":
        cap = 5 if segment in {"micro", "prof"} else 10
        return max(1, min(emp, cap))
    if unit == "per counter":
        return sites
    if unit == "per camera":
        return (2 if segment == "micro" else 4) * sites
    if unit == "per user":
        return emp
    if unit == "per device":
        if product.id == "P24":  # machine monitoring: 5 sensors per factory site
            return 5 * sites
        return emp
    if unit == "per channel":
        return max(2, emp // 5)
    return 1  # per account / pack / number / IP / vehicle


def setup_for(product: Product, qty: int) -> int:
    if product.setup == 0:
        return 0
    if product.unit.lower() in SETUP_MULTIPLIED_UNITS:
        return product.setup * qty
    return product.setup


def build_line(
    product: Product,
    profile: BusinessProfile,
    segment: str,
    chosen_term: int,
    *,
    qty: int | None = None,
    is_addon: bool = False,
    why: str = "",
    rules_passed: list[str] | None = None,
) -> LineItem:
    quantity = max(1, qty if qty is not None else default_qty(product, profile, segment))
    return LineItem(
        product_id=product.id,
        name=product.name,
        category=product.category,
        description=product.description,
        qty=quantity,
        unit=product.unit,
        price_min=product.price_min,
        price_max=product.price_max,
        unit_price=unit_price(product, chosen_term),
        setup_inr=setup_for(product, quantity),
        setup_each=product.setup,
        line_term_months=line_term(product, chosen_term),
        is_addon=is_addon,
        why=why,
        rules_passed=rules_passed or [],
        install_days=product.install_days,
    )


def totals(items: list[LineItem]) -> dict:
    """Totals are always the sum of their lines - the invariant the UI checks."""
    monthly = sum(i.unit_price * i.qty for i in items)
    lo = sum(i.price_min * i.qty for i in items)
    hi = sum(i.price_max * i.qty for i in items)
    setup = sum(i.setup_inr for i in items)
    contract = max((i.line_term_months for i in items), default=PRICING_POLICY["default_term_months"])
    install = max((i.install_days for i in items), default=0)
    return {
        "total_monthly": monthly,
        "total_monthly_range": (lo, hi),
        "total_setup": setup,
        "contract_months": contract,
        "install_days": install,
    }
