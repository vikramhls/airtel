"""Request/response schemas (Pydantic v2)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Segment = Literal["micro", "prof", "multi", "mfg"]
Need = Literal[
    "internet", "mobile", "billing_pos", "whatsapp", "sms", "email_cloud",
    "security", "cctv", "telephony", "wifi", "iot", "tracking", "website",
]
BlockReason = Literal[
    "gstin_missing", "gstin_cancelled", "gstin_suspended", "employees",
    "sites", "city_tier", "dependency",
]


class BusinessProfile(BaseModel):
    business_type: str | None = None
    business_name: str | None = None
    segment: Segment | None = None
    city: str | None = None
    city_tier: int | None = None
    state: str | None = None
    employees: int | None = None
    sites: int | None = 1
    has_gstin: bool | None = None
    gstin: str | None = None
    gstin_status: Literal["Active", "Cancelled", "Suspended"] | None = None
    has_udyam: bool | None = None
    udyam_number: str | None = None
    needs: list[Need] = Field(default_factory=list)
    requested_products: list[str] = Field(default_factory=list)
    budget_inr: int | None = None
    current_spend_inr: int | None = None
    current_provider: str | None = None
    current_internet: str | None = None
    fibre_available: bool | None = None


class LineItem(BaseModel):
    product_id: str
    name: str
    category: str
    description: str = ""
    qty: int
    unit: str
    price_min: int
    price_max: int
    unit_price: int
    setup_inr: int
    setup_each: int = 0
    line_term_months: int
    is_addon: bool = False
    why: str = ""
    rules_passed: list[str] = Field(default_factory=list)
    install_days: int = 0


class UnlockPath(BaseModel):
    product_id: str
    name: str
    category: str = ""
    blocked_by: BlockReason
    failed_rules: list[str] = Field(default_factory=list)
    message: str
    unlock_action: str
    adds_per_month: tuple[int, int]
    alternative_product_id: str | None = None
    alternative_name: str | None = None
    needed: bool = False


class Rung(BaseModel):
    label: Literal["Start", "Grow", "Complete"]
    items: list[LineItem]
    addons: list[LineItem]
    total_monthly: int
    total_monthly_range: tuple[int, int]
    total_setup: int
    contract_months: int
    vs_current_spend: float | None = None
    install_days: int = 0
    why: str = ""
    over_budget_by: int | None = None


class RecommendationResult(BaseModel):
    available: bool = True
    notice: str | None = None
    segment: Segment | None = None
    city_tier: int | None = None
    ladder: list[Rung] = Field(default_factory=list)
    blocked: list[UnlockPath] = Field(default_factory=list)
    unlock_summary: dict | None = None
    anchor_spend: int | None = None
    budget_advice: dict | None = None
    trace: dict = Field(default_factory=dict)
    handoff: bool = False


class Problem(BaseModel):
    code: str
    message: str
    fix_hint: str | None = None


class ProfilePatch(BaseModel):
    """Everything the advisor may set from free text - all optional."""
    business_type: str | None = None
    business_name: str | None = None
    city: str | None = None
    state: str | None = None
    employees: int | None = None
    sites: int | None = None
    has_gstin: bool | None = None
    gstin: str | None = None
    needs: list[Need] | None = None
    requested_products: list[str] | None = None
    budget_inr: int | None = None
    current_spend_inr: int | None = None
    current_provider: str | None = None
    fibre_available: bool | None = None
    has_udyam: bool | None = None
