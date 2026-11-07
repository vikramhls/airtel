"""Orders + tracker (docs/07).

Stage dates come from config.REFERENCE_DATE plus a per-order demo clock -
never the wall clock. expected_activation = order date + KYC SLA + processing
+ max(install days of the lines), counted in working days (Sundays skipped).
"""
from __future__ import annotations

import json
import random
import string
from datetime import date, timedelta

from app import config, db
from app.services import catalogue, quotes, sessions
from app.services.kyc import service as kyc_service
from app.utils.dates import add_working_days, iso

STAGES = [
    ("placed", "Order placed"),
    ("kyc", "KYC verification"),
    ("processing", "Order processing"),
    ("scheduled", "Installation scheduled"),
    ("activated", "Service activated"),
]
BLOCKS = {
    "ADDRESS_PROOF_EXPIRED": {
        "stage": "kyc", "action": "Upload a recent electricity bill (less than 90 days old).",
        "fix_hint": "Your address proof is older than 90 days.", "link": "/kyc"},
    "ID_EXPIRED": {
        "stage": "kyc", "action": "Upload a valid signatory ID.", "fix_hint": "The signatory ID has expired.",
        "link": "/kyc"},
    "KYC_INCOMPLETE": {
        "stage": "kyc", "action": "Finish your KYC documents.", "fix_hint": "Some KYC checks are still failing.",
        "link": "/kyc"},
    "GSTIN_INACTIVE": {
        "stage": "kyc", "action": "Remove the products that need a GSTIN, or reactivate your GSTIN.",
        "fix_hint": "Your GSTIN is not active, and some products in this order need one.", "link": "/kyc"},
    "SITE_SURVEY": {
        "stage": "scheduled", "action": "A partner (Ravi) will visit for a site survey on {date}.",
        "fix_hint": "Fibre needs a quick site check before installation.", "link": None},
}


KYC_NOTE = {
    "instant": "Verified automatically: all checks passed",
    "manual": "A person reviews one warning: about 2 working days",
    "recheck": "Re-checked automatically once you fix it",
}


def _order_id() -> str:
    rng = random.SystemRandom()
    return "ORD-" + "".join(rng.choice(string.ascii_uppercase + string.digits) for _ in range(6))


def _load(order_id: str) -> tuple[dict, dict] | tuple[None, None]:
    row = db.one("SELECT * FROM orders WHERE id = ?", (order_id,))
    if not row:
        return None, None
    return row, json.loads(row["data_json"])


def _save(order_id: str, data: dict, status: str, eta: str) -> None:
    db.execute("UPDATE orders SET data_json = ?, status = ?, expected_activation_date = ? WHERE id = ?",
               (json.dumps(data), status, eta, order_id))


def _notify(order_id: str, body: str, at: date) -> None:
    db.execute("INSERT INTO notifications(order_id, channel, body, sent_at) VALUES(?,?,?,?)",
               (order_id, "whatsapp_sim", body, at.isoformat()))


def milestones(order_date: date, lines: list[dict], kyc_days: int) -> dict[str, date]:
    install = max((l["install_days"] for l in lines), default=0)
    kyc_done = add_working_days(order_date, kyc_days)
    processed = add_working_days(kyc_done, config.ORDER_PROCESSING_DAYS)
    activated = add_working_days(processed, install)
    return {"placed": order_date, "kyc": kyc_done, "processing": processed,
            "scheduled": processed, "activated": activated}


def _gst_required(lines: list[dict]) -> list[dict]:
    return [l for l in lines if (catalogue.get(l["product_id"]) and catalogue.get(l["product_id"]).requires_gstin)]


