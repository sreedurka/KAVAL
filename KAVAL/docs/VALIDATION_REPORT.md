# KAVAL — Validation Report

*Generated 2026-10-01 by `scripts/p9_validation_report.py`. Every figure regenerates from a script in `KAVAL/scripts/`.*

---

## Headline

**81.7% accuracy, 0.564 macro F1** — MLP, regime `3-event` (grouped by survey capture event), 5-fold.

Under a random row split the same pipeline reports **89.7%**. The difference is not the model; it is the split.

We do not claim the brief's >95% target. On this data that figure is reachable only by validating in a way the brief itself says invalidates the result.

---

## 1. What the ground truth actually contains

- **14,643 survey records** resolve to only **3,204 capture events** (4.57x label inflation)
- one capture event supplies up to **43 parcel labels**; 93.8% of records sit in a multi-parcel event
- **0** of 3,204 events contain more than one crop label — the label is attached to the event and copied
- the photograph sits a median **1,436 m** from the parcel it documents (p90 3,808 m); 62.3% are over 1 km away
- **385** records declare more than one crop category

- **1,930 records** carry a village code that disagrees with the polygon the point falls inside

### Effective sample size per crop

| Crop | Records | Independent capture events | Inflation |
|---|---:|---:|---:|
| Rice (Paddy) | 9,221 | **2322** | 4.0x |
| Coconut | 2,633 | **517** | 5.1x |
| Maize | 1,568 | **162** | 9.7x |
| Banana | 655 | **66** | 9.9x |
| Sugarcane | 433 | **120** | 3.6x |
| Marigold | 36 | **3** | 12.0x |
| Sorghum | 30 | **4** | 7.5x |
| Cassava | 24 | **3** | 8.0x |
| Diploid Cotton (Paruththi) | 19 | **2** | 9.5x |
| Groundnut | 16 | **2** | 8.0x |
| Mango | 6 | **1** | 6.0x |
| Fodder Sorghum | 2 | **2** | 1.0x |

> This table is why per-class metrics below carry capture events alongside record counts. Marigold's 36 records are three field observations.

---

## 2. Leakage controls and the Leakage Ladder

Same model, same features, same hyper-parameters. Only the split changes.

| Regime | Accuracy | Macro F1 | Log loss | What it controls for |
|---|---:|---:|---:|---|
| `1-random` | 89.7% ± 0.004 | 0.772 | 0.343 | Stratified row-wise k-fold. Diagnostic only — never a headline. |
| `2-parcel` | 89.5% ± 0.005 | 0.769 | 0.343 | Grouped by parcel id. The obvious control; on this data it changes nothing, because parcels are already 1:1 with rows. |
| `3-event` | 81.2% ± 0.022 | 0.528 | 0.823 | Grouped by survey capture event (one photograph, up to 43 parcels). THE HEADLINE REGIME. |
| `4-village` | 70.8% ± 0.095 | 0.326 | 1.459 | Grouped by the village the parcel actually falls in (village_spatial, not the recorded code). Geographic generalisation. |

Accuracy falls **18.9 points** and macro F1 **0.446** from loosest to strictest.

**Grouping by parcel is not a leakage control on this data.** It moves accuracy by -0.2 points, because parcels are already one-to-one with rows. Only capture-event grouping exposes the drop.

The headline regime additionally unions the delineated field id into the group key: parcels sharing one satellite-delineated polygon carry identical zonal features and leak exactly as capture-event siblings do.

---

## 3. Model heads and embedding sources

Regime `3-event`, identical folds throughout.

### Heads

| Head | Accuracy | Macro F1 | Log loss |
|---|---:|---:|---:|
| MLP | 81.7% ± 0.012 | 0.564 | 1.048 |
| LogisticRegression | 80.6% ± 0.025 | 0.537 | 0.655 |
| LightGBM | 81.2% ± 0.022 | 0.528 | 0.823 |
| RandomForest | 79.1% ± 0.021 | 0.469 | 0.658 |

