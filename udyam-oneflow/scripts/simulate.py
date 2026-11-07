"""What-if projection under the default (editable) assumptions, with low/base/high sensitivity.

Usage: python scripts/simulate.py
Writes reports/simulation.json and reports/simulation.md. Projection, not a claim.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app import config  # noqa: E402
from app.services import simulator  # noqa: E402

zero = simulator.simulate({"recovery": {k: 0 for k in simulator.DEFAULT_RECOVERY}})
assert [round(x) for x in zero["projected"]["funnel"]] == [5000, 3406, 1974, 861, 588, 368], "baseline check failed"
base = simulator.simulate()
sens = simulator.sensitivity()
(config.REPORTS_DIR / "simulation.json").write_text(json.dumps({"base": base, "sensitivity": sens}, indent=2))

b, p = base["baseline"], base["projected"]
lines = [
    "# OneFlow what-if projection (under stated assumptions)", "",
    "Zero-recovery check: reproduces the observed funnel exactly (5000/3406/1974/861/588/368).", "",
    "| Metric | Observed | Projected (base) | Low (x0.5) | High (x1.5) |", "|---|---|---|---|---|",
    f"| Activations | {b['activations']} | {p['activations']} | {sens['low']['activations']} | {sens['high']['activations']} |",
    f"| Lead -> activation % | {b['lead_to_activation_pct']} | {p['lead_to_activation_pct']} | "
    f"{sens['low']['lead_to_activation_pct']} | {sens['high']['lead_to_activation_pct']} |",
    f"| Blended CAC (Rs) | {b['cac_inr']:,} | {p['cac_inr']:,} | {sens['low']['cac_inr']:,} | {sens['high']['cac_inr']:,} |",
    f"| Needs -> quote % | {b['assessed_to_quote_pct']} | {p['assessed_to_quote_pct']} | | |",
    f"| Avg days to activate | {b['avg_days_to_activate']} | {p['avg_days_to_activate']} (assumes -{base['assumptions']['days_saved_digital']} days) | | |",
    "", "## Where the extra activations come from", "",
    "| Drop reason | OneFlow lever | Dropped leads | Recovery % | Extra activations |", "|---|---|---|---|---|",
]
for r in base["by_reason"]:
    lines.append(f"| {r['reason']} | {r['lever']} | {r['leads']} | {round(r['rate'] * 100)}% | {r['extra_activations']} |")
lines += ["", "## Formulas", ""] + [f"- **{k}:** {v}" for k, v in base["formulas"].items()]
lines += ["", f"_{base['disclaimer']}_"]
(config.REPORTS_DIR / "simulation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"[OK] activations {b['activations']} -> {p['activations']} (low {sens['low']['activations']}, "
      f"high {sens['high']['activations']}); CAC Rs {b['cac_inr']:,} -> Rs {p['cac_inr']:,}")
