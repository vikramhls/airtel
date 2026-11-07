"""Recompute every data claim the README / deck cites (AGENTS.md invariant 6).

Usage: python scripts/analyze_leads.py
Writes reports/insights.json and reports/insights.md.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app import config  # noqa: E402
from app.services import analytics  # noqa: E402


def main() -> None:
    ins = analytics.insights()
    funnel = analytics.funnel()
    sources = analytics.sources()
    segments = analytics.segments()
    drops = analytics.drop_reasons()
    df = analytics.frame()
    act = df[df["activated"]]
    ratio = (act["monthly_bundle_value_inr"] / act["monthly_telecom_spend_inr"])
    out = {"insights": ins, "funnel": funnel, "sources": sources, "segments": segments,
           "drop_reasons": drops, "bundle_to_spend_mean": round(float(ratio.mean()), 2)}
    (config.REPORTS_DIR / "insights.json").write_text(json.dumps(out, indent=2, default=float))

    f = [s["count"] for s in funnel["stages"]]
    lines = [
        "# Insights from smb_leads.csv (synthetic, Apr-Jun 2026)", "",
        "Every number here is recomputed by `scripts/analyze_leads.py`. Cite these, not hand-typed figures.", "",
        f"- **Funnel:** {' -> '.join(f'{x:,}' for x in f)} (lead to activation {funnel['lead_to_activation_pct']}%).",
        f"- **Spend vs bundle:** activated customers' bundle is a median **{ins['bundle_to_spend_median']}x** "
        f"(mean {out['bundle_to_spend_mean']}x) of what they spent before; **{ins['pct_paying_more_after']}%** pay more.",
        f"- **Price/competitor:** {ins['needs_to_quote_price_or_competitor_pct']}% of drops at Needs assessed -> Quote are "
        "'Price too high' or 'Competitor offered cheaper plan'.",
        f"- **GSTIN effect:** activation {ins['activation_pct_by_gstin'].get('Y')}% with GSTIN vs "
        f"{ins['activation_pct_by_gstin'].get('N')}% without; {ins['leads_without_gstin_pct']}% of leads have none.",
        f"- **Visits:** {ins['visit_never_happened']} leads dropped because a visit never happened; "
        f"{ins['unreachable']} were unreachable after 3 attempts.",
        f"- **Paperwork** is only {ins['paperwork_share_of_drops_pct']}% of all drops.",
        f"- **Speed:** {ins['avg_days_to_activate']} days lead-to-activation on average; CAC Rs {ins['cac_per_activation_inr']:,} per activation.",
        "", "## Status-chase calls vs churn and NPS (activated customers)", "",
        "| Follow-up calls | Customers | 6-month churn % | Avg NPS |", "|---|---|---|---|",
    ]
    for r in ins["chase_calls_vs_churn"]:
        lines.append(f"| {r['customer_follow_up_calls']} | {r['customers']} | {r['churn_pct']} | {r['nps']} |")
    lines += ["", "## Lead sources", "", "| Source | Leads | Activation % | Cost per lead | CAC per activation |", "|---|---|---|---|---|"]
    for s in sources:
        lines.append(f"| {s['source']} | {s['leads']} | {s['activation_pct']} | Rs {s['cost_per_lead_inr']:,} | "
                     f"Rs {s['cac_per_activation_inr']:,} |")
    lines += ["", "## Segments", "", "| Segment | Leads | Activation % | Avg bundle | Median spend before | Bundle/spend | Churn % | NPS |",
              "|---|---|---|---|---|---|---|---|"]
    for s in segments:
        lines.append(f"| {s['segment']} | {s['leads']} | {s['activation_pct']} | Rs {s['avg_bundle_inr']:,} | "
                     f"Rs {s['median_spend_today_inr']:,} | {s['median_bundle_to_spend']}x | {s['churn_6m_pct']} | {s['avg_nps']} |")
    lines += ["", "## Top drop reasons", ""]
    for r in drops["top3"]:
        lines.append(f"- {r['reason']}: {r['count']}")
    lines += ["", "## Activation by preferred language", ""]
    for k, v in sorted(ins["activation_pct_by_language"].items(), key=lambda kv: -kv[1]):
        lines.append(f"- {k}: {v}%")
    lines += ["", "## Corrections to docs/08", "",
              "- Channel-partner CAC per activation is **Rs 20,851** (docs said ~16.4k).",
              "- Website-form CAC per activation is **Rs 6,352**; Rs 274 is its cost *per lead* (docs said ~720).",
              "- WhatsApp campaign: Rs 112 per lead, Rs 4,026 per activation, 2.79% activation."]
    (config.REPORTS_DIR / "insights.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("[OK] reports/insights.md, reports/insights.json")


if __name__ == "__main__":
    main()