### Sources

| Source | Features | Accuracy | Macro F1 |
|---|---:|---:|---:|
| GSE only (64-d) | 64 | 81.5% | 0.563 |
| Seasonal S1/S2 only (12) | 12 | 73.7% | 0.399 |
| GSE + seasonal (76) | 76 | 81.7% | 0.564 |
| Presto (128-d) | 128 | 74.2% | 0.452 |
| GSE + Presto (192) | 192 | 81.3% | 0.559 |

Paired against `GSE only (64-d)` on identical folds (14,310 parcels):

| Source | Mean Δ macro F1 | SD of Δ | Folds favouring | Verdict |
|---|---:|---:|---:|---|
| Seasonal S1/S2 only (12) | -0.1646 | 0.0332 | 0/5 | worse |
| GSE + seasonal (76) | +0.0008 | 0.0081 | 2/5 | **underpowered** — within fold noise |
| Presto (128-d) | -0.1115 | 0.0106 | 0/5 | worse |
| GSE + Presto (192) | -0.0040 | 0.0064 | 1/5 | **underpowered** — within fold noise |

**Reading the Presto rows.** Presto alone is clearly behind GSE under identical folds, but four things limit how far that is a verdict on Presto rather than on how we could feed it:

- Presto was pretrained on Sentinel-2 L1C top-of-atmosphere; we feed L2A surface reflectance. A small systematic shift, reported rather than corrected. Any GSE-vs-Presto gap should be read with this in mind.
- Temperature and precipitation are reanalysis products at ~0.5 deg and 0.05 deg respectively, so both are constant across the taluk within a month. They supply seasonality, not spatial signal.
- One series per parcel: the monthly value is the MEAN over the parcel's pixels (p1_acquire_stac.py), not a per-pixel series pooled afterwards. Presto was pretrained per pixel.
- Frozen pretrained encoder, no fine-tuning; the 128-d embedding is fed to the same MLP head and folds as GSE (p4 section C).

Sentinel-2 was observed for 92.2% of parcel-months overall, but only 38.1% in 2024-11 — the survey month — because of north-east monsoon cloud.

---

## 4. Per-class performance

Regime `3-event`, MLP.

| Crop | Records | Capture events | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| Rice (Paddy) | 8,970 | **2102** | 0.865 | 0.916 | 0.890 |
| Coconut | 2,566 | **463** | 0.772 | 0.765 | 0.769 |
| Maize | 1,560 | **159** | 0.711 | 0.678 | 0.694 |
| Sugarcane | 429 | **117** | 0.781 | 0.667 | 0.719 |
| Banana | 653 | **64** | 0.440 | 0.254 | 0.322 |
| Other | 132 | **16** | 0.000 | 0.000 | 0.000 |

### Confusion matrix

| true \\ predicted | Banana | Coconut | Maize | Other | Rice (Paddy) | Sugarcane |
|---|---:|---:|---:|---:|---:|---:|
| **Banana** | 166 | 139 | 52 | 8 | 270 | 18 |
| **Coconut** | 67 | 1964 | 50 | 5 | 457 | 23 |
| **Maize** | 26 | 78 | 1058 | 8 | 388 | 2 |
| **Other** | 8 | 53 | 4 | 0 | 67 | 0 |
| **Rice (Paddy)** | 97 | 280 | 320 | 17 | 8219 | 37 |
| **Sugarcane** | 13 | 29 | 4 | 0 | 97 | 286 |

### Dominant error pattern

- **Coconut → Rice (Paddy)**: 457 parcels
- **Maize → Rice (Paddy)**: 388 parcels
- **Rice (Paddy) → Maize**: 320 parcels
- **Rice (Paddy) → Coconut**: 280 parcels
- **Banana → Rice (Paddy)**: 270 parcels

Errors collapse toward Rice, which is 63% of the data. Banana is the weakest class: 653 records but only 64 independent capture events, so its F1 rests on very little evidence.

