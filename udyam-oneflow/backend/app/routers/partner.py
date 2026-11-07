"""Partner / sales cockpit + analytics + simulator (docs/08)."""
from __future__ import annotations

import secrets

from fastapi import APIRouter
from pydantic import BaseModel

from app import db
from app.routers.common import problem, resolved_profile
from app.services import analytics, propensity, sessions, simulator

router = APIRouter(tags=["partner"])


class LinkIn(BaseModel):
    partner_id: str
    lead_ref: str | None = None


class SimIn(BaseModel):
    recovery: dict[str, float] | None = None
    digital_cost_per_recovered_lead_inr: float | None = None
    days_saved_digital: float | None = 4
    multiplier: float | None = 1.0


@router.post("/partner/links")
def create_link(body: LinkIn):
    partner_id = body.partner_id.strip()[:40]
    if not partner_id:
        raise problem(422, "PARTNER_ID_REQUIRED", "Partner ID is required.", None)
    token = secrets.token_urlsafe(8)
    db.execute("INSERT INTO partner_links(partner_id, token, lead_ref, created_at) VALUES(?,?,?,?)",
               (partner_id, token, body.lead_ref, db.now()))
    return {"token": token, "url": f"/?partner={token}", "partner_id": partner_id}


@router.get("/partner/leads")
def leads(min_score: float = 0, segment: str | None = None, action: str | None = None,
          open_only: bool = True, limit: int = 50, offset: int = 0, sort: str = "value"):
    return propensity.leads_queue(min_score, segment, action, open_only, min(limit, 200), offset, sort)


@router.get("/partner/leads/{lead_id}")
def lead(lead_id: str):
    out = propensity.lead_detail(lead_id)
    if not out:
        raise problem(404, "LEAD_NOT_FOUND", "Lead not found.", None)
    return out


@router.get("/partner/handoffs")
def handoffs():
    """Advisor-could-not-close queue, each with a live score from the trained model."""
    out = []
    for h in sessions.handoffs():
        session = sessions.get(h["session_id"]) or {}
        score = None
        try:
            score = propensity.score_profile(resolved_profile(h["session_id"]),
                                             "Channel partner" if session.get("partner_id") else "Website form",
                                             session.get("lang") or "en")
        except Exception:
            score = None
        profile = sessions.load_profile(h["session_id"])
        summary = [
            f"{profile.business_type or 'Business'} in {profile.city or 'unknown city'}, "
            f"{profile.employees or '?'} people, {profile.sites or 1} site(s)",
            f"Needs: {', '.join(profile.needs) or 'not given'}; GST: "
            f"{profile.gstin_status or ('yes' if profile.has_gstin else 'no')}",
            f"Reason: {h['reason'].replace('_', ' ')}",
        ]
        out.append({**h, "summary": summary, "score": score, "partner_id": session.get("partner_id")})
    return out


@router.get("/partner/stats")
def partner_stats():
    rows = db.query("SELECT partner_id, COUNT(*) AS orders FROM orders WHERE partner_id IS NOT NULL GROUP BY partner_id")
    links = db.query("SELECT partner_id, COUNT(*) AS links FROM partner_links GROUP BY partner_id")
    return {"orders_by_partner": rows, "links_by_partner": links,
            "attribution_rule": "Any order from a session opened via a partner link is credited to that partner."}


@router.get("/analytics/funnel")
def funnel(segment: str | None = None):
    return analytics.funnel(segment)


@router.get("/analytics/dropreasons")
def dropreasons(segment: str | None = None, stage: str | None = None):
    return analytics.drop_reasons(segment, stage)


@router.get("/analytics/segments")
def segments():
    return analytics.segments()


@router.get("/analytics/sources")
def sources():
    return analytics.sources()


@router.get("/analytics/insights")
def insights():
    return analytics.insights()


@router.get("/analytics/model")
def model():
    return propensity.metrics()


@router.get("/simulate/defaults")
def sim_defaults():
    return {"recovery": simulator.DEFAULT_RECOVERY, "levers": simulator.LEVERS,
            "days_saved_digital": simulator.DEFAULT_ASSUMPTIONS["days_saved_digital"]}


@router.post("/simulate")
def simulate(body: SimIn):
    assumptions = {k: v for k, v in body.model_dump().items() if v is not None}
    result = simulator.simulate(assumptions)
    result["sensitivity"] = simulator.sensitivity(assumptions)
    return result
