"""What-if simulator (docs/08 section 4). A projection under stated, editable assumptions.

Method (deterministic expected values, no random draws):
  for every dropped lead with reason r at stage S, a fraction recover[r] is
  recovered; a recovered lead moves to stage S+1 and then reaches each later
  stage with the conversion its *segment* actually shows from S+1 onward.
With every recovery rate at 0 the output equals the observed funnel exactly.
"""
from __future__ import annotations

from app.services.analytics import STAGES, frame

DEFAULT_RECOVERY = {
    "Owner had no time for a visit": 0.30, "Visit not scheduled by sales": 0.30,
    "Unreachable after 3 attempts": 0.10, "Wrong or invalid number": 0.0,
    "Quote took too long to arrive": 0.50, "Quote too complex to understand": 0.50,
    "Price too high": 0.20, "Competitor offered cheaper plan": 0.10,
    "Locked in with current provider": 0.05, "Decided to wait": 0.05,
    "Only wanted a mobile plan": 0.20, "Not interested on first call": 0.0,
    "Missing GST or Udyam document": 0.50, "Found paperwork too long": 0.50,
    "Document details did not match": 0.50, "Authorised signatory not available": 0.50,
    "Installation delayed beyond 21 days": 0.15, "Site not feasible for fibre": 0.15,
    "First payment failed": 0.15, "Customer cancelled before install": 0.15,
}
LEVERS = {
    "Owner had no time for a visit": "async link, no visit", "Visit not scheduled by sales": "async link, no visit",
    "Unreachable after 3 attempts": "WhatsApp/SMS link instead of calls", "Wrong or invalid number": "none",
    "Quote took too long to arrive": "instant ladder quote", "Quote too complex to understand": "instant ladder quote",
    "Price too high": "spend-anchored Start rung", "Competitor offered cheaper plan": "Start rung + single bill",
    "Locked in with current provider": "scheduled switch, parked lead", "Decided to wait": "scheduled switch, parked lead",
    "Only wanted a mobile plan": "mobile-only Start rung", "Not interested on first call": "none",
    "Missing GST or Udyam document": "Smart KYC + unlock paths", "Found paperwork too long": "Smart KYC",
    "Document details did not match": "Smart KYC fix hints", "Authorised signatory not available": "e-sign / async",
    "Installation delayed beyond 21 days": "tracker + 5G FWA alternative", "Site not feasible for fibre": "5G FWA alternative",
    "First payment failed": "tracker reminders", "Customer cancelled before install": "tracker, fewer chases",
}
DEFAULT_ASSUMPTIONS = {
    "recovery": DEFAULT_RECOVERY,
    "digital_cost_per_recovered_lead_inr": None,   # None -> dataset's Website-form cost per lead
    "days_saved_digital": 4,
    "multiplier": 1.0,
}


def _conversion_tables(df):
    """P(reach stage k | reached stage j) per segment."""
    tables = {}
    for seg, grp in df.groupby("segment"):
        reached = [int((grp["stage_idx"] >= i).sum()) for i in range(len(STAGES))]
        tables[seg] = reached
    return tables


