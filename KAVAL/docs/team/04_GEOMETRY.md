# 04 · Parcel Geometry & Field Delineation

**Owner: M1 (Data & Geospatial) · Phase 2 · AI-1**
This phase **failed its gate**, and the failure is one of the more interesting results in
the project. Know why.

---

## 1. Why we had to make the geometry at all

The brief asks for **parcel-level** classification. FarmwiseAI supplied ground-truth
**points** and village boundaries. No cadastral parcel polygons.

Without polygons there is no parcel-level anything: no area statistic, no zonal
aggregation of embeddings over a parcel, no map of land. So geometry had to be created,
and how we created it is a substantive part of the work rather than a preprocessing step.

Two paths, both built:

- **Primary (AI-1):** satellite field-boundary delineation — `p2_ftw_delineate.py`
- **Fallback:** village-constrained Voronoi tessellation — `p2_parcel_layer.py`

`geometry_source` distinguishes them in every downstream output, and it feeds the Record
Trust Score.

## 2. The fallback: why Voronoi, not buffers

The obvious fallback is a buffer — draw a 30 m circle around each survey point. We did
not, for one reason:

**Buffers overlap.** Sum their areas and you count the same land twice. Crop-wise
cultivated area is a headline product output, so an overlapping geometry would corrupt a
number we publish.

A **Voronoi tessellation partitions** the village exactly once — every location belongs to
exactly one cell. Cells are clipped to 30 m radius so an isolated point
cannot claim half a village.

Verified: **0.0 m² double-counted**. Median parcel 1,953 m² (~0.2 ha),
plausible for smallholder Tamil Nadu.

*In review:* this is a small decision that shows the habit — choosing the representation
whose failure mode does not corrupt a published figure.

## 3. The primary path: Fields of The World

**The model.** A three-class U-Net (background / field interior / field boundary) with an
EfficientNet-B7 encoder, over a **bi-temporal** Sentinel-2 stack. Trained across 24
countries including Asian smallholder systems, which is why zero-shot was worth trying.

**Licence choice.** We use `FTW_PRUE_EFNET_B7_CCBY`, not the more accurate mixed-licence
"FULL" model, because we would be redistributing geometry derived from it. That costs
accuracy, deliberately, and it is recorded in `config.FTW_MODEL`.

**How it was run.** Via the maintainers' own CLI (`ftw inference all`), so scene selection
and normalisation are theirs rather than ours. Hand-rolling the 8-band stack risked
silently mis-normalising — FTW divides by 3000 internally, so pre-normalising would wreck
inference.

**Output: 64,708 raw field polygons; 64,530 after removing 178 slivers (median 1,100 m²).**

**The independent check, and a correction to it.** The Agrisnet registry reports
12,097 ha cropped across the 21 revenue villages. Our first published comparison said FTW
was "within 8%" of that. **That was wrong**: FTW's 13,062 ha covers the *whole taluk*, including
736 ha inside Reserve Forest, while the registry covers only the villages.

Restricted to the same footprint, FTW delineates **7,151 ha, which is 41% below the
registry**, and 26% below its annual-crop area (9,602 ha). So the delineation does
under-recover cropped land. We cannot isolate why: candidates are Rabi-only windows missing
fallow or late-sown fields, cloud, the processing-baseline mismatch below, and fields under
the 500 m² floor. `scripts/p2c_ftw_registry_area.py` reproduces it.

*This is worth telling as a story about method:* the near-match looked like validation, and
we only found it was a footprint artefact by checking that both sides measured the same
land.

**A caveat to volunteer:** ftw-tools warned the Sentinel-2 processing baseline is **5.11**
where FTW expects 5.1 — *"Processing version 5.11 unknown or untested. Inference quality
might decrease"* — and rescaled to baseline 3.0. Some shortfall may be attributable to
that rather than to the landscape.

## 4. The gate, and why it failed

The gate was **revised** mid-project after an agent showed the original wording was
degenerate: *"≥80% of points inside exactly one polygon"* is trivially satisfied by
**under**-segmentation, since one polygon per village scores 100%. The risk register had
anticipated the opposite failure. So a second criterion was added.

| Criterion | Threshold | Measured | |
|---|---:|---:|---|
| `match_rate` — points inside exactly one field | ≥ 80% | **73.3%** | fail |
| `one_point_per_field_rate` — fields with exactly one point | ≥ 60% | **20.4%** | fail |

### Criterion 1: not what it looks like

Strict containment scored only **36.4%**. That reads like the model missed the
fields. It did not — unmatched points sit a **median 15.2 m** from the nearest field (`docs/evidence/p2e_ftw_match_detail.json`), 58%
within 20 m, only 0.9% beyond 200 m.

