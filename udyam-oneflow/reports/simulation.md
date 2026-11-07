# OneFlow what-if projection (under stated assumptions)

Zero-recovery check: reproduces the observed funnel exactly (5000/3406/1974/861/588/368).

| Metric | Observed | Projected (base) | Low (x0.5) | High (x1.5) |
|---|---|---|---|---|
| Activations | 368 | 670.2 | 519.1 | 821.3 |
| Lead -> activation % | 7.36 | 13.4 | 10.38 | 16.43 |
| Blended CAC (Rs) | 15,053 | 8,622 | 10,902 | 7,182 |
| Needs -> quote % | 43.62 | 56.24 | | |
| Avg days to activate | 17.6 | 13.6 (assumes -4 days) | | |

## Where the extra activations come from

| Drop reason | OneFlow lever | Dropped leads | Recovery % | Extra activations |
|---|---|---|---|---|
| Quote too complex to understand | instant ladder quote | 206 | 50% | 40.2 |
| Quote took too long to arrive | instant ladder quote | 179 | 50% | 35.3 |
| Price too high | spend-anchored Start rung | 414 | 20% | 32.8 |
| Missing GST or Udyam document | Smart KYC + unlock paths | 94 | 50% | 29.6 |
| Owner had no time for a visit | async link, no visit | 531 | 30% | 27.4 |
| Found paperwork too long | Smart KYC | 79 | 50% | 24.9 |
| Authorised signatory not available | e-sign / async | 53 | 50% | 16.7 |
| Visit not scheduled by sales | async link, no visit | 296 | 30% | 16.0 |
| Document details did not match | Smart KYC fix hints | 47 | 50% | 14.9 |
| Installation delayed beyond 21 days | tracker + 5G FWA alternative | 98 | 15% | 14.7 |
| Only wanted a mobile plan | mobile-only Start rung | 280 | 20% | 9.6 |
| Unreachable after 3 attempts | WhatsApp/SMS link instead of calls | 805 | 10% | 8.9 |
| Competitor offered cheaper plan | Start rung + single bill | 207 | 10% | 8.1 |
| Customer cancelled before install | tracker, fewer chases | 53 | 15% | 7.9 |
| Site not feasible for fibre | 5G FWA alternative | 41 | 15% | 6.1 |
| First payment failed | tracker reminders | 28 | 15% | 4.2 |
| Locked in with current provider | scheduled switch, parked lead | 325 | 5% | 2.8 |
| Decided to wait | scheduled switch, parked lead | 107 | 5% | 2.1 |

## Formulas

- **recovered:** dropped leads x recovery rate (per drop reason)
- **extra activations:** recovered x P(activated | reached next stage, same segment)
- **projected CAC:** (observed total acquisition cost + recovered leads x digital cost per lead) / projected activations
- **avg days:** observed average - assumed days saved by the digital path

_Projection under stated assumptions; recovery rates are editable placeholders, not facts._
