"""The bundler: spend-anchored Start / Grow / Complete ladder + unlock paths.

Deterministic and pure. The LLM never reaches this module (AGENTS.md invariant 1).
"""
from __future__ import annotations

from app.dataio import segment_spend_median
from app.schemas import BusinessProfile, LineItem, RecommendationResult, Rung, UnlockPath
from app.services import catalogue, pricing, unlock
from app.services.eligibility import check
from app.services.segmenter import infer_segment, resolve_tier

SEG_TEMPLATES: dict[str, dict[str, list[str]]] = {
    "micro": {
        "Start": ["conn", "mobile"],
        "Grow": ["P19", "P15", "P14"],
        "Complete": ["P23", "P22", "P18"],
    },
    "prof": {
        "Start": ["conn", "mobile", "P16"],
        "Grow": ["P20", "P17"],
        "Complete": ["P09", "P11", "P12"],
    },
    "multi": {
        "Start": ["conn", "mobile"],
        "Grow": ["P09", "P23", "P19"],
        "Complete": ["P10", "P12", "P13"],
    },
    "mfg": {
        "Start": ["conn", "mobile", "P20"],
        "Grow": ["P21", "P09"],
        "Complete": ["P05", "P06", "P24"],
    },
}

NEED_PRODUCTS: dict[str, list[str]] = {
    "billing_pos": ["P19"],
    "whatsapp": ["P15"],
    "sms": ["P14"],
    "email_cloud": ["P16"],
    "cctv": ["P23"],
    "telephony": ["P12"],
    "wifi": ["P22"],
    "iot": ["P24"],
    "tracking": ["P25"],
    "website": ["P18"],
}

NEED_RUNG = {
    "internet": 1, "mobile": 1, "email_cloud": 1,
    "billing_pos": 2, "whatsapp": 2, "sms": 2, "security": 2, "wifi": 2, "website": 2,
    "cctv": 3, "telephony": 3, "iot": 3, "tracking": 3,
    "requested": 2, "dependency": 1,
}

NEED_LABEL = {
    "internet": "Your business internet",
    "mobile": "Mobile lines for your team",
    "billing_pos": "Billing and POS at the counter",
    "whatsapp": "WhatsApp Business for customer updates",
    "sms": "Alerts and promotions by SMS",
    "email_cloud": "Business email on your own domain",
    "security": "Security for your devices",
    "cctv": "Cloud CCTV you can check on your phone",
    "telephony": "Cloud telephony with IVR",
    "wifi": "Managed Wi-Fi for staff and customers",
    "iot": "Machine monitoring",
    "tracking": "Fleet tracking",
    "website": "Website and domain",
    "requested": "You asked for this",
    "dependency": "Base connection required by another service",
}

LABELS = ["Start", "Grow", "Complete"]


def rupees(value: int) -> str:
    return f"\u20b9{value:,}"


def choose_connectivity(profile: BusinessProfile, segment: str) -> str:
    if segment == "multi":
        return "P02"
    if segment == "mfg":
        return "P02"
    if profile.fibre_available is False:
        return "P04"
    if (profile.employees or 0) > 10:
        return "P02"
    return "P01"


def choose_mobile(profile: BusinessProfile, segment: str) -> str:
    if segment in {"multi", "mfg"} and (profile.employees or 0) >= 25:
        return "P08"
    return "P07"


def _security_products(segment: str) -> list[str]:
    return ["P21"] if segment in {"mfg", "multi"} else ["P20"]


def _wanted(profile: BusinessProfile, segment: str, tier: int | None) -> tuple[dict[str, str], dict[str, dict]]:
    """product_id -> need label, plus per-product rule results."""
    needs = list(dict.fromkeys(profile.needs))
    unspecified = not needs

    requested = [catalogue.get(pid) for pid in profile.requested_products]
    requested = [p for p in requested if p]

    def eligible(p) -> bool:
        return not check(p, profile, tier)["failed"]

    conn = choose_connectivity(profile, segment)
    req_conn = next(
        (p for p in requested if p.category == "Connectivity" and p.unit.lower() == "per site"
         and not p.requires_one_of and eligible(p)),   # failover / SD-WAN ride on a base link
        None,
    )
    if req_conn:
        conn = req_conn.id
    mobile = choose_mobile(profile, segment)
    req_mobile = next(
        (p for p in requested if p.category == "Connectivity" and p.unit.lower() == "per line" and eligible(p)),
        None,
    )
    if req_mobile:
        mobile = req_mobile.id

    wanted: dict[str, str] = {}
    if unspecified or "internet" in needs:
        wanted[conn] = "internet"
    if unspecified or "mobile" in needs:
        wanted[mobile] = "mobile"
    for need in needs:
        if need == "security":
            ids = _security_products(segment)
        else:
            ids = NEED_PRODUCTS.get(need, [])
        for pid in ids:
            wanted.setdefault(pid, need)
    for p in requested:
        wanted.setdefault(p.id, "requested")

    results = {pid: check(catalogue.get(pid), profile, tier) for pid in wanted}  # type: ignore[arg-type]
    return wanted, results