Fifteen metres is one to two Sentinel-2 pixels: the positional accuracy of a handheld GPS
fix. **A binary point-in-polygon test is the wrong instrument for data with that
positional uncertainty.**

So points are snapped within a tolerance — and to stop that becoming a tuned number, the
whole curve is published:

| Snap tolerance | `match_rate` | `one_point_per_field_rate` |
|---:|---:|---:|
| 0 m | 36.4% | 16.6% |
| 10 m | 61.4% | 19.8% |
| 15 m | 68.0% | 20.2% |
| 20 m **(applied)** | 73.3% | 20.4% |
| 30 m | 81.4% | 20.8% |
| 50 m | 90.4% | 21.0% |

**20 m was chosen from the measured offset distribution, not from where the gate
flips.** At 30 m the first criterion would pass. We did not take it.

### Criterion 2: the actual finding

**Loosening the tolerance never fixes sharing** — it sits near 20% across the entire
curve, because the two criteria measure different things.

> **Satellite delineation recovers *physical fields*, not *legal parcels*.**
>
> 10,707 matched parcels map onto 5,528 distinct fields — a mean of **1.94 legal parcels
> per physical field**, up to **19**. 46% of matched fields carry more than one parcel.

This is not a model deficiency. A survey record is a **legal** unit created by
registration and inheritance. A delineated field is the unit that is **farmed**. In
smallholder Tamil Nadu several legal parcels are routinely worked as one block, and **no
optical sensor can see a boundary that exists only in a land register.**

The per-crop pattern corroborates the mechanism:

| Crop | Match rate | Type |
|---|---:|---|
| Groundnut | 62.5% (16 points) | annual arable |
| Sugarcane | 56.5% (432 points) | annual arable |
| Rice | 41.4% (9,201 points) | annual arable |
| Banana | 27.5% (655 points) | perennial |
| **Coconut** | **23.6% (2,627 points)** | **perennial tree crop** |

Strict containment, from `docs/evidence/p2e_ftw_match_detail.json`. Groundnut's
figure rests on 16 points, so the comparison worth making is Sugarcane against Coconut.
A model trained on annual cropland bounds annual cropland. Coconut groves — 18% of this
dataset — are not delineated as fields at all.

## 5. The two consequences, handled structurally

Phase 3 opened on a failed gate because all three `plan.md` §6 conditions are met: nothing
lost, leakage handled, area handled.

**Leakage.** Parcels sharing a field carry identical zonal features — a second leakage
channel behaving exactly like a shared capture event. `splits.headline_groups` unions
`field_id` with `bag_id` through **union-find**, so transitively linked parcels (A shares a
bag with B, B shares a field with C) never split across folds. Measured cost: 2,921 bags
collapse to 2,269 components (`docs/evidence/p4_results.json` → `group_structure`), a 22% loss of independent groups, and about 0.8 of a point of
accuracy.

**Area.** Initially each sharing parcel inherited the **whole field's area**, inflating the
shared set **3.88×** and the feature-store total from 2,250 ha to **4,801 ha** — in a
crop-area figure we publish (`docs/evidence/p2d_shared_field_area.json`: `shared_set_inflation`,
`apportioned_total_ha`, `inherited_total_ha`). Field area was then apportioned among sharing
parcels, weighted by their fallback Voronoi extent; `field_area_m2` keeps the undivided
figure. That made the total right (the shared set's apportioned 884.8 ha equals its
unique-field 884.8 ha) but still split one physical field across several crops.

**Crop area is now aggregated at field level** for `ftw_shared` parcels (`kaval/area.py`;
rule text in `p7_registry.json` → `area_rule`). Each of the 2,545 shared fields is assigned
**one** crop — the label with the largest apportioned area inside it, ties to the
alphabetically first — and contributes the summed area of its records present in the audit.
Totals equal the apportioned totals. `conflicted_area_ha` is the area of fields whose records
disagree on the label, so the majority rule does not hide the disagreement.

**Feature-store area is not audited area.** 301 parcels (112.6 ha) have no satellite
features and never reach the audit, so audit-based crop area totals **2,137.6 ha**, not
2,250.2 ha (sum of `agreement_status_area_ha` in `p6_audit.json`). Of the dropped parcels,
72 are in shared fields: 50 shared fields are only partly represented and 8 are lost
entirely (`p2d_shared_field_area.json`).

## 6. The village-code discrepancy, and what we can and cannot say about it

