# Phase 6 — Trust, Calibration and Verification Economics

14,310 parcels · 2,921 capture events · split regime `3-event`

## 1. Calibration

Method: two-fold bag-grouped isotonic, cross-fitted. Every parcel is calibrated by a model fitted on capture events it did not belong to, so ECE is measured out-of-fit.

| | Raw | Calibrated |
|---|---:|---:|
| Expected Calibration Error | 0.1247 | **0.0046** |
| Mean confidence | 0.942 | 0.817 |
| Actual accuracy | 0.817 | 0.817 |

ECE improves by 0.1201. Raw confidence overstates accuracy.

## 2. Label-error detection

**2,183 records (15.26%)** are candidate label errors — the satellite confidently prefers a different crop than the surveyor declared.

`p_label_wrong` is discounted by the model's own measured accuracy (0.817), because a model that is right 82% of the time cannot assert more than that about anyone else's label. Mean `p_label_wrong` = 0.1097.

| Declared crop | Candidate errors |
|---|---:|
| Rice (Paddy) | 758 |
| Coconut | 497 |
| Banana | 374 |
| Maize | 351 |
| Sugarcane | 108 |
| Other | 95 |

> These are disagreements, not errors. Which side is right is what the field visit determines.

## 3. Record Trust Score

Weights applied (bag_support included — Phase 5 attention signal is informative):

| Component | Weight | Mean score |
|---|---:|---:|
| `bag_size` | 0.250 | 0.595 |
| `photo_distance` | 0.200 | 0.491 |
| `bag_support` | 0.250 | 0.598 |
| `stage_plausibility` | 0.100 | 0.875 |
| `mixed_crop` | 0.100 | 0.973 |
| `geometry_source` | 0.050 | 0.733 |
| `heterogeneity` | 0.050 | 0.437 |

> `geometry_source` mean score 0.733: parcels on their own delineated field score highest, shared fields lower, Voronoi fallback lowest.

## 4. Agreement status

| Status | Parcels | Area (ha) |
|---|---:|---:|
| `UNCERTAIN` | 8,429 | 1,143.0 |
| `CONFIRMED` | 4,825 | 870.8 |
| `DISPUTED` | 784 | 100.8 |
| `UNVERIFIABLE` | 272 | 23.0 |

> `CONFIRMED` requires high trust; `DISPUTED` does not. We are deliberately conservative about clearing a parcel and liberal about flagging one, which inflates DISPUTED relative to CONFIRMED.

## 5. Verification targeting

The base disagreement rate is **18.3%** — 2,617 of 14,310 parcels carry a satellite prediction differing from the declared crop. A random visit lands on one that often; a routed visit essentially always does.

| Budget | % of parcels | Routed hits | Random expected | Targeting |
|---:|---:|---:|---:|---:|
| 100 | 0.7% | 100 | 18 | 5.47x |
| 250 | 1.75% | 250 | 46 | 5.47x |
| 500 | 3.49% | 498 | 91 | 5.45x |
| 1,000 | 6.99% | 972 | 183 | 5.31x |
| 2,000 | 13.98% | 1,882 | 366 | 5.15x |

**Read this honestly.** Targeting efficiency is pinned to 1 / 0.183 = 5.47x at most, by construction: it reaches that cap whenever every routed parcel is a disagreement. It measures coverage, not ranking quality, and it establishes nothing about which side of a disagreement is correct. Any classifier can enumerate its own disagreements; the operational value is that only 18.3% of parcels need looking at.

The part that is *not* pinned — does the ranking put better-evidenced disagreements first?

| | Mean calibrated confidence |
|---|---:|
| Routed (budget 100) | 0.758 |
| All disagreements | 0.652 |

Model-estimated corrections, shown separately because they are an estimate rather than a count: 391 routed versus 54 random at budget 500.

## 6. Auto-clear

**4,825 parcels (33.7%)** are `CONFIRMED` — satellite and survey agree at high calibrated confidence on a record we trust. These need not be revisited next season.

- Area: 870.8 ha
- Surveyor-days saved per season: **193.0** of a 572.4-day baseline
- Rough residual-risk proxy: 7.6% (~365 parcels)

> Accuracy *within* the auto-cleared set is 100% by construction — `CONFIRMED` is defined as the model agreeing with the survey — so it is not reported. Auto-clearing fails only when the satellite and the surveyor err in the SAME way. That quantity is UNIDENTIFIED from this data: the calibrator was fitted against the declared label, so 1 - calibrated confidence estimates the probability of an event CONFIRMED already conditions on. It is offered as a rough proxy, NOT a bound, and can only be settled by an independent field audit of a CONFIRMED sample.

> Cost assumption: Assumption. Derived from 3,204 capture events over a ~7-day survey window across 21 villages in the supplied sample; revise with FarmwiseAI's actuals.