def _levels(segment: str, conn: str, mobile: str) -> dict[str, int]:
    levels: dict[str, int] = {}
    for index, label in enumerate(LABELS, start=1):
        for token in SEG_TEMPLATES[segment][label]:
            pid = conn if token == "conn" else mobile if token == "mobile" else token
            levels.setdefault(pid, index)
    return levels


def _why(need: str, product, rules_passed: list[str]) -> str:
    label = NEED_LABEL.get(need, "Needed for your business")
    if need == "requested":
        return f"You asked for this. {product.description}"
    if need == "dependency":
        return "Added because another service needs a base internet connection."
    return f"{label}. {product.description}"


def _need_for(pid: str) -> str:
    for need, ids in NEED_PRODUCTS.items():
        if pid in ids:
            return need
    return "optional"


def _addon_why(segment: str) -> str:
    return f"Optional for a {segment} business - not needed for what you told us."


def _rung_why(label: str, items: list[LineItem], added: list[LineItem], ratio: float | None, over: int | None) -> str:
    names = ", ".join(i.name for i in items)
    if label == "Start":
        text = f"The essentials: {names}."
        if ratio is not None:
            if ratio <= 1.5:
                text += f" Starts close to what you pay today ({ratio}x)."
            else:
                text += f" This is {ratio}x what you pay today because it adds services you did not have."
    elif label == "Grow":
        text = "Adds " + (", ".join(i.name for i in added) or "more services") + " to what Start includes."
    else:
        text = "Everything in one bill: " + names + "."
    if over:
        text += f" It is over your budget by {rupees(over)}."
    return text


ESSENTIAL_NEEDS = {"internet", "mobile", "dependency"}


def _budget_advice(start: Rung, budget: int | None, included: dict[str, str]) -> dict | None:
    """Never hide an overage: say by how much, and what to defer to fit."""
    if not budget or start.total_monthly <= budget:
        return None
    over = start.total_monthly - budget
    droppable = sorted(
        (i for i in start.items if included.get(i.product_id) not in ESSENTIAL_NEEDS),
        key=lambda i: -(i.unit_price * i.qty),
    )
    drop, remaining = [], start.total_monthly
    for item in droppable:
        if remaining <= budget:
            break
        drop.append({"product_id": item.product_id, "name": item.name, "saves": item.unit_price * item.qty})
        remaining -= item.unit_price * item.qty
    fits = remaining <= budget
    note = f"Start is {rupees(start.total_monthly)}/month, over your {rupees(budget)} budget by {rupees(over)}."
    if drop:
        note += " Defer " + ", ".join(d["name"] for d in drop) + f" to bring it to {rupees(remaining)}/month."
    if not fits:
        note += " Even the cheapest working connection costs more than the budget, so this is the lowest price we can offer."
    return {"budget": budget, "start_total": start.total_monthly, "over_by": over,
            "drop": drop, "after_drop": remaining, "fits_after_drop": fits, "note": note}