Spatially joining points to the supplied village polygons, **1,930 of 14,611 records (13%)
fall inside a different village than their code claims** — 1,895 of them the Viswanathaperi
Part-1/Part-2 pair (911 and 912). Source: `p7_registry.json` → `attribution_test.pair_geometry`.

**Our first reading was that the survey mis-recorded codes. We then "reversed" that using the
registry, and the reversal overreached** (correction #22 in `13_CORRECTIONS.md`). The
registry is the survey's own published aggregate, compiled by the **recorded** village code,
so it agrees with the recorded codes by construction. Its figures — mean |Δ share|
**0.0183** by recorded code against **0.1053** by polygon across the pair; **0.0569** against
**0.0655** across all villages (`attribution_test`, Rabi 2024, 3-event split regime) —
cannot show which attribution is right. The all-village figures also show the gap is a
two-village effect, not taluk-wide.

**The only independent evidence is geometric.** All 1,175 records coded 912 fall inside
polygon 911 (Part-1) and polygon 912 contains none of them; of the records coded 911, 398
fall inside 911 and 720 inside 912. That **suggests** a boundary or labelling error in the
supplied layer. It does not prove it. It is a question for FarmwiseAI to settle with
cadastral records or a field check — not a finding against the survey or the layer.

**Two consequences:** the registry comparison attributes by recorded code (like-for-like with
how the registry is compiled, not a verdict); the leakage
protocol still groups by polygon membership, because spatial blocking depends on where a
parcel physically *is*, not on which label the polygon carries.

## 7. The reserve-forest control

Four of the 25 polygons are **Reserve Forest** (`village_co = 'YYY'`) — protected land, not
unsurveyed farmland, as an earlier draft of our own proposal assumed.

**734.7 ha (4.0%)** of 18,385 ha reads as field-like; Naranapuram R.F reads
37%.

**Do not call this encroachment.** There is no ground truth inside these polygons. It is
equally consistent with cultivation, with delineation false positives on canopy gaps and
fire lines, or with another boundary error — and 37% looks more like a mislabelled polygon
than a third-encroached forest. What it produces is a bounded, ranked list of places worth
a field visit.

## 8. The CRS bug

FTW's output revealed the AOI is **UTM zone 43N** (mean longitude 77.41°E; zone 43 spans
72–78°E). `config.METRIC_CRS` said 44N. Every area was inflated **0.218%** and every
photo-distance slightly distorted. Fixed and all affected outputs regenerated.

*Worth telling:* we did not find this by reasoning about it. A third-party tool wrote its
own CRS and we noticed the mismatch.

---

## Questions you must be able to answer

**"Your delineation only matches 73% — isn't that a failure?"**
> Two different things are happening. Points that miss a field sit a median 15 m away,
> which is GPS error, and we handle it with a tolerance chosen from the measured
> distribution. The real result is the other criterion: satellite delineation recovers
> farmed fields, not legal parcels — 1.94 parcels per field. That is a finding about what
> the technology can do, not a defect in our pipeline.

**"How do you know the delineation itself is any good?"**
> Partly, and we are careful about it. It recovers physical fields well enough to show that
> legal parcels share them, and it behaves sensibly by crop type. But it under-recovers total
> cropped area: inside the 21 registry villages it finds 7,151 ha against 12,097 ha, about
> 41% short. We first reported that as "within 8%", which compared different footprints, and
> we corrected it.

**"Isn't a 20 m snap tolerance just moving the goalposts?"**
> It would be if we had picked it because it passes the gate. It does not — the gate still
> fails. We picked it from the measured offset distribution (median 15.2 m), and we publish
> the whole tolerance curve so anyone can see what other choices would have given. At 30 m
> the first criterion would have passed and we did not take it.

**"Why not just use buffered points and move on?"**
> Buffers overlap, so summing their areas double-counts land. We publish crop-wise
> cultivated area. The geometry had to be one whose failure mode does not corrupt that.

**"You blamed FarmwiseAI's boundary file. Are you sure?"**
> No, and we no longer claim it. We once argued the registry sided with the recorded codes,
> but the registry is compiled from those same codes, so that agreement was circular. The
> only independent evidence is geometric: all 1,175 records coded 912 sit inside polygon 911
> and polygon 912 contains none. That suggests a boundary or labelling error in the layer,
> but only cadastral records or a field check from FarmwiseAI can confirm it. We have changed
> our mind twice on this — first blaming the surveyors, then the layer — which is why we now
> state it as a question.

**"Is the reserve-forest result encroachment?"**
> We do not claim that. There is no ground truth inside those polygons and at least three
> explanations fit. It is a ranked list of places worth visiting, which is what the whole
> product is.