def simulate(assumptions: dict | None = None) -> dict:
    a = {**DEFAULT_ASSUMPTIONS, **(assumptions or {})}
    recovery = {**DEFAULT_RECOVERY, **(a.get("recovery") or {})}
    mult = float(a.get("multiplier") or 1.0)
    df = frame()
    tables = _conversion_tables(df)
    n = len(STAGES)

    baseline = [float((df["stage_idx"] >= i).sum()) for i in range(n)]
    projected = list(baseline)
    recovered_total = 0.0
    by_reason = []
    dropped = df[~df["activated"]]
    for (seg, stage_idx, reason), grp in dropped.groupby(["segment", "stage_idx", "drop_reason"]):
        rate = min(1.0, max(0.0, float(recovery.get(reason, 0.0)) * mult))
        if rate == 0:
            continue
        recovered = rate * len(grp)
        recovered_total += recovered
        reached = tables[seg]
        nxt = int(stage_idx) + 1
        gained_act = 0.0
        for k in range(nxt, n):
            share = reached[k] / reached[nxt] if reached[nxt] else 0.0
            projected[k] += recovered * share
            if k == n - 1:
                gained_act = recovered * share
        by_reason.append({"reason": reason, "segment": seg, "stage": STAGES[int(stage_idx)], "leads": int(len(grp)),
                          "rate": rate, "recovered": recovered, "extra_activations": gained_act})

    # Aggregate per reason for display
    agg: dict[str, dict] = {}
    for r in by_reason:
        row = agg.setdefault(r["reason"], {"reason": r["reason"], "lever": LEVERS.get(r["reason"], ""),
                                           "stage": r["stage"], "leads": 0, "rate": r["rate"],
                                           "recovered": 0.0, "extra_activations": 0.0})
        row["leads"] += r["leads"]
        row["recovered"] += r["recovered"]
        row["extra_activations"] += r["extra_activations"]
    reasons = sorted(agg.values(), key=lambda r: -r["extra_activations"])
    for r in reasons:
        r["recovered"] = round(r["recovered"], 1)
        r["extra_activations"] = round(r["extra_activations"], 1)

    web = df[df["lead_source"] == "Website form"]
    digital_cost = a.get("digital_cost_per_recovered_lead_inr")
    if digital_cost is None:
        digital_cost = float(web["acquisition_cost_inr"].sum() / len(web))
    total_cost = float(df["acquisition_cost_inr"].sum())
    base_act, proj_act = baseline[-1], projected[-1]
    proj_cost = total_cost + recovered_total * float(digital_cost)
    act = df[df["activated"]]
    base_days = float(act["days_lead_to_activation"].mean())

    def pct(x, y):
        return round(100 * x / y, 2) if y else 0.0

    return {
        "assumptions": {"recovery": recovery, "multiplier": mult, "digital_cost_per_recovered_lead_inr": round(digital_cost),
                        "days_saved_digital": a.get("days_saved_digital")},
        "baseline": {"funnel": [round(x) for x in baseline], "activations": round(base_act),
                     "lead_to_activation_pct": pct(base_act, baseline[0]),
                     "assessed_to_quote_pct": pct(baseline[3], baseline[2]),
                     "cac_inr": round(total_cost / base_act), "avg_days_to_activate": round(base_days, 1)},
        "projected": {"funnel": [round(x, 1) for x in projected], "activations": round(proj_act, 1),
                      "lead_to_activation_pct": pct(proj_act, projected[0]),
                      "assessed_to_quote_pct": pct(projected[3], projected[2]),
                      "cac_inr": round(proj_cost / proj_act),
                      "avg_days_to_activate": round(base_days - float(a.get("days_saved_digital") or 0), 1)},
        "stages": STAGES,
        "recovered_leads": round(recovered_total, 1),
        "by_reason": reasons,
        "formulas": {
            "recovered": "dropped leads x recovery rate (per drop reason)",
            "extra activations": "recovered x P(activated | reached next stage, same segment)",
            "projected CAC": "(observed total acquisition cost + recovered leads x digital cost per lead) / projected activations",
            "avg days": "observed average - assumed days saved by the digital path",
        },
        "disclaimer": "Projection under stated assumptions; recovery rates are editable placeholders, not facts.",
    }


def sensitivity(assumptions: dict | None = None) -> dict:
    out = {}
    for label, mult in (("low", 0.5), ("base", 1.0), ("high", 1.5)):
        res = simulate({**(assumptions or {}), "multiplier": mult * float((assumptions or {}).get("multiplier") or 1.0)})
        out[label] = {"activations": res["projected"]["activations"], "cac_inr": res["projected"]["cac_inr"],
                      "lead_to_activation_pct": res["projected"]["lead_to_activation_pct"]}
    return out