def create(session_id: str, quote_id: str) -> dict:
    quote = quotes.get(quote_id)
    if not quote or quote["session_id"] != session_id:
        raise KeyError("quote")
    session = sessions.get(session_id) or {}
    profile = sessions.load_profile(session_id)
    kyc = kyc_service.report(session_id) if kyc_service.consent.active(session_id) else None

    order_date = config.REFERENCE_DATE
    lines = [{"product_id": i["product_id"], "name": i["name"], "qty": i["qty"],
              "install_days": i["install_days"], "monthly": i["unit_price"] * i["qty"]} for i in quote["items"]]
    if kyc and kyc.get("state") == "green":
        kyc_mode, kyc_days = "instant", config.KYC_SLA_DAYS_INSTANT
    elif kyc and kyc.get("ready_for_order"):
        kyc_mode, kyc_days = "manual", config.KYC_SLA_DAYS_MANUAL
    else:
        kyc_mode, kyc_days = "recheck", config.KYC_SLA_DAYS_AUTO
    data = {"order_date": order_date.isoformat(), "clock_days": 0, "lines": lines, "kyc_days": kyc_days,
            "kyc_mode": kyc_mode, "block": None, "last_status": {}, "partner_task": None}

    status = (profile.gstin_status or "").lower()
    if status in {"cancelled", "suspended"} and _gst_required(lines):
        data["block"] = {"code": "GSTIN_INACTIVE", "products": [l["name"] for l in _gst_required(lines)]}
    elif not kyc or not kyc.get("ready_for_order"):
        nxt = (kyc or {}).get("next_action") or {}
        code = "ADDRESS_PROOF_EXPIRED" if nxt.get("code") == "ADDR_DATE_FRESH" else \
            "ID_EXPIRED" if nxt.get("code") == "ID_NOT_EXPIRED" else "KYC_INCOMPLETE"
        data["block"] = {"code": code, "detail": nxt.get("label")}

    order_id = _order_id()
    eta = milestones(order_date, lines, kyc_days)["activated"]
    db.execute(
        "INSERT INTO orders(id, session_id, quote_id, status, partner_id, created_at, expected_activation_date, data_json) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (order_id, session_id, quote_id, "placed", session.get("partner_id"), db.now(), eta.isoformat(), json.dumps(data)),
    )
    if kyc_days:
        _notify(order_id, f"Order {order_id} received. Next: we verify your documents (about {kyc_days} working day"
                          f"{'s' if kyc_days > 1 else ''}).", order_date)
    else:
        _notify(order_id, f"Order {order_id} received.", order_date)
    db.execute("INSERT INTO audit_log(at, actor, action, session_id, detail_masked) VALUES(?,?,?,?,?)",
               (db.now(), "owner", "order_placed", session_id, f"order={order_id} quote={quote_id}"))
    return get(order_id)


def _view(row: dict, data: dict) -> dict:
    order_date = date.fromisoformat(data["order_date"])
    today = order_date + timedelta(days=data["clock_days"])
    ms = milestones(order_date, data["lines"], data["kyc_days"])
    block = data.get("block")
    block_stage = BLOCKS[block["code"]]["stage"] if block else None
    stages, blocked_hit = [], False
    for key, label in STAGES:
        status = "done" if today >= ms[key] else "pending"
        if block and (key == block_stage or blocked_hit):
            if key == block_stage:
                status, blocked_hit = "blocked", True
            elif status == "done":
                status = "pending"
        stages.append({"key": key, "label": label, "status": status, "expected_date": iso(ms[key]),
                       "note": KYC_NOTE.get(data.get("kyc_mode", "")) if key == "kyc" else None})
    # first not-done, not-blocked stage after the last done is "in progress"
    for stage in stages:
        if stage["status"] == "pending":
            if not any(s["status"] == "blocked" for s in stages):
                stage["status"] = "in_progress"
            break
    current = next((s for s in stages if s["status"] in ("blocked", "in_progress")), stages[-1])
    pending_action = None
    if block:
        spec = BLOCKS[block["code"]]
        pending_action = {
            "code": block["code"],
            "action": spec["action"].format(date=iso(add_working_days(today, 1))),
            "fix_hint": block.get("detail") or spec["fix_hint"],
            "link": spec["link"],
            "products": block.get("products"),
            "options": (["remove_gst_products", "reactivate_gstin"] if block["code"] == "GSTIN_INACTIVE"
                        else ["recheck_kyc"] if spec["link"] else []),
        }
    install_start = ms["scheduled"]
    lines = [{**l, "install_date": iso(add_working_days(install_start, l["install_days"]))} for l in data["lines"]]
    notes = db.query("SELECT body, sent_at FROM notifications WHERE order_id = ? ORDER BY id", (row["id"],))
    status = "blocked" if block else ("activated" if stages[-1]["status"] == "done" else current["key"])
    return {
        "order_id": row["id"], "session_id": row["session_id"], "quote_id": row["quote_id"],
        "partner_id": row["partner_id"], "status": status, "order_date": data["order_date"],
        "today": iso(today), "clock_days": data["clock_days"],
        "expected_activation_date": iso(ms["activated"]), "paused": bool(block),
        "stages": stages, "current_stage": current["key"], "pending_action": pending_action,
        "lines": lines, "monthly_total": sum(l["monthly"] for l in data["lines"]),
        "notifications": notes, "partner_task": data.get("partner_task"),
        "eta_formula": "order date + KYC SLA + processing + max(install days), working days (Sundays skipped)",
    }


