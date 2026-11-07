# Insights from smb_leads.csv (synthetic, Apr-Jun 2026)

Every number here is recomputed by `scripts/analyze_leads.py`. Cite these, not hand-typed figures.

- **Funnel:** 5,000 -> 3,406 -> 1,974 -> 861 -> 588 -> 368 (lead to activation 7.36%).
- **Spend vs bundle:** activated customers' bundle is a median **2.59x** (mean 3.73x) of what they spent before; **94.3%** pay more.
- **Price/competitor:** 55.8% of drops at Needs assessed -> Quote are 'Price too high' or 'Competitor offered cheaper plan'.
- **GSTIN effect:** activation 9.6% with GSTIN vs 2.0% without; 29.3% of leads have none.
- **Visits:** 827 leads dropped because a visit never happened; 805 were unreachable after 3 attempts.
- **Paperwork** is only 5.9% of all drops.
- **Speed:** 17.6 days lead-to-activation on average; CAC Rs 15,053 per activation.

## Status-chase calls vs churn and NPS (activated customers)

| Follow-up calls | Customers | 6-month churn % | Avg NPS |
|---|---|---|---|
| 1 | 34 | 5.9 | 7.5 |
| 2 | 84 | 14.3 | 7.2 |
| 3 | 137 | 11.7 | 6.9 |
| 4 | 70 | 20.0 | 6.7 |
| 5 | 43 | 27.9 | 6.0 |

## Lead sources

| Source | Leads | Activation % | Cost per lead | CAC per activation |
|---|---|---|---|---|
| Field sales | 1720 | 7.27 | Rs 1,769 | Rs 24,335 |
| Channel partner | 1010 | 8.02 | Rs 1,672 | Rs 20,851 |
| Website form | 995 | 4.32 | Rs 274 | Rs 6,352 |
| Inbound call | 504 | 9.52 | Rs 487 | Rs 5,113 |
| Referral | 413 | 14.77 | Rs 605 | Rs 4,099 |
| WhatsApp campaign | 358 | 2.79 | Rs 112 | Rs 4,026 |

## Segments

| Segment | Leads | Activation % | Avg bundle | Median spend before | Bundle/spend | Churn % | NPS |
|---|---|---|---|---|---|---|---|
| Micro retail & services | 2709 | 4.06 | Rs 2,505 | Rs 925 | 2.74x | 22.7 | 7.0 |
| Professional offices | 1247 | 11.07 | Rs 6,796 | Rs 2,525 | 2.66x | 13.8 | 6.9 |
| Small manufacturers | 289 | 12.8 | Rs 19,980 | Rs 13,800 | 1.23x | 8.1 | 6.5 |
| Small multi-site businesses | 755 | 10.99 | Rs 31,233 | Rs 9,650 | 3.04x | 10.8 | 6.7 |

## Top drop reasons

- Unreachable after 3 attempts: 805
- Owner had no time for a visit: 531
- Not interested on first call: 470

## Activation by preferred language

- Bengali: 9.0%
- Malayalam: 8.4%
- English: 8.0%
- Hindi: 7.9%
- Telugu: 7.7%
- Marathi: 6.3%
- Gujarati: 6.0%
- Kannada: 5.1%
- Tamil: 4.3%
- Punjabi: 4.2%

## Corrections to docs/08

- Channel-partner CAC per activation is **Rs 20,851** (docs said ~16.4k).
- Website-form CAC per activation is **Rs 6,352**; Rs 274 is its cost *per lead* (docs said ~720).
- WhatsApp campaign: Rs 112 per lead, Rs 4,026 per activation, 2.79% activation.