def recommend(profile: BusinessProfile, term_months: int | None = None) -> RecommendationResult:
    segment = profile.segment or infer_segment(profile.business_type, profile.sites)
    tier = resolve_tier(profile)
    term = term_months or 12

    if not profile.city:
        return RecommendationResult(
            available=False,
            notice="Which city is your business in? We sell in 22 cities today.",
            segment=segment,  # type: ignore[arg-type]
            handoff=False,
            trace={"reason": "city_unknown"},
        )
    if tier is None:
        return RecommendationResult(
            available=False,
            notice=(
                f"We do not sell in {profile.city} yet. Your details are saved and a partner can "
                "help you plan a move when we launch there."
            ),
            segment=segment,  # type: ignore[arg-type]
            city_tier=None,
            handoff=True,
            trace={"reason": "city_not_served", "city": profile.city},
        )
    if segment is None:
        return RecommendationResult(
            available=False,
            notice="Tell me what your business does (for example a kirana shop or a dental clinic) so I can size the plan.",
            trace={"reason": "segment_unknown"},
        )

    prof = profile.model_copy(update={"segment": segment, "city_tier": tier})

    anchor = prof.current_spend_inr or segment_spend_median().get(segment, 1000)
    wants, results = _wanted(prof, segment, tier)

    conn = choose_connectivity(prof, segment)
    mobile = choose_mobile(prof, segment)
    for pid, need in wants.items():
        if need == "internet":
            conn = pid
        if need == "mobile":
            mobile = pid

    included: dict[str, str] = {pid: need for pid, need in wants.items() if not results[pid]["failed"]}

    # Over budget? Use the cheapest eligible connection for the same need (S10).
    budget_swap = None
    if prof.budget_inr and conn in included and prof.fibre_available is not True:
        estimate = sum(catalogue.get(p).mid_price for p in included)
        cheapest = min(
            (p for p in catalogue.all_products()
             if p.category == "Connectivity" and p.unit == "per site" and not p.requires_one_of
             and not check(p, prof, tier)["failed"]),
            key=lambda p: pricing.unit_price(p, term),
        )
        if estimate > prof.budget_inr and cheapest.id != conn:
            included[cheapest.id] = included.pop(conn)
            results[cheapest.id] = check(cheapest, prof, tier)
            budget_swap = {"from": conn, "to": cheapest.id, "reason": "over budget: cheapest eligible connection"}
            conn = cheapest.id

    # Dependency resolution: auto-add the cheapest eligible base connection.
    auto_added: list[dict] = []
    for pid in sorted(included):
        product = catalogue.get(pid)
        if not product or not product.requires_one_of:
            continue
        if set(product.requires_one_of) & set(included):
            continue
        base = None
        if conn in product.requires_one_of and conn not in included:
            base = catalogue.get(conn)
        if base is None:
            options = []
            for candidate_id in product.requires_one_of:
                candidate = catalogue.get(candidate_id)
                if candidate and not check(candidate, prof, tier)["failed"]:
                    options.append(candidate)
            base = min(options, key=lambda p: p.mid_price) if options else None
        if base is None:
            results[pid]["failed"].append("dependency")
            included.pop(pid, None)
            continue
        included[base.id] = "dependency"
        results[base.id] = check(base, prof, tier)
        auto_added.append({
            "product": base.id,
            "name": base.name,
            "reason": f"{product.name} requires one of {'|'.join(product.requires_one_of)}",
        })
        if pid not in product.requires_one_of and base.requires_one_of and not (set(base.requires_one_of) & set(included)):
            pass

    # Template suggestions for Grow / Complete: eligible products the segment
    # typically adds. They are priced, labelled "suggested" and toggleable -
    # never silently added to Start (docs/04 section 4).
    levels = _levels(segment, conn, mobile)
    suggestions: dict[int, list[str]] = {2: [], 3: []}
    for pid, level in levels.items():
        if level < 2 or pid in included or pid in wants:
            continue
        product = catalogue.get(pid)
        if not product:
            continue
        res = check(product, prof, tier)
        results.setdefault(pid, res)
        if not res["failed"]:
            suggestions[level].append(pid)

    # ---- Unlock paths -------------------------------------------------------
    blocked_ids = [pid for pid, res in results.items() if res["failed"]]
    gstin_blocked = [pid for pid in blocked_ids if any(r.startswith("gstin_") for r in results[pid]["failed"])]
    blocked: list[UnlockPath] = []
    for pid in blocked_ids:
        product = catalogue.get(pid)
        if not product:
            continue
        blocked.append(
            unlock.build(
                product, results[pid], prof, tier,
                needed=wants.get(pid) not in {None, "template"},
                related_blocked=max(len(gstin_blocked) - 1, 0),
            )
        )
    blocked.sort(key=lambda u: (not u.needed, u.failed_rules[0] if u.failed_rules else "", u.adds_per_month))

    # ---- Rungs --------------------------------------------------------------
    def line_for(pid: str, need: str, is_addon: bool = False) -> LineItem:
        product = catalogue.get(pid)
        if pid not in results:
            results[pid] = check(product, prof, tier)
        why = _addon_why(segment) if is_addon else _why(need, product, results[pid]["passed"])
        current = prof.current_internet
        if need == "internet" and current and current not in ("None", "Leased line"):
            why = f"Upgrade from your {current.lower()}. " + why
        return pricing.build_line(
            product, prof, segment, term,
            is_addon=is_addon,
            why=why,
            rules_passed=results[pid]["passed"],
        )

    def with_bases(pids: list[str]) -> list[str]:
        """Suggested products may need a base link the owner did not ask for."""
        out = list(pids)
        for pid in list(out):
            product = catalogue.get(pid)
            if not product.requires_one_of or set(product.requires_one_of) & set(out):
                continue
            options = [catalogue.get(c) for c in product.requires_one_of]
            options = [p for p in options if p and not check(p, prof, tier)["failed"]]
            if not options:
                out.remove(pid)
                continue
            base = catalogue.get(conn) if conn in product.requires_one_of and catalogue.get(conn) in options \
                else min(options, key=lambda p: p.mid_price)
            out.insert(0, base.id)
            results.setdefault(base.id, check(base, prof, tier))
        return out

    def order_key(pid: str):
        p = catalogue.get(pid)
        return (0 if pid in included else 1, p.category, p.mid_price)

    previous: list[str] = []
    rung_pids: list[list[str]] = []
    rung_items: list[list[LineItem]] = []
    core = list(included)
    for index, label in enumerate(LABELS, start=1):
        extra = [pid for level in range(2, index + 1) for pid in suggestions.get(level, [])]
        pids = with_bases(core + [p for p in extra if p not in core])
        pids = sorted(dict.fromkeys(pids), key=order_key)
        rung_pids.append(pids)
        items = [
            line_for(pid, included[pid]) if pid in included else line_for(pid, _need_for(pid), is_addon=True)
            for pid in pids
        ]
        if index > 1:
            for item in items:
                if item.is_addon:
                    item.why = f"Suggested for {label}: {catalogue.get(item.product_id).description}"
        rung_items.append(items)

    ladder: list[Rung] = []
    for index, label in enumerate(LABELS, start=1):
        items = rung_items[index - 1]
        pids = rung_pids[index - 1]
        later = [p for lvl in range(index + 1, 4) for p in suggestions.get(lvl, []) if p not in pids]
        addons = [line_for(pid, _need_for(pid), is_addon=True) for pid in later]

        t = pricing.totals(items)
        ratio = round(t["total_monthly"] / anchor, 2) if anchor and t["total_monthly"] else None
        over = (t["total_monthly"] - prof.budget_inr) if prof.budget_inr and t["total_monthly"] > prof.budget_inr else None
        added = [i for i in items if i.product_id not in previous]
        ladder.append(
            Rung(
                label=label,  # type: ignore[arg-type]
                items=items,
                addons=addons,
                total_monthly=t["total_monthly"],
                total_monthly_range=t["total_monthly_range"],
                total_setup=t["total_setup"],
                contract_months=t["contract_months"],
                vs_current_spend=ratio,
                install_days=t["install_days"],
                why=_rung_why(label, items, added, ratio, over),
                over_budget_by=over,
            )
        )
        previous = pids
    budget_advice = _budget_advice(ladder[0], prof.budget_inr, included)

    trace_rules = [
        {"product": pid, "passed": res["passed"], "failed": res["failed"]}
        for pid, res in sorted(results.items())
    ]
    trace = {
        "segment": segment,
        "city_tier": tier,
        "rules": trace_rules,
        "auto_added": auto_added,
        "blocked": [
            {"product": u.product_id, "blocked_by": u.blocked_by, "failed": u.failed_rules}
            for u in blocked
        ],
        "pricing": {"policy": "12m=mid, 24m=min, <12m=max", "source": "product_catalogue.csv", "term": term},
        "anchor": anchor,
        "ratio": ladder[0].vs_current_spend if ladder else None,
        "install_days": ladder[0].install_days if ladder else None,
        "needs": list(prof.needs),
        "requested": list(prof.requested_products),
    }
    if auto_added:
        trace["auto_added_note"] = "A needed service requires a base connection, so it was added once."
    if budget_swap:
        trace["budget_swap"] = budget_swap
    trace["suggested"] = {LABELS[k - 1]: v for k, v in suggestions.items()}

    handoff = (not ladder[0].items) or (prof.sites or 1) > 10
    return RecommendationResult(
        budget_advice=budget_advice,
        available=True,
        segment=segment,  # type: ignore[arg-type]
        city_tier=tier,
        ladder=ladder,
        blocked=blocked,
        unlock_summary=unlock.summary(prof, tier, segment),
        anchor_spend=anchor,
        trace=trace,
        handoff=handoff,
    )


def product_ids_for(rung: Rung) -> list[str]:
    return [i.product_id for i in rung.items]


def explain_blocked_short(blocked: list[UnlockPath], limit: int = 3) -> str:
    if not blocked:
        return ""
    parts = [f"{u.name} ({u.blocked_by.replace('_', ' ')})" for u in blocked[:limit]]
    return "; ".join(parts)
