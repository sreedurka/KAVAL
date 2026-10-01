# Ground-Truth Forensics — Supplied Reference Sample

Source: `Dataset/Ground Truth Points/Ground_truth_Points.csv`  ·  regenerate with `KAVAL/scripts/gt_forensics.py`

## Headline

- **14,643 survey records** across 21 villages
- ...but only **3,204 distinct capture events** (**4.57x label inflation**)
- A single capture event supplies up to **43 parcel labels**
- **93.8%** of records sit in a multi-parcel capture event
- Capture events containing more than one crop label: **0** (out of 3,204)

## Effective sample size per crop

| Crop | Records | Capture events | Inflation |
|---|---:|---:|---:|
| Rice (Paddy) | 9,221 | 2322 | 4.0x |
| Coconut | 2,633 | 517 | 5.1x |
| Maize | 1,568 | 162 | 9.7x |
| Banana | 655 | 66 | 9.9x |
| Sugarcane | 433 | 120 | 3.6x |
| Marigold | 36 | 3 | 12.0x |
| Sorghum | 30 | 4 | 7.5x |
| Cassava | 24 | 3 | 8.0x |
| Diploid Cotton (Paruththi) | 19 | 2 | 9.5x |
| Groundnut | 16 | 2 | 8.0x |
| Mango | 6 | 1 | 6.0x |
| Fodder Sorghum | 2 | 2 | 1.0x |

> Per-class metrics for the minority crops rest on a handful of independent
> observations. Reporting an F1 score for them without stating this is misleading.

## Photograph geolocation vs. the parcel it documents

- median **1,436 m**, p90 **3,808 m**, max **8,559 m**
- **62.3%** of records are documented by a photograph taken over 1 km away
- separately, **647** records store two coordinates in one cell and **13** decode to a location outside the study area — both must be repaired before use
- the parcels sharing one label are themselves tight (median spread 117 m), so the label behaves as a spatially smoothed block, not a per-parcel observation

## Class structure

- 12 crop classes; top 5 account for **99.1%** of records
- **385** records declare more than one crop category (single-label classification cannot express these)
