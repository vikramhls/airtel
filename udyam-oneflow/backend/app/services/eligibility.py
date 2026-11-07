"""Eligibility rules. Pure functions, no I/O.

Rule codes follow docs/04 section 2. `dependency` is resolved by the bundler
because it needs the whole bundle; everything else is per product.
"""
from __future__ import annotations

from app.schemas import BusinessProfile
from app.services.catalogue import Product

RULE_ORDER = ["city_tier", "employees", "sites", "gstin_missing", "gstin_cancelled", "gstin_suspended"]


def gstin_block(profile: BusinessProfile) -> str | None:
    status = (profile.gstin_status or "").strip().lower()
    if status == "cancelled":
        return "gstin_cancelled"
    if status == "suspended":
        return "gstin_suspended"
    if profile.has_gstin is False:
        return "gstin_missing"
    if profile.has_gstin is None and not profile.gstin:
        return "gstin_missing"  # unknown -> asks the owner, does not silently pass
    return None


def check(product: Product, profile: BusinessProfile, tier: int | None) -> dict:
    """Returns {'product', 'passed': [...], 'failed': [...]}."""
    passed: list[str] = []
    failed: list[str] = []

    if tier is not None and tier in product.tiers:
        passed.append("city_tier")
    else:
        failed.append("city_tier")

    if profile.employees is None:
        if product.min_employees <= 1:
            passed.append("employees")
        else:
            failed.append("employees")
    elif profile.employees >= product.min_employees:
        passed.append("employees")
    else:
        failed.append("employees")

    sites = profile.sites if profile.sites is not None else 1
    if sites >= product.min_sites:
        passed.append("sites")
    else:
        failed.append("sites")

    if not product.requires_gstin:
        passed.append("gstin")
    else:
        block = gstin_block(profile)
        if block is None:
            passed.append("gstin")
        else:
            failed.append(block)

    if product.segments and (profile.segment or "") in product.segments:
        passed.append("segment_fit")

    return {"product": product.id, "passed": passed, "failed": failed}


def primary_failure(product: Product, failed: list[str]) -> str:
    for rule in RULE_ORDER:
        if rule in failed:
            return rule
    return failed[0] if failed else "dependency"


def is_eligible(product: Product, profile: BusinessProfile, tier: int | None) -> bool:
    return not check(product, profile, tier)["failed"]


def segment_fit(product: Product, segment: str | None) -> bool:
    return bool(product.segments) and (segment or "") in product.segments
