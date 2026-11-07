"""Funnel / drop-reason / segment / source aggregates from smb_leads.csv (docs/08 section 6)."""
from __future__ import annotations

from functools import lru_cache

import pandas as pd

from app.dataio import SEGMENT_KEY, leads_frame

STAGES = ["Lead", "Contacted", "Needs assessed", "Quote accepted", "KYC complete", "Activated"]


@lru_cache(maxsize=1)
def frame() -> pd.DataFrame:
    df = leads_frame().copy()
    for col in ("monthly_telecom_spend_inr", "monthly_bundle_value_inr", "acquisition_cost_inr",
                "customer_follow_up_calls", "nps_score", "days_lead_to_activation", "employee_count", "num_sites"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["stage_idx"] = df["stage_reached"].map({s: i for i, s in enumerate(STAGES)})
    df["activated"] = df["outcome"] == "Activated"
    df["seg"] = df["segment"].map(SEGMENT_KEY)
    return df


def _filter(segment: str | None) -> pd.DataFrame:
    df = frame()
    if segment:
        key = SEGMENT_KEY.get(segment, segment)
        df = df[df["seg"] == key]
    return df


def funnel(segment: str | None = None) -> dict:
    df = _filter(segment)
    counts = [int((df["stage_idx"] >= i).sum()) for i in range(len(STAGES))]
    rows = []
    for i, stage in enumerate(STAGES):
        rows.append({"stage": stage, "count": counts[i],
                     "pct_of_previous": None if i == 0 else round(100 * counts[i] / counts[i - 1], 1) if counts[i - 1] else 0,
                     "dropped_here": int(((df["stage_idx"] == i) & ~df["activated"]).sum())})
    act = df[df["activated"]]
    return {"segment": segment, "stages": rows,
            "lead_to_activation_pct": round(100 * counts[-1] / counts[0], 2) if counts[0] else 0,
            "avg_days_to_activate": round(float(act["days_lead_to_activation"].mean()), 1) if len(act) else None,
            "avg_follow_up_calls": round(float(act["customer_follow_up_calls"].mean()), 1) if len(act) else None,
            "cac_per_activation_inr": round(float(df["acquisition_cost_inr"].sum() / max(len(act), 1)))}


def drop_reasons(segment: str | None = None, stage: str | None = None) -> dict:
    df = _filter(segment)
    df = df[~df["activated"]]
    if stage:
        df = df[df["stage_reached"] == stage]
    grouped = df.groupby(["stage_reached", "drop_reason"]).size().reset_index(name="count")
    grouped["stage_order"] = grouped["stage_reached"].map({s: i for i, s in enumerate(STAGES)})
    grouped = grouped.sort_values(["stage_order", "count"], ascending=[True, False])
    total = int(len(df))
    top = df["drop_reason"].value_counts().head(3)
    return {"total_dropped": total,
            "rows": [{"stage": r.stage_reached, "reason": r.drop_reason, "count": int(r.count),
                      "pct_of_drops": round(100 * r.count / total, 1)} for r in grouped.itertuples()],
            "top3": [{"reason": k, "count": int(v)} for k, v in top.items()]}


def segments() -> list[dict]:
    df = frame()
    out = []
    for key, grp in df.groupby("segment"):
        act = grp[grp["activated"]]
        ratio = (act["monthly_bundle_value_inr"] / act["monthly_telecom_spend_inr"]).median() if len(act) else None
        out.append({"segment": key, "key": SEGMENT_KEY.get(key), "leads": int(len(grp)),
                    "activation_pct": round(100 * len(act) / len(grp), 2),
                    "avg_bundle_inr": round(float(act["monthly_bundle_value_inr"].mean())) if len(act) else None,
                    "median_spend_today_inr": round(float(act["monthly_telecom_spend_inr"].median())) if len(act) else None,
                    "median_bundle_to_spend": round(float(ratio), 2) if ratio is not None else None,
                    "churn_6m_pct": round(100 * float((act["churned_within_6_months"] == "Y").mean()), 1) if len(act) else None,
                    "avg_nps": round(float(act["nps_score"].mean()), 1) if len(act) else None})
    return out


def sources() -> list[dict]:
    df = frame()
    out = []
    for src, grp in df.groupby("lead_source"):
        act = int(grp["activated"].sum())
        cost = float(grp["acquisition_cost_inr"].sum())
        out.append({"source": src, "leads": int(len(grp)), "activated": act,
                    "activation_pct": round(100 * act / len(grp), 2),
                    "cost_per_lead_inr": round(cost / len(grp)),
                    "cac_per_activation_inr": round(cost / act) if act else None})
    return sorted(out, key=lambda r: -r["leads"])


def insights() -> dict:
    """The claims the README/deck cite, recomputed from data (AGENTS.md invariant 6)."""
    df = frame()
    act = df[df["activated"]]
    gst = {flag: round(100 * float(g["activated"].mean()), 1) for flag, g in df.groupby("has_gstin")}
    ratio = act["monthly_bundle_value_inr"] / act["monthly_telecom_spend_inr"]
    chases = act.groupby("customer_follow_up_calls").agg(
        customers=("lead_id", "size"),
        churn_pct=("churned_within_6_months", lambda s: round(100 * float((s == "Y").mean()), 1)),
        nps=("nps_score", lambda s: round(float(s.mean()), 1)))
    nq = df[df["stage_reached"] == "Needs assessed"]["drop_reason"].value_counts()
    price_comp = int(nq.get("Price too high", 0) + nq.get("Competitor offered cheaper plan", 0))
    lang = {k: round(100 * float(g["activated"].mean()), 1) for k, g in df.groupby("preferred_language")}
    paperwork = {"Missing GST or Udyam document", "Found paperwork too long", "Document details did not match",
                 "Authorised signatory not available"}
    drops = df[~df["activated"]]
    return {
        "funnel": [s["count"] for s in funnel()["stages"]],
        "activation_pct_by_gstin": gst,
        "leads_without_gstin_pct": round(100 * float((df["has_gstin"] == "N").mean()), 1),
        "bundle_to_spend_median": round(float(ratio.median()), 2),
        "pct_paying_more_after": round(100 * float((ratio > 1).mean()), 1),
        "needs_to_quote_price_or_competitor_pct": round(100 * price_comp / max(int(nq.sum()), 1), 1),
        "visit_never_happened": int(drops["drop_reason"].isin(["Owner had no time for a visit",
                                                               "Visit not scheduled by sales"]).sum()),
        "unreachable": int((drops["drop_reason"] == "Unreachable after 3 attempts").sum()),
        "paperwork_share_of_drops_pct": round(100 * float(drops["drop_reason"].isin(paperwork).mean()), 1),
        "chase_calls_vs_churn": chases.reset_index().to_dict("records"),
        "activation_pct_by_language": lang,
        "avg_days_to_activate": round(float(act["days_lead_to_activation"].mean()), 1),
        "cac_per_activation_inr": round(float(df["acquisition_cost_inr"].sum() / len(act))),
    }
