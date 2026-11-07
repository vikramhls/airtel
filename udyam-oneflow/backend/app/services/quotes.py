"""Quotes: build line items from product IDs, persist, re-total on toggles."""
from __future__ import annotations

import json
import uuid

from app import db
from app.schemas import BusinessProfile
from app.services import catalogue, pricing


def build_items(
    product_ids: list[str],
    profile: BusinessProfile,
    segment: str,
    term_months: int,
    qty_overrides: dict[str, int] | None = None,
) -> list[dict]:
    qty_overrides = qty_overrides or {}
    items = []
    seen: set[str] = set()
    for pid in product_ids:
        product = catalogue.get(pid)
        if not product or product.id in seen:
            continue
        seen.add(product.id)
        line = pricing.build_line(
            product, profile, segment, term_months,
            qty=qty_overrides.get(product.id),
            why=f"Selected from your plan.",
        )
        items.append(line.model_dump())
    return _add_dependencies(items, product_ids, profile, segment, term_months, qty_overrides)


def _add_dependencies(
    items: list[dict], original_ids: list[str], profile: BusinessProfile,
    segment: str, term: int, qty_overrides: dict[str, int],
) -> list[dict]:
    from app.services.eligibility import check

    tier = profile.city_tier
    ids = {i["product_id"] for i in items}
    changes: list[dict] = []
    for item in list(items):
        product = catalogue.get(item["product_id"])
        if not product or not product.requires_one_of:
            continue
        if set(product.requires_one_of) & ids:
            continue
        options = [catalogue.get(pid) for pid in product.requires_one_of]
        options = [p for p in options if p and not check(p, profile, tier)["failed"]]
        if not options:
            continue
        base = min(options, key=lambda p: p.mid_price)
        if base.id in ids:
            continue
        line = pricing.build_line(
            base, profile, segment, term,
            qty=qty_overrides.get(base.id),
            why=f"Added because {product.name} needs a base connection.",
        )
        items.insert(0, line.model_dump())
        ids.add(base.id)
        changes.append({"added": base.id, "reason": f"{product.name} requires it"})
    return items


def save(session_id: str, rung: str, term_months: int, items: list[dict], trace: dict | None = None) -> dict:
    quote_id = f"Q-{uuid.uuid4().hex[:8].upper()}"
    t = pricing.totals([_to_model(i) for i in items])
    db.execute(
        "INSERT INTO quotes(id, session_id, rung, term_months, total_monthly_inr, total_setup_inr, "
        "created_at, trace_json, items_json) VALUES(?,?,?,?,?,?,?,?,?)",
        (quote_id, session_id, rung, term_months, t["total_monthly"], t["total_setup"],
         db.now(), json.dumps(trace or {}), json.dumps(items)),
    )
    return get(quote_id) or {}


def _to_model(item: dict):
    from app.schemas import LineItem

    return LineItem(**item)


def get(quote_id: str) -> dict | None:
    row = db.one("SELECT * FROM quotes WHERE id = ?", (quote_id,))
    if not row:
        return None
    items = json.loads(row["items_json"])
    t = pricing.totals([_to_model(i) for i in items])
    return {
        "quote_id": row["id"],
        "session_id": row["session_id"],
        "rung": row["rung"],
        "term_months": row["term_months"],
        "items": items,
        "addons": [],
        "trace": json.loads(row["trace_json"] or "{}"),
        **t,
    }


def replace_items(quote_id: str, items: list[dict]) -> dict | None:
    row = db.one("SELECT * FROM quotes WHERE id = ?", (quote_id,))
    if not row:
        return None
    t = pricing.totals([_to_model(i) for i in items])
    db.execute("UPDATE quotes SET items_json = ?, total_monthly_inr = ?, total_setup_inr = ? WHERE id = ?",
               (json.dumps(items), t["total_monthly"], t["total_setup"], quote_id))
    return get(quote_id)


def toggle(quote_id: str, product_id: str, on: bool, profile: BusinessProfile) -> dict | None:
    quote = get(quote_id)
    if not quote:
        return None
    product = catalogue.get(product_id)
    if not product:
        return quote
    items = list(quote["items"])
    ids = [i["product_id"] for i in items]
    changes: list[dict] = []
    segment = profile.segment or "micro"
    term = quote["term_months"]

    if on and product.id not in ids:
        line = pricing.build_line(product, profile, segment, term,
                                  why="Added by you on the quote screen.")
        items.append(line.model_dump())
        changes.append({"added": product.id, "reason": "you turned it on"})
        items = _add_dependencies(items, ids + [product.id], profile, segment, term, {})
        for item in items:
            if item["product_id"] not in ids and item["product_id"] != product.id:
                changes.append({"added": item["product_id"],
                                "reason": f"{product.name} needs a base connection: added {item['name']}"})
    elif not on and product.id in ids:
        removed = [product.id]
        # Remove dependents first, then try to keep the bundle valid.
        dependents = [
            i["product_id"] for i in items
            if product.id in (catalogue.get(i["product_id"]).requires_one_of or ())
        ]
        ids_to_remove = [product.id] + dependents
        items = [i for i in items if i["product_id"] not in ids_to_remove]
        changes.append({"removed": product.id, "reason": "you turned it off"})
        for dep in dependents:
            changes.append({"removed": dep, "reason": f"needs {product.name}"})

        # Any remaining product whose dependency is now unmet must be removed too.
        remaining_ids = {i["product_id"] for i in items}
        orphans = [
            i["product_id"] for i in items
            if catalogue.get(i["product_id"]).requires_one_of
            and not (set(catalogue.get(i["product_id"]).requires_one_of) & remaining_ids)
        ]
        if orphans:
            items = [i for i in items if i["product_id"] not in orphans]
            for orphan in orphans:
                changes.append({"removed": orphan, "reason": "no base connection left"})

    quote = replace_items(quote_id, items) or quote
    quote["changes"] = changes
    return quote
