# Phase 2 Gate — Failed, With Explanation

`plan.md` §6 permits Phase 3 to open on a failed Phase 2 gate **only** with a documented
explanation and the fallback in place. This is that document.

Evidence: `docs/evidence/p2_ftw_delineation.json`.
Reproduce: `scripts/p2_parcel_layer.py` then `scripts/p2_ftw_delineate.py --fields …`.

---

## The gate

Revised on 2026-09-30 after the `parcel-delineation` agent showed the original wording was
degenerate. It now requires **both**:

| Criterion | Threshold | Measured | Verdict |
|---|---:|---:|---|
| `match_rate` — points inside exactly one delineated field | ≥ 80% | **73.3%** | fail |
| `one_point_per_field_rate` — fields holding exactly one point | ≥ 60% | **20.4%** | fail |

Both fail. Phase 3 opened anyway, for the reasons below.

## What was actually run

`ftw inference all` — the Fields of The World maintainers' own pipeline, so normalisation
and scene selection are theirs rather than ours — with the **CC-BY EfficientNet-B7**
checkpoint (a licence choice that costs accuracy against the mixed-licence "FULL" model)
over real Sentinel-2 L2A for Sivagiri taluk, windows 2024-09→11 and 2024-12→2025-02.

Output: **64,708 field polygons, median 0.11 ha, 13,062 ha across the whole taluk.**

## Why the first criterion failed, and why it does not indicate a bad delineation

Strict containment scored **36.4%**. That reads like the model missed the fields. It did
not:

- **Correction to an earlier version of this document.** It said FTW's 13,062 ha was
  "within 8%" of the Agrisnet registry's 12,097 ha. That compared different footprints: FTW's
  figure covers the whole taluk, including 736 ha inside Reserve Forest, while the registry
  covers only the 21 revenue villages. Like for like, FTW delineates **7,151 ha inside those
  villages, 41% below the registry** and 26% below its annual-crop area.
  This is a genuine under-recovery, not a footprint artefact. `scripts/p2c_ftw_registry_area.py`.
- Points that fell outside a field sit a **median of 15.2 m** from the nearest one (`docs/evidence/p2e_ftw_match_detail.json`). 58% are
  within 20 m; only **0.9%** are beyond 200 m.

Fifteen metres is one to two Sentinel-2 pixels — the positional accuracy of a handheld
GPS fix. A binary point-in-polygon test is simply the wrong instrument for data carrying
that much positional uncertainty.

So points are snapped to the nearest field within a tolerance. To keep that from becoming
a tuned number, the whole curve is published:

| Snap tolerance | `match_rate` | `one_point_per_field_rate` |
|---:|---:|---:|
| 0 m (strict) | 36.4% | 16.6% |
| 10 m | 61.4% | 19.8% |
| 15 m | 68.0% | 20.2% |
| **20 m — applied** | **73.3%** | **20.4%** |
| 30 m | 81.4% | 20.8% |
| 50 m | 90.4% | 21.0% |

20 m was chosen from the measured offset distribution, not from where the gate flips. At
30 m the first criterion would pass — we did not take it, because the second criterion
shows the gate is not really about coverage.

## Why the second criterion failed — the actual finding

**Loosening the tolerance never fixes sharing.** It sits at ~20% across the entire curve,
because coverage and sharing measure different things:

> **Satellite delineation recovers *physical fields*, not *legal parcels*.**
>
> 10,707 matched parcels map onto **5,528 distinct fields** — a mean of **1.94 legal
> parcels per physical field**, up to **19** in one. 46% of matched fields carry more than
> one parcel.

This is not a model deficiency. A survey record is a legal unit — a survey number and
subdivision, often created by inheritance. A delineated field is the unit that is *farmed*.
In smallholder Tamil Nadu several legal parcels are routinely worked as one field, and no
optical sensor can see a boundary that exists only in a land register.

The mechanism is corroborated by the per-crop pattern:

