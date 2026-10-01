# 01 · System Architecture

**Audience:** everyone. You must be able to draw this from memory.

---

## The pipeline

```
   SUPPLIED            FarmwiseAI: 14,643 ground-truth points, 25 village polygons
        │
        ▼
   PHASE 1  ACQUISITION      Google Satellite Embedding (GEE) · Sentinel-1/2 (STAC, no key)
                             Fields of The World checkpoint · TN Agrisnet crop registry
                             CHIRPS rainfall · NASA POWER temperature · Presto checkpoint
        │
        ▼
   PHASE 2  GEOMETRY  AI-1   FTW U-Net over Sentinel-2 → 64,530 field polygons
                             Voronoi fallback for unmatched points
        │                    → parcels.gpkg  (geometry_source, field_id)
        ▼
   PHASE 3  FEATURES  AI-2   zonal aggregation → feature_store.parquet
                             14,611 parcels × 76 features, keys intact
        │
        ▼
   PHASE 4  VALIDATION       the Leakage Ladder — 4 regimes, 4 heads, 3 sources
        │                    → oof_predictions.parquet  (leakage-free probabilities)
        ▼
   PHASE 5  LEARNING  AI-3   attention-MIL over capture-event bags → bag_support
        │
        ▼
   PHASE 6  AUDIT     AI-4   calibration · confident learning · Record Trust Score
        │                    → agreement status → verification routing
        ▼
   PHASE 7  SURFACE   AI-5   FastAPI (17 routes) ← agentic analyst (9 typed tools)
        │
        ▼
   PHASE 8  PRODUCT          React + Leaflet, coloured by agreement status
```

## The six AI components

Each is load-bearing. Remove one and something downstream stops working.

| | Component | Why it must exist | Outcome |
|---|---|---|---|
| **AI-1** | FTW field-boundary segmentation | We were given *points*, not polygons. "Parcel-level" is impossible without geometry. | Worked; found fields ≠ parcels |
| **AI-2** | GSE + Presto foundation embeddings | The brief asks for this comparison. Two different inductive biases. | Both run. GSE clearly ahead as a standalone source (macro F1 0.563 vs 0.452, 3-event); combining adds nothing measurable |
| **AI-3** | Attention-MIL over capture-event bags | The label defect becomes the modelling framework. | **Failed as a classifier**, works as an audit signal |
| **AI-4** | Confident learning + calibration | Uncalibrated confidence cannot route a budget. | ECE 0.125 → 0.005 |
| **AI-5** | Agentic analyst over typed tools | The product surface; answers the brief's queries with citations. | Tool layer verified; planning verified on Gemini (9/9 core questions, 2/2 extended), not on Claude |
| **AI-6** | Vision-language photo check | Closes the audit loop with independent evidence. | **Conditional** — we hold paths, not pixels |

## The output vocabulary

Every parcel gets an **agreement status**. This, not the crop class, is what the product is
organised around — and it is the single most important design decision to be able to
defend.

| Status | Condition | Action | Count |
|---|---|---|---:|
| `CONFIRMED` | model agrees, high calibrated confidence, high trust | skip next season | 4,825 |
| `DISPUTED` | model disagrees at high confidence | top of the worklist | 784 |
| `UNCERTAIN` | confidence below threshold | route by budget | 8,429 |
| `UNVERIFIABLE` | trust below floor | re-survey the **record**, not the parcel | 272 |
| `UNSEEN` | no survey record | satellite-only, no audit claim | 0 |

**`UNVERIFIABLE` is the one to talk about.** It says the problem is the *evidence*, not the
field. A parcel labelled from a photograph taken 3 km away, shared with 40 other parcels,
cannot be audited — and nothing downstream of the Digital Crop Survey reports that today.

## Why the order matters

The pipeline is gated: **no phase opens until its predecessor's acceptance criteria pass**
(`plan.md` §6). This is not bureaucracy. Two examples of it doing real work:

- **Phase 0 before Phase 4.** Auditing the ground truth *before* modelling is what revealed
  the capture-event structure. Had we modelled first, we would have reported ~90% accuracy
  and never known it was leakage.
- **Phase 4 before Phase 6.** The calibration and confident-learning inputs are
  out-of-fold probabilities from the headline regime. Had they come from a random split,
  every trust signal downstream would have inherited the leak.

## Where the code lives

| Path | What |
|---|---|
| `kaval/config.py` | **Every threshold and constant.** A number in two files means one is wrong. |
| `kaval/splits.py` | The leakage protocol, in code. The only place splits are made. |
| `kaval/mil.py` | Attention-MIL |
| `kaval/audit.py` | Calibration, confident learning, trust, routing |
| `kaval/provenance.py` | The only way a `PROVENANCE.md` entry gets written |
| `scripts/p*.py` | One script per phase; every number in every document comes from here |
| `api/main.py`, `api/analyst.py` | FastAPI + the agentic analyst |
| `frontend/` | React + Leaflet |
| `docs/evidence/` | Generated artefacts — **never hand-edited** |

## Two structural guarantees worth naming in review

1. **A metric cannot leave the API without its split regime.** `metric_response()` raises
   if `split_regime` is absent. It is not a convention, it is enforced.
2. **The agreement-status rule exists in exactly one place.** The frontend originally
   re-derived it in TypeScript; we deleted that and added threshold parameters to the API
   instead, so the rule cannot drift between server and browser.
