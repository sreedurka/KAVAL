# Phase 4 — Leakage Ladder, Heads and Sources

14,310 parcels · 2,921 capture events · 21 villages · 76 features · 5-fold

## A. The Leakage Ladder

Same model, same features, same hyper-parameters. Only the split changes.

| Regime | Accuracy | Macro F1 | Log loss | What it controls for |
|---|---:|---:|---:|---|
| 1-random | 89.7% ± 0.004 | 0.772 | 0.343 | Stratified row-wise k-fold. Diagnostic only — never a headline. |
| 2-parcel | 89.5% ± 0.005 | 0.769 | 0.343 | Grouped by parcel id. The obvious control; on this data it changes nothing, because parcels are already 1:1 with rows. |
| 3-event | 81.2% ± 0.022 | 0.528 | 0.823 | Grouped by survey capture event (one photograph, up to 43 parcels). THE HEADLINE REGIME. |
| 4-village | 70.8% ± 0.095 | 0.326 | 1.459 | Grouped by the village the parcel actually falls in (village_spatial, not the recorded code). Geographic generalisation. |

Accuracy falls **18.9 points** and macro F1 falls **0.446** from the loosest regime to the strictest, with no change to the model.

Grouping by parcel — the obvious control — moves accuracy by -0.2 points. It is not protection. Only capture-event grouping exposes the drop.

### Group structure behind regime 3

The headline regime unions capture events with delineated fields: 2,921 bags collapse to 2,269 components (22.3% of groups lost); the largest component spans 164 parcels across 25 bags.

| Grouping | Accuracy | Macro F1 |
|---|---:|---:|
| Diagnostic: bag_id only, no field union (not a regime) | 82.0% ± 0.006 | 0.559 |
| Regime 3-event (bag_id ∪ field_id, headline) | 81.2% ± 0.022 | 0.528 |

LightGBM, all features, identical splitter settings. ± is the SD across the 5 folds.

## B. Model heads

Regime 3-event, identical folds.

| Head | Accuracy | Macro F1 | Log loss |
|---|---:|---:|---:|
| MLP | 81.7% ± 0.012 | 0.564 | 1.048 |
| LogisticRegression | 80.6% ± 0.025 | 0.537 | 0.655 |
| LightGBM | 81.2% ± 0.022 | 0.528 | 0.823 |
| RandomForest | 79.1% ± 0.021 | 0.469 | 0.658 |

## C. Feature sources

Regime 3-event, MLP, identical folds.

| Source | Features | Accuracy | Macro F1 |
|---|---:|---:|---:|
| GSE only (64-d) | 64 | 81.5% | 0.563 |
| Seasonal S1/S2 only (12) | 12 | 73.7% | 0.399 |
| GSE + seasonal (76) | 76 | 81.7% | 0.564 |
| Presto (128-d) | 128 | 74.2% | 0.452 |
| GSE + Presto (192) | 192 | 81.3% | 0.559 |

### Paired against GSE only, fold by fold

| Source | Metric | Mean Δ | SD of Δ | Folds favouring | Verdict |
|---|---|---:|---:|---:|---|
| Seasonal S1/S2 only (12) | macro_f1 | -0.1646 | 0.0332 | 0/5 | worse |
| Seasonal S1/S2 only (12) | accuracy | -0.0782 | 0.0065 | 0/5 | worse |
| GSE + seasonal (76) | macro_f1 | +0.0008 | 0.0081 | 2/5 | underpowered — within fold noise |
| GSE + seasonal (76) | accuracy | +0.0022 | 0.0068 | 3/5 | underpowered — within fold noise |
| Presto (128-d) | macro_f1 | -0.1115 | 0.0106 | 0/5 | worse |
| Presto (128-d) | accuracy | -0.0730 | 0.0068 | 0/5 | worse |
| GSE + Presto (192) | macro_f1 | -0.0040 | 0.0064 | 1/5 | underpowered — within fold noise |
| GSE + Presto (192) | accuracy | -0.0018 | 0.0118 | 2/5 | underpowered — within fold noise |

## D. Per-class performance

Regime 3-event, MLP. **Capture events, not record count, is the honest sample size.**

| Crop | Records | Capture events | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| Rice (Paddy) | 8,970 | **2102** | 0.865 | 0.916 | 0.890 |
| Coconut | 2,566 | **463** | 0.772 | 0.765 | 0.769 |
| Maize | 1,560 | **159** | 0.711 | 0.678 | 0.694 |
| Sugarcane | 429 | **117** | 0.781 | 0.667 | 0.719 |
| Banana | 653 | **64** | 0.440 | 0.254 | 0.322 |
| Other | 132 | **16** | 0.000 | 0.000 | 0.000 |

> Classes with few independent capture events have metrics with very wide error bars. The `Other` class aggregates seven crops that individually have between 1 and 4 capture events; no per-class claim is made for them.

## Confusion matrix

| true \\ pred | Banana | Coconut | Maize | Other | Rice (Paddy) | Sugarcane |
|---|---:|---:|---:|---:|---:|---:|
| **Banana** | 166 | 139 | 52 | 8 | 270 | 18 |
| **Coconut** | 67 | 1964 | 50 | 5 | 457 | 23 |
| **Maize** | 26 | 78 | 1058 | 8 | 388 | 2 |
| **Other** | 8 | 53 | 4 | 0 | 67 | 0 |
| **Rice (Paddy)** | 97 | 280 | 320 | 17 | 8219 | 37 |
| **Sugarcane** | 13 | 29 | 4 | 0 | 97 | 286 |