MESSAGES = {
    "kyc": "Documents verified. Next: we reserve your installation slot.",
    "processing": "Order processed. Installation booked for {date}, 10am-1pm.",
    "activated": "You're live! Your single support number: 1800-000-0000 (fictional).",
}


def _sync_notifications(order_id: str, view: dict, data: dict) -> None:
    last = data.get("last_status", {})
    today = date.fromisoformat(view["today"])
    for stage in view["stages"]:
        before, now = last.get(stage["key"]), stage["status"]
        if now == before:
            continue
        if now == "done" and stage["key"] in MESSAGES:
            _notify(order_id, MESSAGES[stage["key"]].format(date=view["expected_activation_date"]), today)
        if now == "blocked" and view["pending_action"]:
            _notify(order_id, "One thing needed: " + view["pending_action"]["action"], today)
        last[stage["key"]] = now
    data["last_status"] = last


def get(order_id: str) -> dict | None:
    row, data = _load(order_id)
    if not row:
        return None
    view = _view(row, data)
    before = json.dumps(data.get("last_status"))
    _sync_notifications(order_id, view, data)
    if json.dumps(data.get("last_status")) != before:
        _save(order_id, data, view["status"], view["expected_activation_date"])
        view = _view(row, data)
    return view


def advance(order_id: str, days: int | None = None, to_stage: str | None = None) -> dict | None:
    row, data = _load(order_id)
    if not row:
        return None
    if to_stage:
        ms = milestones(date.fromisoformat(data["order_date"]), data["lines"], data["kyc_days"])
        target = ms.get(to_stage)
        if target:
            data["clock_days"] = max(data["clock_days"], (target - date.fromisoformat(data["order_date"])).days)
    else:
        data["clock_days"] += max(0, int(days or 1))
    _save(order_id, data, row["status"], row["expected_activation_date"])
    return get(order_id)


def fail(order_id: str, reason: str) -> dict | None:
    row, data = _load(order_id)
    if not row:
        return None
    if reason not in BLOCKS:
        raise ValueError(reason)
    data["block"] = {"code": reason}
    _save(order_id, data, "blocked", row["expected_activation_date"])
    return get(order_id)


def resolve(order_id: str, action: str) -> dict | None:
    """Owner acted on the pending card: re-run KYC, or drop GSTIN-only products."""
    row, data = _load(order_id)
    if not row:
        return None
    block = data.get("block")
    if not block:
        return get(order_id)
    if action == "remove_gst_products":
        keep = [l for l in data["lines"] if l not in _gst_required(data["lines"])]
        removed = [l["name"] for l in data["lines"] if l not in keep]
        data["lines"] = keep
        data["block"] = None
        today = date.fromisoformat(data["order_date"]) + timedelta(days=data["clock_days"])
        _notify(order_id, "Updated order: removed " + ", ".join(removed) + ". New monthly total: Rs "
                + f"{sum(l['monthly'] for l in keep):,}.", today)
    elif action in ("recheck_kyc", "reactivate_gstin"):
        report = kyc_service.report(row["session_id"]) if kyc_service.consent.active(row["session_id"]) else None
        profile = sessions.load_profile(row["session_id"])
        gst_ok = (profile.gstin_status or "Active") == "Active" or not _gst_required(data["lines"])
        if block["code"] == "SITE_SURVEY" or (report and report.get("ready_for_order") and gst_ok):
            data["block"] = None
        elif report:
            data["block"]["detail"] = (report.get("next_action") or {}).get("label")
    _save(order_id, data, row["status"], row["expected_activation_date"])
    return get(order_id)


def need_help(order_id: str) -> dict | None:
    row, data = _load(order_id)
    if not row:
        return None
    data["partner_task"] = {"status": "open", "message": "A partner will call you today (simulated)."}
    sessions.add_handoff(row["session_id"], "tracker_need_help", {"order_id": order_id, "status": row["status"]})
    _save(order_id, data, row["status"], row["expected_activation_date"])
    return get(order_id)


def by_session(session_id: str) -> list[dict]:
    return [get(r["id"]) for r in db.query("SELECT id FROM orders WHERE session_id = ? ORDER BY created_at DESC",
                                          (session_id,))]