---

## 5. Multiple-Instance Learning over capture-event bags

| Model | Parcel accuracy | Parcel macro F1 |
|---|---:|---:|
| Per-parcel baseline | 81.7% | 0.566 |
| Attention-MIL | 78.7% | 0.509 |
| **Difference** | **-3.00 pp** | **-0.0565** |

Bag-level accuracy: **87.6%** ± 0.020.

**MIL does not beat the per-parcel baseline on macro F1.** Reported as a negative result.

### Is the attention signal usable as an audit signal?

- lowest-support quartile agrees with the survey 69.4% of the time
- the other three quartiles agree 85.6% of the time
- gap: **+16.18 pp**

The signal is informative and is weighted in the Record Trust Score.

---

## 6. Calibration, trust and verification economics

### Calibration

| | Raw | Calibrated |
|---|---:|---:|
| Expected Calibration Error | 0.1247 | **0.0046** |
| Mean confidence | 0.942 | 0.817 |
| Actual accuracy | 0.817 | — |

Method: two-fold bag-grouped isotonic, cross-fitted.

### Label-error detection

**2,183 records (15.26%)** are candidate label errors — the satellite confidently prefers a different crop than the surveyor declared. These are disagreements; the field visit decides which side is right.

### Agreement status

| Status | Parcels | Area (ha) |
|---|---:|---:|
| `UNCERTAIN` | 8,429 | 1,143.0 |
| `CONFIRMED` | 4,825 | 870.8 |
| `DISPUTED` | 784 | 100.8 |
| `UNVERIFIABLE` | 272 | 23.0 |

### Verification targeting

The base disagreement rate is **18.3%** — 2,617 parcels carry a satellite prediction differing from the declared crop. A random visit lands on one that often; a routed visit essentially always does.

| Budget | % of parcels | Routed hits | Random expected | Targeting |
|---:|---:|---:|---:|---:|
| 100 | 0.7% | 100 | 18 | 5.47x |
| 250 | 1.75% | 250 | 46 | 5.47x |
| 500 | 3.49% | 498 | 91 | 5.45x |
| 1,000 | 6.99% | 972 | 183 | 5.31x |
| 2,000 | 13.98% | 1,882 | 366 | 5.15x |

**Read this honestly.** Targeting efficiency is pinned to 1 / 0.183 = 5.47x at most, by construction: it reaches that cap whenever every routed parcel is a disagreement. It measures coverage, not ranking quality, and establishes nothing about which side of a disagreement is correct — any classifier can enumerate its own disagreements. The operational value is that only 18.3% of parcels need looking at at all.

**Auto-clear:** 4,825 parcels (33.7%), 870.8 ha, saving **193.0 surveyor-days** of a 572.4-day baseline.

> Cost assumption: Assumption. Derived from 3,204 capture events over a ~7-day survey window across 21 villages in the supplied sample; revise with FarmwiseAI's actuals.

---

## 7. Threats to validity

Stated plainly, because a report that lists none has not looked.

- **Geometry is derived, not cadastral.** Parcel polygons come from a village-constrained Voronoi tessellation of the survey points, or from satellite delineation. Neither is the legal parcel boundary. Area figures inherit that approximation.
- **One taluk, one season.** 21 revenue villages, an 8-day survey window in November 2024. Generalisation beyond Sivagiri is untested, and the village-grouped regime is the closest proxy we have.
- **Seven crops are not evaluable.** Classes with fewer than five independent capture events are collapsed to `Other`. No per-class claim is made for them.
- **The registry comparison uses declared crop as its reference** where an independent registry figure is unavailable. That makes it a consistency check, not an external validation.
- **The cost saving rests on a stated assumption** about surveyor productivity, not on FarmwiseAI's actual figures.
- **Confident learning identifies disagreement, not error.** Whether the satellite or the surveyor is right is exactly what a field visit resolves; nothing here settles it.