| Crop | Match rate | Type |
|---|---:|---|
| Groundnut | 62.5% (16 points) | annual arable |
| Sorghum | 56.7% (30 points) | annual arable |
| Sugarcane | 56.5% (432 points) | annual arable |
| Rice (Paddy) | 41.4% (9,201 points) | annual arable |
| Banana | 27.5% (655 points) | perennial |
| Maize | 25.9% (1,563 points) | annual, often intercropped |
| **Coconut** | **23.6% (2,627 points)** | **perennial tree crop** |

Groundnut and Sorghum rest on 16 and 30 points, so the comparison worth making is
Sugarcane (432 points) against Coconut (2,627). Strict containment,
`docs/evidence/p2e_ftw_match_detail.json`.

A model trained on annual cropland bounds annual cropland. Coconut groves — 18% of this
dataset — are not delineated as fields at all.

## Why Phase 3 opened anyway

Three conditions from `plan.md` §6 are met.

**1. The fallback is in place and no record was lost.** 14,611 parcels carry geometry:
2,983 `ftw` (sole occupant), 7,724 `ftw_shared`, 3,904 `voronoi`. `geometry_source`
distinguishes them everywhere downstream and feeds the Record Trust Score.

**2. The leakage consequence is handled structurally, not by inspection.** Parcels sharing
a field carry identical zonal features — a second leakage channel behaving exactly like a
shared capture event. `splits.headline_groups` unions `field_id` with `bag_id` through
union-find, so transitively linked parcels never split across folds. The cost is now
measured: **2,921 capture-event bags collapse to 2,269 components** (`docs/evidence/p4_results.json` → `group_structure`), a 22% loss of
independent groups, with one chain spanning 164 parcels. Phase 4 reports the ladder under
that grouping.

**3. The area consequence is fixed.** Initially each sharing parcel inherited the whole
field's area, inflating the shared set **3.88×** and the taluk total from 2,250 ha to
4,801 ha. Crop-wise area is a headline product output, so that would have been a published
figure that was simply wrong. Field area is now apportioned among the parcels sharing it,
weighted by their fallback Voronoi extent; `field_area_m2` retains the undivided figure.
Verified: inflation exactly 1.000×. Figures: `docs/evidence/p2d_shared_field_area.json`.

*Later refinement:* apportioning got the total right but still split one physical field
across several crops. Crop area is now aggregated at **field** level for shared fields — one
crop per field, the label with the largest apportioned area; totals unchanged; a
`conflicted_area_ha` column exposes fields whose records disagree (rule text in
`p7_registry.json` → `area_rule`). Note also that 2,250 ha is the feature-store total; the
audited total is 2,137.6 ha, because 301 parcels (112.6 ha) without features never reach
the audit.

## What this is worth to FarmwiseAI

The question behind AI-1 was whether satellite delineation can substitute for cadastral
geometry. The measured answer for this landscape:

- It recovers **most but not all of the cropped extent** — about 59% of the registry's area inside the villages
  (the registry is the survey's own published aggregate, not an independent survey).
- It recovers the **farmed unit**, not the **ownership unit**, and here those differ by
  about **2×**.
- It matches annual arable roughly **2.4× better than perennial tree crops**: Sugarcane 56.5% (432 points) against Coconut 23.6% (2,627). The top two rows of the table rest on 16 and 30 points and should not carry the comparison.

So it is a strong substitute for *land-use* mapping and a weak one for *parcel* mapping.
That is a more useful answer than a passing gate would have been, and it is the answer the
revised gate was designed to surface — the original wording would have passed at 30 m
tolerance while concealing every one of these facts.

## Known caveats

- ftw-tools reported the Sentinel-2 processing baseline as **5.11** where FTW expects 5.1,
  warned "Processing version 5.11 unknown or untested — inference quality might decrease",
  and rescaled to baseline 3.0. Some of the 36.4% strict-containment shortfall may be
  attributable to that rather than to the landscape.
- The CC-BY checkpoint is less accurate than the mixed-licence FULL model. That is a
  deliberate licensing decision, recorded in `config.FTW_MODEL`.
- Zero-shot only. No fine-tuning on Indian smallholder data was attempted.
- Untested against real cadastral geometry. `p2_ftw_delineate.py --cadastral` computes IoU
  if FarmwiseAI supplies FMB polygons; see `docs/DATA_REQUEST.md`.
