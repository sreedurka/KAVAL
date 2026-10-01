# The Leakage Ladder

Same model. Same features. Same hyper-parameters. **Only the split changes.**

LightGBM · 76 features (64-d Google Satellite Embedding + 12 seasonal Sentinel-1/2) · 14,310 parcels · 5-fold

| # | Validation split | Accuracy | Macro F1 | What it leaks |
|---|---|---:|---:|---|
| 1 | Random row split | 89.7% | 0.775 | Near-duplicate parcels from the same capture event land on both sides |
| 2 | Grouped by parcel | 90.5% | 0.796 | Capture-event siblings still span the split |
| 3 | Grouped by capture event | 81.7% | 0.554 | Nothing from the same field visit — but neighbouring villages remain |
| 4 | Grouped by village (spatial) | 69.0% | 0.287 | Nothing; the model must generalise to unseen geography |

**Accuracy falls 20.7 points** and **macro F1 falls 0.488** between the loosest and the strictest regime, with no change to the model whatsoever.

A team reporting row 1 and a team reporting row 4 have built the same system.
Only one of them has measured it.
