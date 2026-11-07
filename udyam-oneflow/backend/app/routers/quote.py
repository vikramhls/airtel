from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app import config, db
from app.routers.common import problem, require_session, resolved_profile
from app.services import bundler, catalogue, orders, quotes
from app.services.eligibility import check

router = APIRouter(tags=["quote"])


class QuoteIn(BaseModel):
    session_id: str
    rung: str | None = "Start"
    product_ids: list[str] | None = None
    qty_overrides: dict[str, int] | None = None
    term_months: int = 12


class ToggleIn(BaseModel):
    quote_id: str
    product_id: str
    on: bool


class TermIn(BaseModel):
    quote_id: str
    term_months: int


class QtyIn(BaseModel):
    quote_id: str
    product_id: str
    qty: int


def _load(quote_id: str) -> dict:
    quote = quotes.get(quote_id)
    if not quote:
        raise problem(404, "QUOTE_NOT_FOUND", "Quote not found.", "Build a new quote from your plan.")
    return quote


def _enrich(quote: dict, session_id: str) -> dict:
    """Add what the checkout screen needs: add-ons, unlock cards, ETA, budget/spend comparison."""
    profile = resolved_profile(session_id)
    # Best case: documents pass every check when uploaded (the tracker shows the real date per order).
    ms = orders.milestones(config.REFERENCE_DATE, quote["items"], config.KYC_SLA_DAYS_INSTANT) if quote["items"] else None
    current = {i["product_id"] for i in quote["items"]}
    rec = bundler.recommend(profile, quote["term_months"])
    addons, seen = [], set()
    for rung in rec.ladder:
        for line in rung.items + rung.addons:
            if line.product_id in current or line.product_id in seen:
                continue
            seen.add(line.product_id)
            p = catalogue.get(line.product_id)
            addons.append({"product_id": p.id, "name": p.name, "category": p.category, "unit": p.unit,
                           "unit_price": line.unit_price, "qty": line.qty, "setup_inr": line.setup_inr,
                           "needs": list(p.requires_one_of), "description": p.description})
    quote["available_addons"] = addons
    quote["blocked"] = [u.model_dump() for u in rec.blocked]
    quote["expected_activation_date"] = ms["activated"].isoformat() if ms else None
    quote["vs_current_spend"] = (round(quote["total_monthly"] / profile.current_spend_inr, 2)
                                 if profile.current_spend_inr else None)
    quote["over_budget_by"] = (quote["total_monthly"] - profile.budget_inr
                               if profile.budget_inr and quote["total_monthly"] > profile.budget_inr else None)
    quote["pricing_note"] = ("Prices come from product_catalogue.csv: 12-month term = midpoint of the price band, "
                             "24 months = bottom of the band.")
    return quote


@router.post("/quote")
def create_quote(body: QuoteIn):
    require_session(body.session_id)
    if body.term_months not in (12, 24):
        raise problem(422, "BAD_TERM", "Contract term must be 12 or 24 months.", "Pick 12 or 24 months.")
    profile = resolved_profile(body.session_id)
    rec = bundler.recommend(profile, body.term_months)
    qty = dict(body.qty_overrides or {})
    if body.product_ids:
        ids, label = body.product_ids, "Custom"
        for pid in ids:
            product = catalogue.get(pid)
            if not product:
                raise problem(404, "PRODUCT_NOT_FOUND", f"{pid} is not in the catalogue.", None)
            if check(product, profile, profile.city_tier)["failed"]:
                raise problem(422, "NOT_ELIGIBLE", f"{product.name} is not available for your business yet.",
                              "See its unlock card on the plan screen.")
    else:
        if not rec.available or not rec.ladder:
            raise problem(409, "NO_PLAN", rec.notice or "No plan yet.", "Finish the advisor questions first.")
        rung = next((r for r in rec.ladder if r.label == body.rung), rec.ladder[0])
        ids, label = [i.product_id for i in rung.items], rung.label
        qty = {**{i.product_id: i.qty for i in rung.items}, **qty}
    items = quotes.build_items(ids, profile, profile.segment, body.term_months, qty)
    quote = quotes.save(body.session_id, label, body.term_months, items, rec.trace)
    return _enrich(quote, body.session_id)


@router.get("/quote/{quote_id}")
def get_quote(quote_id: str):
    quote = _load(quote_id)
    return _enrich(quote, quote["session_id"])


@router.post("/quote/toggle")
def toggle(body: ToggleIn):
    quote = _load(body.quote_id)
    profile = resolved_profile(quote["session_id"])
    product = catalogue.get(body.product_id)
    if not product:
        raise problem(404, "PRODUCT_NOT_FOUND", "No such product.", None)
    if body.on and check(product, profile, profile.city_tier)["failed"]:
        raise problem(422, "NOT_ELIGIBLE", f"{product.name} is not available for your business yet.",
                      "See its unlock card on the plan screen.")
    out = quotes.toggle(body.quote_id, body.product_id, body.on, profile)
    return _enrich(out, quote["session_id"])


@router.post("/quote/term")
def change_term(body: TermIn):
    quote = _load(body.quote_id)
    if body.term_months not in (12, 24):
        raise problem(422, "BAD_TERM", "Contract term must be 12 or 24 months.", "Pick 12 or 24 months.")
    profile = resolved_profile(quote["session_id"])
    qty = {i["product_id"]: i["qty"] for i in quote["items"]}
    items = quotes.build_items([i["product_id"] for i in quote["items"]], profile, profile.segment,
                               body.term_months, qty)
    db.execute("UPDATE quotes SET term_months = ? WHERE id = ?", (body.term_months, body.quote_id))
    return _enrich(quotes.replace_items(body.quote_id, items), quote["session_id"])


@router.post("/quote/qty")
def change_qty(body: QtyIn):
    quote = _load(body.quote_id)
    if not 1 <= body.qty <= 200:
        raise problem(422, "BAD_QTY", "Quantity must be between 1 and 200.", None)
    profile = resolved_profile(quote["session_id"])
    qty = {i["product_id"]: i["qty"] for i in quote["items"]}
    qty[body.product_id] = body.qty
    items = quotes.build_items([i["product_id"] for i in quote["items"]], profile, profile.segment,
                               quote["term_months"], qty)
    return _enrich(quotes.replace_items(body.quote_id, items), quote["session_id"])
