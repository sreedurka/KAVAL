# KAVAL Glossary

Terms you may meet in the KAVAL app, the documents or the talk. Each entry gives a
plain-language meaning, why it matters in KAVAL, an example from this project's data, and
where you will see it.

**How to read the examples.** Every figure comes from a file in `KAVAL/docs/evidence/`,
named in square brackets, for example `[p6_audit.json]`. Every accuracy or F1 names its
validation split regime. The headline is **81.7% accuracy, 0.564 macro F1: MLP head, regime
`3-event` (capture event joined with shared delineated fields), 5-fold.** Where the survey
and the satellite differ, we say they *disagree*. A field visit decides which one is right.

**App views** referred to below: *Audit map*, *Village audit*, *Field worklist*,
*Auto-clear*, *Leakage Ladder* (the validation view), *Analyst*, plus the *parcel panel*
(opens when you click a parcel) and the *thresholds rail* (left side).

**Sections**

1. [Agreement statuses](#1-agreement-statuses)
2. [Survey, land records and agriculture](#2-survey-land-records-and-agriculture)
3. [Village audit table](#3-village-audit-table)
4. [Worklist, auto-clear and economics](#4-worklist-auto-clear-and-economics)
5. [Satellite data and remote sensing](#5-satellite-data-and-remote-sensing)
6. [AI and machine learning](#6-ai-and-machine-learning)
7. [Validation and leakage](#7-validation-and-leakage)
8. [Product and engineering](#8-product-and-engineering)
9. [Project names, places and process](#9-project-names-places-and-process)

---

## 1. Agreement statuses

### Agreement status
**Meaning.** The verdict KAVAL attaches to every parcel. It replaces a bare crop label with
the action to take: trust the record, re-check it, or treat the evidence as untestable.
**Why it matters.** The product is organised around status, not crop. The map is coloured
by it and the worklist is sorted by it. The rule exists in one place only
(`kaval/audit.agreement_status`), applied in this order: UNSEEN overrides UNVERIFIABLE,
which overrides DISPUTED and CONFIRMED. Anything left over is UNCERTAIN.
**Example.** Across 14,310 audited parcels: CONFIRMED 4,825 · DISPUTED 784 · UNCERTAIN
8,429 · UNVERIFIABLE 272 · UNSEEN 0 (regime `3-event`) `[p6_audit.json →
agreement_status_counts]`.
**Where.** Audit map legend and colours; parcel panel; *Status* column in the Field
worklist; `/audit/status-summary`; `01_ARCHITECTURE.md`.

### CONFIRMED
**Meaning.** The satellite agrees with the declared crop, its calibrated confidence is at
or above `confidence_high` (0.80), and the record's Record Trust Score is at or above
`trust_high` (0.65).
**Why it matters.** These parcels are candidates to **auto-clear**, meaning they can skip
next season's visit. The rule asks for high trust as well as agreement, so we are
deliberately cautious about clearing a parcel.
**Example.** 4,825 parcels, 870.8 ha, which is 33.7% of parcels (regime `3-event`)
`[p6_audit.json]`. On the map it is blue, not green. The usual green/red pair fails
colour-vision checks at ΔE 4.1 under deuteranopia `[p8_palette.json]`.
**Where.** Audit map; Auto-clear view; parcel panel.

### DISPUTED
**Meaning.** The satellite prefers a different crop from the one declared, with calibrated
confidence at or above `confidence_high` (0.80). No trust requirement applies.
**Why it matters.** These go to the top of the field worklist. Because DISPUTED does not
require high trust, we flag liberally and clear conservatively, which makes DISPUTED larger
relative to CONFIRMED.
**Example.** 784 parcels, 100.8 ha (regime `3-event`) `[p6_audit.json]`. DISPUTED does not
mean the record is in error. It means the two sources disagree.
**Where.** Audit map; Field worklist; parcel panel.

### UNCERTAIN
**Meaning.** The record is testable (trust above the floor), but the model is not confident
enough to confirm or dispute it.
**Why it matters.** This is the largest group. It is routed by budget rather than settled
automatically.
**Example.** 8,429 parcels, 1,143.0 ha (regime `3-event`) `[p6_audit.json]`.
**Where.** Audit map; Field worklist; the analyst's answer to the brief's "low-confidence
parcels" query `[p7_analyst_verification.json]`.

### UNSEEN
**Meaning.** A parcel or field with no survey record. Only a satellite prediction exists,
so there is nothing to audit.
**Why it matters.** It keeps satellite-only predictions apart from audit claims. It would
apply to delineated fields that no surveyor visited.
**Example.** 0 in the audited set, because every audited parcel came from a survey record
`[p6_audit.json]`. Of 64,530 delineated fields, 59,002 contain no ground-truth point, and
those are where UNSEEN would apply `[p2_ftw_delineation.json → gate]`. It is drawn as an
outline with no fill.
**Where.** Audit map legend; `01_ARCHITECTURE.md`.

### UNVERIFIABLE
**Meaning.** The Record Trust Score is below `trust_floor` (0.35). The evidence behind the
record is too weak to test, whatever the model predicts.
**Why it matters.** It says the problem is the **evidence**, not the field. The fix is to
re-survey the *record*, for example with a new photograph taken at the parcel. Nothing
downstream of the Digital Crop Survey reports this today.
**Example.** 272 parcels, 23.0 ha (regime `3-event`) `[p6_audit.json]`. A typical case has a
photograph taken kilometres away that is shared by dozens of parcels.
**Where.** Audit map; parcel panel; the `trust_floor` slider on the thresholds rail.

---

## 2. Survey, land records and agriculture

### AgriStack
**Meaning.** India's digital public infrastructure for agriculture. It has three
registries: farmers, geo-referenced village maps, and the Crop Sown Registry.
**Why it matters.** The Digital Crop Survey fills the Crop Sown Registry, and that is the
data KAVAL audits.
**Example.** Our ground truth is a DCS extract with village code, survey number,
subdivision, crop, stage and image reference columns.
**Where.** `02_DOMAIN_PRIMER.md` §1; proposal §3.

### Bag
**Meaning.** The machine-learning name for a capture event: a group of parcels that share
one label. Its key is `bag_id`, which is the record's `image_path`.
**Why it matters.** The bag is the leakage group key and the unit used by attention-MIL.
**Example.** 3,204 bags in the records, with 2,921 among the 14,310 audited parcels. The
largest bag covers 43 parcels `[gt_forensics.json; p4_results.json]`.
**Where.** *Bag* column in the Field worklist; "Parcels sharing this photograph" in the
parcel panel; `07_MODELS_MIL.md`.

### Capture event
**Meaning.** One surveyor, one photograph, one moment, plus every parcel record that
photograph was used to label.
**Why it matters.** This is the unit at which a crop was actually observed, so it is the
honest sample size and the headline validation group.
**Example.** 14,643 records come from 3,204 capture events, an inflation of 4.57×. 93.8% of
records sit in a multi-parcel event. **0** events carry more than one crop label. Parcels
within one event are a median 117 m apart `[gt_forensics.json]`.
**Where.** Leakage Ladder view (forensics panel); "Capture event" in the parcel panel; every
document.

### Crop stage
**Meaning.** The growth stage the surveyor declared, such as sown, vegetation, flowering,
full growth or harvesting.
**Why it matters.** It feeds the *stage plausibility* component of the Record Trust Score.
A rare stage for the declared crop lowers trust.
**Example.** vegetation 8,905 · full_growth 5,138 · flowering 243 · sown 198 · harvesting
159. 98.9% of Coconut records sit in that crop's most common stage, against 64.4% of
Sugarcane `[gt_forensics.json]`.
**Where.** "Declared stage" in the parcel panel.

### Digital Crop Survey (DCS)
**Meaning.** India's seasonal survey in which a surveyor visits agricultural parcels and
records the crop, its stage and a geotagged photograph.
**Why it matters.** Its figures feed crop insurance, procurement planning and disaster
compensation. KAVAL helps decide which visits are worth making. It does not replace the
survey. We regard the DCS as a national-scale achievement. Provenance artefacts are
expected at that scale, and what has been missing is a tool that measures them.
**Example.** Our extract covers Sivagiri taluk from 2024-11-06 to 2024-11-13, an 8-day
window `[p1_repair.json]`.
**Where.** Everywhere. `02_DOMAIN_PRIMER.md` §1.

### FMB / cadastral map
**Meaning.** The Field Measurement Book, Tamil Nadu's cadastral map. It holds the legal
boundary of every survey number and subdivision.
**Why it matters.** None was supplied, so "parcel-level" first required satellite
delineation (AI-1). FMB geometry would let us measure how close satellite fields come to
legal parcels (IoU).
**Example.** `parcel_polygons_supplied: false` `[gt_forensics.json]`. Request #1 in
`docs/DATA_REQUEST.md`.
**Where.** `DATA_REQUEST.md`; `04_GEOMETRY.md`; talk §9.

### Geotagged photograph
**Meaning.** The survey photograph with GPS coordinates and a timestamp
(`image_latitude`, `image_longitude`, `image_timestamp`).
**Why it matters.** It is the only field evidence behind a record. Its position defines
photo distance, and its path defines the capture event.
**Example.** The photo coordinates and timestamp are identical within all 3,204 events.
647 records store two coordinates in one cell, and 13 fall outside the study area
`[gt_forensics.json]`. We hold the paths, not the images, so AI-6 is conditional.
**Where.** "Photograph taken" and "The photograph this label came from" in the parcel
panel; `DATA_REQUEST.md` §2.

### Ground-truth point
**Meaning.** One row of the supplied survey CSV: a point location with a declared crop.
After repair it becomes one parcel record.
**Why it matters.** These points are the labels, and they are the thing being audited.
**Example.** 14,643 input records become 14,611 canonical parcels after 32 duplicate
parcel keys are merged. 14,310 of those have features `[p1_repair.json;
p3_feature_store.json]`.
**Where.** Audit map points; `03_DATA_ACQUISITION.md`.

### Kharif
**Meaning.** The south-west monsoon cropping season, roughly June to September.
**Why it matters.** It is not our survey season, but our satellite year starts there:
season window 1 (June to August 2024) is labelled "Kharif / pre-season".
**Example.** The registry download also holds Kharif 2025 village totals, and all 21
villages reconcile `[p1_registry_acquisition.json → checks]`.
**Where.** `02_DOMAIN_PRIMER.md` §2; `kaval/config.py` `SEASON_WINDOWS`.

### Mixed crop
**Meaning.** A record that declares more than one crop category on one parcel.
**Why it matters.** A mixed parcel has no single answer for a single-label classifier, so
the declaration lowers trust. Detecting mixed crops from satellite is a deliberate
non-goal for now.
**Example.** 385 records `[gt_forensics.json]`. The `mixed_crop` trust component has weight
0.10 and a mean of 0.973 `[p6_audit.json]`.
**Where.** Parcel panel trust breakdown; proposal §10 item 10.

### Perennial crop
**Meaning.** A crop that stays in the ground all year, such as coconut or banana. Annual
crops include rice, maize and sugarcane.
**Why it matters.** Perennials behave differently in both the classifier and field
delineation. A field-boundary model trained on annual cropland does not outline tree
crops well.
**Example.** FTW strict match rate: Coconut 23.6% (2,627 points) against Sugarcane 56.5%
(432) `[p2e_ftw_match_detail.json]`. The registry holds 2,495 ha of perennial tree crops
against 9,602 ha of annual crops `[p2c_ftw_registry_area.json]`.
**Where.** `04_GEOMETRY.md`; talk §4 AI-1.

### Photo distance
**Meaning.** The distance from where the survey photograph was taken to the parcel it
labels.
**Why it matters.** A distant photograph cannot show that particular parcel, so trust
falls as distance grows. It is weighted 0.20 in the trust score and gives zero credit
beyond 3,000 m.
**Example.** Median 1,436 m, p90 3,808 m, maximum 8,559 m. 62.3% are over 1 km and 16.2%
over 3 km `[gt_forensics.json]`. The feature store's projected median, 1,432.9 m, uses a
different method. The published figure is the 1,436 m haversine median
`[p3_feature_store.json]`.
**Where.** *Photo* column in the Field worklist; "Median photo-to-parcel distance" tile;
parcel panel.

### Rabi
**Meaning.** The October to March cropping season. In Tamil Nadu it coincides with the
north-east monsoon, which brings most of the rain here.
**Why it matters.** Our survey and registry are both Rabi 2024. Monsoon cloud in this season
is why optical imagery has gaps around the survey dates.
**Example.** Taluk mean rainfall was 288.0 mm in October 2024 and 270.0 mm in November 2024
`[p1_chirps_acquisition.json]`. Sentinel-2 saw only 38.1% of parcels in November
`[p3b_presto.json]`.
**Where.** Village audit (registry season); `02_DOMAIN_PRIMER.md` §2.

### Reserve Forest
**Meaning.** Protected forest land. It is not revenue land and should hold no farmland.
**Why it matters.** Four of the 25 supplied polygons are Reserve Forest (`village_co =
'YYY'`). We first misread them as "unlabelled villages" (correction #7). Now they serve as a
**negative control**. Field-like patches inside them are places worth a visit. They are
**not** evidence of encroachment.
**Example.** 734.7 ha (4.0%) of 18,384.8 ha reads as field-like. Naranapuram R.F reads
37.2% `[p2b_reserve_forest.json]`.
**Where.** Audit map ("Reserve Forest" layer); `02_DOMAIN_PRIMER.md` §5; `13_CORRECTIONS.md`.

### Revenue village
**Meaning.** The basic administrative land unit below the taluk. It is not the same thing
as a settlement.
**Why it matters.** Villages are the unit of the registry comparison and of the strictest
validation regime (`4-village`).
**Example.** 21 of the 25 supplied polygons are revenue villages with ground truth. They
cover 26,588 ha `[p2_parcel_layer.json; p2c_ftw_registry_area.json]`.
**Where.** Village audit; village filter in the Field worklist.

### Subdivision
**Meaning.** A survey number divided by inheritance or sale, for example 1A or 2B
(`sub_divi_1`).
**Why it matters.** Village code, survey number and subdivision together form the legal
parcel key, `parcel_id`.
**Example.** Parcel IDs such as `9_177_1` and `9_217_1A` (village 9, survey 217,
subdivision 1A) `[p7_analyst_verification.json]`. 283 records have a blank subdivision
`[p1_repair.json]`.
**Where.** *Parcel* column in the worklist; parcel panel header.

### Survey number
**Meaning.** The primary land-parcel identifier within a village (`survey_n_1`).
**Why it matters.** It is a *legal* unit. A satellite sees *physical* fields, and the
difference between the two is a central AI-1 finding.
**Example.** 10,707 matched parcels fall in 5,528 fields, about 1.94 legal parcels per
physical field, and up to 19 in one field `[p2_ftw_delineation.json → gate]`.
**Where.** Parcel panel; `02_DOMAIN_PRIMER.md` §2.

### Surveyor
**Meaning.** The field official who visits parcels and records the crop, stage and
photograph.
**Why it matters.** Surveyor time is the cost KAVAL tries to save. A disagreement is never
treated as the surveyor's fault. It is a question for a field visit.
**Example.** Cost model: an assumed 25 parcels per surveyor-day, stated rather than measured
`[p6_audit.json → visit_cost_assumption]`.
**Where.** Auto-clear view ("The cost assumption").

### Taluk
**Meaning.** The administrative unit below a district.
**Why it matters.** Our whole study area is one taluk. Climate inputs are taluk-scale, so
they are constant across parcels within a month.
**Example.** Sivagiri taluk footprint: 44,973 ha, of which 26,588 ha are revenue villages
and 18,385 ha Reserve Forest `[p2c_ftw_registry_area.json]`.
**Where.** Crop-area summaries ("whole taluk"); talk §1.

### TN Agrisnet registry
**Meaning.** Tamil Nadu Agrisnet's published village-wise Digital Crop Survey report, which
gives crop area by village and season.
**Why it matters.** It is the "supplied registry" the brief asks us to compare against.
It is **not independent**: it is the DCS's own aggregate, compiled by the recorded village
code. So it is a consistency check, not validation.
**Example.** Rabi 2024, 21 villages, 12,096.9 ha in total: Rice 7,685.6 ha, Coconut 1,657.8,
Sugarcane 931.6, Maize 544.9, Banana 207.6 `[p1_registry_acquisition.json]`.
**Where.** Village audit ("Not independent validation" caveat); `compare_to_registry` tool.

### Village LGD code
**Meaning.** The Local Government Directory code, the national identifier of a revenue
village. In our CSV it is `village__1`.
**Why it matters.** A record's code can disagree with the polygon its point falls in. That
is an audit finding, not something to clean away.
**Example.** 1,930 records sit in a different polygon from the one their code names, 1,895
of them in the Viswanathaperi 911/912 pair `[p2_parcel_layer.json]`.
**Where.** "Village code mismatch" in the parcel panel; `DATA_REQUEST.md` §3.

---

## 3. Village audit table

The *Village audit* view compares satellite crop shares with the TN Agrisnet registry, one
row per village and crop (regime `3-event`). The worked example throughout this section is
**Rayagiri - Part-1, Sugarcane** `[p7_registry.json → largest_divergences]`.

### Conflicted area
**Meaning.** The area of physical fields whose survey records disagree on the crop. Several
legal parcels share one delineated field, and their labels do not match.
**Why it matters.** Crop area for a shared field is assigned to one majority crop at field
level. Conflicted area shows how much area that rule settled, so the disagreement stays
visible.
**Example.** 93.5 ha in 386 fields on predicted labels, and 22.9 ha in 56 fields on
declared labels `[p2d_shared_field_area.json → field_level_aggregation]`.
**Where.** Crop-area summaries ("conflicted area" per crop); `/summary/crop-area`.

### Delta share (pp)
**Meaning.** Satellite share minus registry share, in percentage points.
**Why it matters.** It is the main sort key. A district officer should look first where the
gap is largest, whichever direction it runs.
**Example.** Rayagiri - Part-1 Sugarcane: 23.7% − 58.2% = **−34.6 pp**. The largest positive
gap is Thenmalai - Part-2 Rice, +32.6 pp `[p7_registry.json]`.
**Where.** Village audit, "Full comparison" table and divergence chart.

### Implied ha delta
**Meaning.** The share gap extrapolated to hectares. Delta share is multiplied by the
registry's village cropped area.
**Why it matters.** It gives a sense of scale in hectares. It is **not measured**: our
parcel sample covers only part of each village.
**Example.** Rayagiri - Part-1 Sugarcane: **−256.0 ha** `[p7_registry.json]`.
**Where.** Village audit, "Full comparison".

### Minimum registry area filter
**Meaning.** Hides village–crop rows where the registry records less than a chosen area
(0, 1, 5, 10 or 25 ha). The default is 1 ha.
**Why it matters.** A crop with a tiny registry area can show a huge share gap from a
handful of parcels.
**Example.** 90 village × crop rows in total `[p7_registry.json → n_rows]`. 76 of them have
at least 1 ha in the registry `[p7_analyst_verification.json → offline_planner]`.
**Where.** Village audit, "Minimum registry area" selector; the `min_registry_ha` parameter
of `compare_to_registry`.

### Registry area outside our scope
**Meaning.** Registry hectares for crops we cannot evaluate, such as Acid Lime, Cassava,
Lemon, Mango, the pulses, Palmyra and Sorghum.
**Why it matters.** Shares are computed over evaluable crops only, so this tile shows what
was excluded.
**Example.** 8.8%. 11,027.5 of 12,096.9 registry ha are in scope `[p7_registry.json]`.
**Where.** Village audit tile.

### Registry ha
**Meaning.** The registry's area for that crop in that village, Rabi 2024.
**Why it matters.** It anchors the implied hectare figure and the minimum-area filter.
**Example.** Rayagiri - Part-1 Sugarcane: 431.2 ha `[p7_registry.json]`.
**Where.** Village audit, "Full comparison".

### Registry share
**Meaning.** The crop's share of the village's in-scope registry area.
**Why it matters.** We compare **shares, not hectares**, because our sample covers only part
of each village. Comparing hectares would measure sampling coverage, not agreement.
**Example.** Rayagiri - Part-1 Sugarcane: 58.2% `[p7_registry.json]`.
**Where.** Village audit ("Share, not hectares" caveat).

### Satellite ha
**Meaning.** The satellite-predicted area of that crop among the audited parcels in that
village. Shared fields are aggregated at field level.
**Why it matters.** It is the numerator of satellite share. It covers only our sample, which
totals 2,137.6 audited ha `[p2d_shared_field_area.json → audited_total_ha]`.
**Example.** Taluk-wide, Rice (Paddy) is predicted on 1,523.2 ha `[p2d_shared_field_area.json
→ field_level_aggregation.y_pred]`.
**Where.** Village audit; "Satellite-estimated crop area by village".

### Satellite share
**Meaning.** The crop's share of satellite-predicted area among the audited parcels in that
village.
**Why it matters.** It is the satellite side of every row.
**Example.** Rayagiri - Part-1 Sugarcane: 23.7%, mean calibrated confidence 0.823
`[p7_registry.json]`.
**Where.** Village audit.

### Systematic bias by crop
**Meaning.** For each crop, the satellite share minus the registry share, averaged across
villages. Shown as *Bias (pp)*.
**Why it matters.** It separates a crop-wide tendency, which looks like model bias, from
village-specific gaps, which are worth a visit.
**Example.** Sugarcane −6.5 pp, Rice +3.6 pp, Maize +2.1 pp, Banana −0.1 pp
`[p7_registry.json → systematic_bias_by_crop]`.
**Where.** Village audit, "Systematic bias by crop".

---

## 4. Worklist, auto-clear and economics

Figures here are at the headline regime `3-event` `[p6_audit.json]` unless stated.

### Area weight
**Meaning.** A parcel's area divided by the median routable parcel area, clipped to the
range [0.25, 4].
**Why it matters.** Larger parcels carry more crop area, so they move up the queue, but the
clip stops size from dominating. Area changes the *ranking* only. It never inflates the
estimated corrections count.
**Example.** A parcel ten times the median gets a weight of 4, not 10 (`kaval/config.py`
`area_weight_clip`).
**Where.** Field worklist chart note ("P(label wrong) × area weight, clipped to [0.25, 4]").

### Auto-clear
**Meaning.** Skipping next season's field visit for a CONFIRMED parcel.
**Why it matters.** This is where the cost saving comes from. It is presented with its
limits: accuracy *inside* the cleared set is 100% by construction (correction #1), so we do
not report it.
**Example.** 4,825 parcels (33.7%), 870.8 ha, saving 193.0 surveyor-days out of 572.4
`[p6_audit.json → auto_clear]`.
**Where.** Auto-clear view ("Parcels safe to skip", "What auto-clear does and does not
claim").

### Base disagreement rate
**Meaning.** The share of parcels where the satellite's top crop differs from the declared
crop.
**Why it matters.** It is the most useful single figure operationally, because it says how
many parcels need any human attention. It also sets the cap on targeting efficiency.
**Example.** 18.3%: 2,617 of 14,310 parcels `[p6_audit.json → budget_curve]`.
**Where.** Field worklist; talk §6 and close.

### Counterfactual (random visits)
**Meaning.** What the same N visits would achieve if chosen at random. It is the mean of
200 random draws, with the standard deviation shown as a whisker.
**Why it matters.** It is the baseline that routing has to beat. It is the same measure
spent differently, not a rival method.
**Example.** At N = 500: 53.9 estimated corrections from random visits (SD 6.0), against
390.5 from routed visits `[p6_audit.json → budget_curve]`.
**Where.** Field worklist ("Estimated corrections: random visits").

### Estimated corrections
**Meaning.** The sum of P(label needs correction) over the visited parcels: the expected
number of declared labels a visit would overturn.
**Why it matters.** It is the routing objective. It is a **model estimate, not a count**,
and the UI labels it that way.
**Example.** N = 500: 390.5 routed against 53.9 random. N = 100: 78.4 against 10.7
`[p6_audit.json → budget_curve]`.
**Where.** Field worklist tiles and chart.

### Priority
**Meaning.** The routing score for each parcel: P(label needs correction) × area weight.
The worklist sorts by it, highest first.
**Why it matters.** It has a single definition (`audit.routing_priority`), so the screen,
the API and the CSV export always produce the same queue.
**Example.** The analyst's `export_layer` call with `budget=500` returns the 500-row routed
queue, ranked by this score `[p7_analyst_verification.json → offline_planner]`.
**Where.** Field worklist "The queue"; `priority` column in exports.

### P(label needs correction) / `p_label_wrong`
**Meaning.** The estimated probability that the declared crop would not survive a field
check. It comes from confident learning and is discounted by the model's own accuracy. In
the UI it appears as "P(declared label is wrong)" or the column "P(wrong)". In speech we say
"needs correction".
**Why it matters.** It drives the worklist. A model that is 81.7% accurate cannot assert
more than that about anyone else's label, so the value is capped at 0.817 (correction #3).
It describes the label, not the parcel or the surveyor.
**Example.** Mean 0.1097 across 14,310 parcels `[p6_audit.json → confident_learning]`.
**Where.** *P(wrong)* column in the Field worklist; parcel panel.

### Ranking quality
**Meaning.** The mean calibrated confidence of routed parcels compared with the mean across
all disagreements.
**Why it matters.** Unlike targeting efficiency, it shows whether the queue puts the
better-evidenced disagreements first.
**Example.** 0.734 against 0.652 at N = 500, and 0.758 at N = 100 `[p6_audit.json →
budget_curve]`.
**Where.** Field worklist "Ranking quality" tile.

### Residual error rate proxy
**Meaning.** A rough estimate of how often auto-clearing would clear a parcel where the
satellite and the surveyor made the same error.
**Why it matters.** The true quantity cannot be identified from this data, because the
calibrator was fitted against the declared label. So this figure is a **proxy, not a
bound**. Only an independent field audit of a CONFIRMED sample can settle it.
**Example.** 7.6%, about 365 parcels `[p6_audit.json → auto_clear]`.
**Where.** Auto-clear "Expected residual error rate" tile and its caveat.

### Suggested correction
**Meaning.** The crop that confident learning prefers when it contests a declared label.
**Why it matters.** It tells the field officer what the satellite expects to find. It is a
hypothesis to check, not a replacement label. KAVAL never writes back to survey records.
**Example.** The most common disagreement is a declared Coconut that the satellite predicts
as Rice (Paddy): 457 parcels (MLP, `3-event`) `[p4_results.json → confusion matrix]`.
**Where.** Parcel panel.

### Surveyor-day
**Meaning.** One surveyor working for one day. Our assumption is that this covers 25
parcels.
**Why it matters.** It turns parcel counts into operating cost. The figure is an assumption,
inferred from 3,204 capture events over the survey window in 21 villages, and stated
wherever it is used.
**Example.** Baseline: 14,310 parcels ÷ 25 = 572.4 surveyor-days per season `[p6_audit.json
→ auto_clear, visit_cost_assumption]`.
**Where.** Auto-clear view ("The cost assumption", "Where the season's surveyor-days go").

### Surveyor-days saved
**Meaning.** Auto-cleared parcels ÷ parcels per surveyor-day.
**Why it matters.** It is the headline operating saving. Change the assumption and the
figure changes with it.
**Example.** 4,825 ÷ 25 = 193.0 surveyor-days per season `[p6_audit.json]`.
**Where.** Auto-clear tile.

### Targeting efficiency
**Meaning.** Disagreements found by routed visits ÷ disagreements expected from random
visits.
**Why it matters.** It is **capped by construction** at 1 ÷ base disagreement rate, and it
reaches the cap whenever every routed parcel is a disagreement. So it measures coverage,
not ranking. It was first published as a 5.58× "lift" and later corrected (#2).
**Example.** The cap is 5.47×. At N = 100 and 250 it equals 5.47×. At N = 500 it is 5.45×
(498 of 500 routed parcels are disagreements). At N = 2,000 it is 5.15× `[p6_audit.json →
budget_curve]`.
**Where.** Field worklist "Ranking quality" tile note ("capped … by construction, so not a
result").

### Verification budget (N)
**Meaning.** The number of field visits available this season.
**Why it matters.** The router chooses which N parcels to visit to maximise estimated
corrections. Any change re-queries the API.
**Example.** The slider runs from 10 to 5,000 with a default of 500. At N = 500 the routed
visits cover 142.8 ha, 3.49% of parcels `[p6_audit.json → budget_curve]`.
**Where.** Field worklist "Field visits available (N)"; `route_verification_budget` tool.

### Worklist (the queue)
**Meaning.** The ranked list of N parcels to visit, with status, declared and satellite
crop, P(wrong), confidence, trust, bag size, photo distance and area.
**Why it matters.** This is what a field officer exports and acts on.
**Example.** "Where should we send 500 surveyors next season?" is answered by the analyst
as 500 parcel *visits* `[p7_analyst_verification.json → product_queries]`.
**Where.** Field worklist "The queue", plus Export CSV and GeoJSON.

---

## 5. Satellite data and remote sensing

### 10 m pixel
**Meaning.** The ground size of one Sentinel-2 visible or near-infrared pixel, and of one
Google Satellite Embedding pixel.
**Why it matters.** Smallholder parcels are only a few pixels across, so per-parcel
averages rest on little data.
**Example.** The median parcel polygon covers 17 pixels, and 24% of polygons cover fewer
than 10 `[p1_stac_acquisition.json → zonal]`. FTW drops fields under 500 m², about five
pixels `[p2_ftw_delineation.json → postprocess]`.
**Where.** `05_FEATURES_EMBEDDINGS.md`.

### CHIRPS
**Meaning.** Climate Hazards Group InfraRed Precipitation with Station data, a public
monthly rainfall product at 0.05°.
**Why it matters.** It is a Presto input. At this resolution it gives seasonality, not
differences between parcels.
**Example.** 56 cells, 29 of them intersecting the taluk, over 12 months. Taluk mean
ranges from 7.4 mm (February 2025) to 307.4 mm (May 2025) `[p1_chirps_acquisition.json]`.
**Where.** `03_DATA_ACQUISITION.md`; `p3b_presto.json`.

### Cloud gap
**Meaning.** A period when optical imagery cannot see the ground because of cloud.
**Why it matters.** Tamil Nadu's north-east monsoon covers the survey month. Any optical
time-series model has little evidence exactly when the crop is surveyed.
**Example.** Sentinel-2 observed 92.2% of parcel-months over the year, but only 38.1% in
November 2024 (5,561 parcels) `[p3b_presto.json; p1_stac_acquisition.json → months]`.
**Where.** Talk §4 AI-2; `14_REVIEW_PREP.md`.

### DEM (Copernicus GLO-30)
**Meaning.** A digital elevation model giving ground height, and slope derived from it, at
30 m.
**Why it matters.** Presto expects terrain inputs. We used the Copernicus DEM in place of
SRTM, read anonymously from public S3 (correction #21).
**Example.** Terrain was observed for 99.99% of parcels `[p3b_presto.json →
terrain_observed_fraction]`.
**Where.** `p3b_presto.json`; `03_DATA_ACQUISITION.md`.

### Earth Engine (GEE)
**Meaning.** Google's geospatial platform. The Google Satellite Embedding is only
distributed there.
**Why it matters.** We hold GSE for all 14,611 surveyed parcels from the prior CropSight
export, but have no credentials to extract it for new geometry. That is why the
reserve-forest classifier check was not done.
**Example.** "Recorded as not done rather than approximated" `[p2b_reserve_forest.json →
calibration_check]`.
**Where.** Proposal §8; talk §9.

### L1C vs L2A
**Meaning.** Two Sentinel-2 processing levels. L1C is top-of-atmosphere reflectance. L2A is
surface reflectance, corrected for the atmosphere.
**Why it matters.** We use L2A. Presto was pretrained on L1C, so this is a documented
domain shift and one reason we do not rank Presto against GSE as models.
**Example.** Collection `sentinel-2-c1-l2a`. Processing baselines 5.1 and 5.11 were both
seen and harmonised `[p1_stac_acquisition.json]`.
**Where.** Leakage Ladder view (source caveats); `VALIDATION_REPORT.md` §3.

### NASA POWER
**Meaning.** NASA's free, keyless climate API. It serves MERRA-2 reanalysis.
**Why it matters.** It replaced ERA5-Land for monthly air temperature, which needs a
Copernicus key we do not have.
**Example.** 12 of 12 months at the taluk centroid (77.3917 E, 9.2898 N). Mean 25.19 °C,
range 22.8–27.24 °C. Cells are about 55 × 70 km, so it is taluk-scale only
`[p1_temperature.json]`.
**Where.** `03_DATA_ACQUISITION.md`.

### NDVI
**Meaning.** Normalised Difference Vegetation Index, (NIR − Red) / (NIR + Red). Higher
values mean more green vegetation.
**Why it matters.** It is part of the 12 seasonal features, and the spread of NDVI across
seasonal windows is the `heterogeneity` trust component.
**Example.** Seasonal features are S1–S4 × {NDVI, VH, VV} = 12 columns
`[p3_feature_store.json → heterogeneity_source]`.
**Where.** Leakage Ladder view, "Feature sources" ("Seasonal S1/S2 only (12)").

### Orbit direction
**Meaning.** Whether Sentinel-1 was travelling north (ascending) or south (descending) when
it imaged. The viewing geometry differs between the two.
**Why it matters.** Mixing directions in one time series creates a step change that does
not exist on the ground.
**Example.** The brief asked for ascending, but only descending (relative orbit 165, 31
scenes) covers this area `[p1_stac_acquisition.json]`.
**Where.** `03_DATA_ACQUISITION.md`.

### SCL cloud mask
**Meaning.** Sentinel-2's Scene Classification Layer, a per-pixel class map. We drop
no-data, saturated, cloud shadow, cloud and cirrus pixels (classes 0, 1, 3, 8, 9, 10).
**Why it matters.** Cloudy pixels would corrupt the monthly series and the features.
**Example.** All six November 2024 scenes were 72.2% to 100% masked over the study area
`[p1_stac_acquisition.json → months.2024-11]`.
**Where.** `scripts/p1_acquire_stac.py`; `03_DATA_ACQUISITION.md`.

### Seasonal windows (S1–S4)
**Meaning.** Four three-month composites spanning the crop year: S1 June–August 2024, S2
September–November 2024 (contains the survey), S3 December 2024–February 2025, S4
March–May 2025.
**Why it matters.** They structure the 12 hand-built seasonal features. Window labels S1–S4
are not Sentinel-1.
**Example.** "GSE + seasonal (76)" against "GSE only (64-d)": +0.0008 macro F1, underpowered
(MLP, `3-event`, 5-fold) `[p4_results.json → source_comparisons]`.
**Where.** Leakage Ladder view; `kaval/config.py`.

### Sentinel-1
**Meaning.** ESA's C-band radar satellites. Radar sees through cloud. KAVAL uses the
radiometrically terrain-corrected product (`sentinel-1-rtc`).
**Why it matters.** It is the only sensor that sees the ground through monsoon cloud.
**Example.** Observed for 99.99% of parcel-months, against 92.2% for Sentinel-2
`[p3b_presto.json]`.
**Where.** Presto input; seasonal VV/VH features.

### Sentinel-2
**Meaning.** ESA's optical satellites, with 10 m visible and near-infrared bands and a
revisit of about five days.
**Why it matters.** It supplies the FTW delineation input, the Presto optical input and
NDVI. It is blocked by cloud.
**Example.** FTW used two scenes, 2024-05-07 and 2024-12-08 `[p2a_ftw_inference.json]`.
Presto used ten bands (B2–B8A, B11, B12) per month `[p3b_presto.json]`.
**Where.** Everywhere in Phases 1–3.

### STAC
**Meaning.** SpatioTemporal Asset Catalog, a standard search API for satellite scenes. We
used Element84 Earth Search for Sentinel-2 and Microsoft Planetary Computer for Sentinel-1.
Neither needs an account.
**Why it matters.** It removed the supposed Earth Engine blocker for Sentinel data.
Planetary Computer's signed URLs expire, which once silently killed the Sentinel-1
download (correction #19).
**Example.** A 10 m grid in EPSG:32643, 2,719 × 3,067 pixels `[p1_stac_acquisition.json]`.
**Where.** `03_DATA_ACQUISITION.md`; plan.md §4.

### UTM 43N (EPSG:32643)
**Meaning.** The map projection used for every distance and area. The study area sits at
about 77.4° E, inside zone 43 (72–78° E).
**Why it matters.** An earlier version used zone 44N, which inflated every area by 0.218%
(correction #10).
**Example.** `grid_crs: EPSG:32643` `[p1_stac_acquisition.json]`.
**Where.** `kaval/config.py` `METRIC_CRS`; `13_CORRECTIONS.md`.

### VV / VH backscatter
**Meaning.** Radar energy returned to Sentinel-1 for two polarisation pairs. VH is more
sensitive to vegetation volume. Values are in dB.
**Why it matters.** It gives crop structure through cloud. Averages are taken in linear
power, then converted to dB, because averaging in dB gives a different answer.
**Example.** "dB image (per-window linear-power average -> dB)" `[p1_stac_acquisition.json →
zonal]`.
**Where.** Seasonal features; Presto input.

---

## 6. AI and machine learning

### Accuracy
**Meaning.** The share of parcels whose predicted crop equals the declared crop.
**Why it matters.** It is the brief's target metric, and it is misleading on its own here,
because Rice is about 63% of parcels (8,970 of 14,310).
**Example.** Headline 81.7% (MLP, `3-event`, 5-fold). The same pipeline with LightGBM
reports 89.7% under a random split `[p4_results.json]`.
**Where.** Leakage Ladder view; "Headline accuracy" tile.

### Attention-MIL
**Meaning.** A gated-attention multiple-instance learning model (AI-3). It reads all
parcels in a capture-event bag, predicts the bag's label, and gives each parcel an
attention weight.
**Why it matters.** It builds the label defect into the model. As a classifier it lost.
Its attention weights became an audit signal.
**Example.** Parcel accuracy 78.7% and macro F1 0.509, which is −3.00 pp and −0.0565 against
the per-parcel baseline on the same folds (`3-event`, 5-fold). Bag-level accuracy 87.6%
`[p5_mil.json]`.
**Where.** `07_MODELS_MIL.md`; `VALIDATION_REPORT.md` §5.

### bag_support
**Meaning.** A parcel's attention weight, normalised by bag size, so that 1.0 means average
support within its bag.
**Why it matters.** Low support marks a "passenger" parcel that may not match the bag's
label. It is weighted 0.25 in the Record Trust Score.
**Example.** The lowest-support quartile agrees with the survey 69.4% of the time, against
85.6% for the rest: **+16.2 pp**, measured against an independent baseline. Against MIL's
own prediction the gap reads +22.8 pp, but that version is partly self-referential
(correction #5) `[p5_mil.json → attention_check]`.
**Where.** Parcel panel trust breakdown; `08_AUDIT_LAYER.md`.

### Calibration
**Meaning.** Adjusting confidence so that "80% sure" is right about 80% of the time.
**Why it matters.** The budget is routed on confidence, and an uncalibrated number
overstates itself.
**Example.** Raw mean confidence 0.942 against accuracy 0.817. After calibration the mean
is 0.817 (`3-event` out-of-fold) `[p6_audit.json → calibration]`.
**Where.** Leakage Ladder view, "Calibration"; parcel panel "Calibrated confidence" and
"Raw confidence".

### Confident learning
**Meaning.** Finding probable label problems by checking where a model confidently prefers
a different class from the given label. It uses a separate threshold for each class.
**Why it matters.** It produces P(label needs correction) and the suggested correction. A
contested label is evidence about the *label*, not proof.
**Example.** 2,183 records (15.26%) are candidates: Rice 758, Coconut 497, Banana 374, Maize
351, Sugarcane 108, Other 95 (`3-event`) `[p6_audit.json → confident_learning]`.
**Where.** Field worklist; parcel panel; `08_AUDIT_LAYER.md`.

### Confusion matrix
**Meaning.** A table of true class against predicted class.
**Why it matters.** It shows which crops are mistaken for which. Here, errors collapse
toward Rice.
**Example.** MLP, `3-event`: Coconut → Rice 457, Maize → Rice 388, Rice → Maize 320
`[p4_results.json]`.
**Where.** Leakage Ladder view, "Confusion matrix" and "Most-confused pairs";
`confusion_report` tool.

### Cross-fitting
**Meaning.** Each parcel's calibration is fitted on other data, specifically on capture
events the parcel does not belong to.
**Why it matters.** Without it, ECE would be measured on the data the calibrator was fitted
to, and would look better than it is.
**Example.** "Two-fold bag-grouped isotonic, cross-fitted" `[p6_audit.json →
calibration.method]`.
**Where.** `08_AUDIT_LAYER.md`; Leakage Ladder view, "Calibration".

### ECE (Expected Calibration Error)
**Meaning.** The average gap between confidence and accuracy across confidence bins. KAVAL
uses 15 bins.
**Why it matters.** It is the calibration quality metric reported alongside accuracy.
**Example.** 0.1247 raw → **0.0046** calibrated (`3-event` out-of-fold) `[p6_audit.json]`.
**Where.** Leakage Ladder view, "Calibration".

### Effective n
**Meaning.** The number of independent observations behind a figure. Here that is
capture events, not records.
**Why it matters.** Per-class metrics for crops with few events have very wide error bars.
We always quote events beside records.
**Example.** Banana: 653 evaluated records, 64 capture events. Marigold: 36 records, 3
events. Mango: 6 records, 1 event `[p4_results.json; gt_forensics.json]`.
**Where.** Leakage Ladder view, "Effective n per crop" and "Per-class metrics with effective
n".

### Evaluable class / Other
**Meaning.** A crop with at least five independent capture events. The others are merged
into `Other`.
**Why it matters.** No per-class claim is made for crops that rest on one to four
observations.
**Example.** Evaluable: Rice (Paddy), Coconut, Maize, Banana, Sugarcane. Merged into Other:
Cassava, Diploid Cotton, Fodder Sorghum, Groundnut, Mango, Marigold, Sorghum. Other has F1
0.000 (MLP, `3-event`) `[p3_feature_store.json; p4_results.json]`.
**Where.** Leakage Ladder view, per-class table.

### Feature store
**Meaning.** The single table of model inputs per parcel, with keys, label, bag and
provenance.
**Why it matters.** Every model reads the same rows, and it rebuilds from scripts alone.
**Example.** 14,611 parcels × 76 features (64 GSE + 12 seasonal). 301 parcels (2.06%) have
no features and are flagged, not dropped `[p3_feature_store.json]`.
**Where.** `05_FEATURES_EMBEDDINGS.md`.

### Fields of The World (FTW)
**Meaning.** A benchmark and pretrained U-Net for field-boundary segmentation from two
Sentinel-2 dates. We use `FTW_PRUE_EFNET_B7_CCBY`.
**Why it matters.** It is AI-1, our only route to polygons. We chose the CC-BY checkpoint
for licence reasons.
**Example.** 64,708 raw polygons (13,061.9 ha) became 64,530 after post-processing
(12,246.7 ha) `[p2e_ftw_match_detail.json]`.
**Where.** Audit map geometry; `04_GEOMETRY.md`.

### Foundation model
**Meaning.** A large model pretrained on broad data and reused for many tasks without being
retrained from scratch.
**Why it matters.** KAVAL uses three and trains none: GSE and Presto for features, and FTW
for geometry.
**Example.** The Presto checkpoint has 822,682 parameters, used frozen
`[p1_presto_checkpoint.json; p3b_presto.json]`.
**Where.** Proposal §4; talk §4.

### Google Satellite Embedding (GSE) / AlphaEarth
**Meaning.** A 64-number, unit-length vector per 10 m pixel per year, produced by Google
DeepMind's AlphaEarth model from several sensors.
**Why it matters.** It is the brief's "satellite embeddings". It turns imagery into tabular
features, and it is our strongest source.
**Example.** GSE only: 81.5% / 0.563 macro F1 (MLP, `3-event`, 5-fold) `[p4_results.json →
sources]`.
**Where.** Leakage Ladder view, "Feature sources"; analyst's GSE vs Presto answer.

### Isotonic regression
**Meaning.** A calibration method that fits a non-decreasing step function from raw
confidence to observed accuracy.
**Why it matters.** It makes no assumption about the shape of the miscalibration.
**Example.** See ECE: 0.1247 → 0.0046 `[p6_audit.json]`.
**Where.** `kaval/audit.fit_calibrator`; `08_AUDIT_LAYER.md`.

### LightGBM
**Meaning.** A gradient-boosted decision-tree library.
**Why it matters.** It is the model held fixed on the Leakage Ladder, so that the split is
the only variable.
**Example.** 81.2% / 0.528 (`3-event`, 5-fold); 89.7% / 0.772 (`1-random`)
`[p4_results.json → ladder]`.
**Where.** Leakage Ladder view.

### Log loss
**Meaning.** A metric that penalises confident incorrect predictions. Lower is better.
**Why it matters.** It shows why calibration is needed: the best head on F1 has the worst
log loss.
**Example.** MLP 1.048 against LightGBM 0.823 (`3-event`) `[p4_results.json → heads]`.
**Where.** Leakage Ladder view, "Model heads".

### Macro F1
**Meaning.** The F1 score computed per class, then averaged with every class weighted
equally.
**Why it matters.** It stops Rice from hiding weak minority crops, and it is the metric we
pick heads by.
**Example.** Headline 0.564 (MLP, `3-event`, 5-fold). Banana alone is F1 0.322 on 64 capture
events `[p4_results.json]`.
**Where.** Leakage Ladder view; every results table.

### MLP
**Meaning.** A multi-layer perceptron, a small fully connected neural network.
**Why it matters.** It is our best head and produces the headline result.
**Example.** 81.7% ± 1.2 / 0.564 (`3-event`, 5-fold). Logistic regression 80.6% / 0.537,
Random Forest 79.1% / 0.469 `[p4_results.json → heads]`.
**Where.** Leakage Ladder view, "Model heads".

### Model head
**Meaning.** The classifier trained on top of fixed embeddings.
**Why it matters.** Heads are compared on identical folds, so differences reflect the head,
not the split.
**Example.** Four heads plus attention-MIL, all `3-event` `[p4_results.json; p5_mil.json]`.
**Where.** Leakage Ladder view, "Model heads, identical folds".

### Multiple-instance learning (MIL)
**Meaning.** Learning when a label belongs to a *bag* of instances rather than to each one.
**Why it matters.** It matches our data exactly: one photograph labels up to 43 parcels.
**Example.** 2,921 bags over 14,310 parcels `[p5_mil.json]`.
**Where.** `07_MODELS_MIL.md`.

### Out-of-fold predictions
**Meaning.** Each parcel's prediction comes from a model that never saw that parcel's group
during training.
**Why it matters.** Calibration, confident learning and every status are built on these. If
they came from a leaky split, every downstream trust signal would inherit the leak.
**Example.** All 14,310 audited parcels carry `3-event` out-of-fold probabilities
`[p6_audit.json]`.
**Where.** `oof_predictions.parquet`; `01_ARCHITECTURE.md` ("Why the order matters").

### Parcel vs field
**Meaning.** A *parcel* is a legal unit (survey number plus subdivision). A *field* is a
physical block farmed as one.
**Why it matters.** Satellites recover fields, not parcels. Parcels that share a field
carry identical features, so `field_id` is also a leakage key.
**Example.** 1.94 parcels per field (10,707 ÷ 5,528), up to 19. Geometry sources: 2,983
`ftw` (own field), 7,724 `ftw_shared`, 3,904 `voronoi` fallback `[p2_ftw_delineation.json]`.
**Where.** "Physical field", "Legal parcels sharing this field" and "Geometry source" in the
parcel panel.

### Per-class precision, recall, F1
**Meaning.** Precision: of the parcels predicted as crop X, how many were X. Recall: of the
true X parcels, how many were found. F1: their harmonic mean.
**Why it matters.** The brief requires them. We print them beside capture-event counts.
**Example.** MLP, `3-event`: Rice F1 0.890, Coconut 0.769, Sugarcane 0.719, Maize 0.694,
Banana 0.322 (recall 0.254) `[p4_results.json]`.
**Where.** Leakage Ladder view, "Per-class metrics".

### Presto
**Meaning.** NASA Harvest's pretrained transformer for remote-sensing time series. It turns
12 monthly steps of optical, radar, climate and terrain inputs into a 128-number embedding.
**Why it matters.** It is the second arm of the brief's embedding comparison. It sees
seasonal change where GSE sees an annual summary.
**Example.** 74.2% / 0.452 against GSE's 81.5% / 0.563, behind on 5 of 5 folds (MLP,
`3-event`). The run had caveats: L2A input, taluk-scale weather, parcel-mean series and a
frozen encoder `[p4_results.json; p3b_presto.json]`.
**Where.** Leakage Ladder view, "Feature sources"; `PRESTO_NOTES.md`.

### Record Trust Score
**Meaning.** A 0–1 score for the *evidence* behind a survey record. It is a weighted mean of
seven components with published weights.
**Why it matters.** It decides UNVERIFIABLE (below 0.35) and gates CONFIRMED (at or above
0.65). It scores provenance, not crop.
**Example.** Weights: bag_size 0.25, photo_distance 0.20, bag_support 0.25,
stage_plausibility 0.10, mixed_crop 0.10, geometry_source 0.05, heterogeneity 0.05. Median
score 0.648. Its correlation with model agreement is only r = 0.124, so it adds
information that agreement alone does not `[p6_audit.json]`.
**Where.** *Trust* column in the Field worklist; "Record Trust Score" in the parcel panel;
thresholds rail.

### Record Trust Score components
**Meaning.** Each component scores from 0 (no trust) to 1. Mean values are in brackets
`[p6_audit.json → trust_components_mean]`.
- **bag_size** (0.595): 1 for a single-parcel bag, falling to 0 for bags of 21 or more
  parcels.
- **photo_distance** (0.491): 1 at 0 m, falling to 0 at 3,000 m.
- **bag_support** (0.598): MIL attention, saturating at 1.5× the bag average.
- **stage_plausibility** (0.875): lower when the declared stage is rare for the declared
  crop.
- **mixed_crop** (0.973): 0 if the record declares a mixed crop.
- **geometry_source** (0.733): `ftw` 1.0, `ftw_shared` 0.75, `voronoi` 0.5.
- **heterogeneity** (0.437): lower when NDVI varies a lot across seasons.

**Why it matters.** The parcel panel shows *why* a record scored as it did. Note that
`p6_audit.md` still says geometry_source is "constant (all Voronoi)". That text is stale:
the mean of 0.733 shows it varies.
**Where.** Parcel panel; `08_AUDIT_LAYER.md`.

### Satellite embedding
**Meaning.** A fixed-length vector that a pretrained model computes from imagery to
summarise what is on the ground.
**Why it matters.** It is the input the brief specifies. A classifier on embeddings is
small, quick and reproducible.
**Example.** GSE has 64 dimensions per pixel per year. Presto has 128 per parcel
`[p4_results.json → sources]`.
**Where.** Proposal §4 AI-2.

### Segmentation / delineation
**Meaning.** Labelling every pixel (here as field interior, field boundary or background),
then turning the result into polygons.
**Why it matters.** This is how AI-1 creates geometry. Post-processing removes slivers and
fields below 500 m², simplifies edges at 5 m, and requires compactness of at least 0.10.
**Example.** 178 slivers were dropped and 0 polygons fell below the minimum area
`[p2_ftw_delineation.json → fields]`.
**Where.** `04_GEOMETRY.md`.

### Snap tolerance
**Meaning.** How far a survey point may be moved to the nearest delineated field.
**Why it matters.** GPS error puts points just outside their field. The tolerance was
chosen from the measured offsets, not tuned to pass the gate, and the full curve is
published.
**Example.** 20 m applied. Match rate is 36.4% at 0 m, 73.3% at 20 m and 90.4% at 50 m.
Unmatched points sit a median 15.2 m from a field `[p2_ftw_delineation.json;
p2e_ftw_match_detail.json]`.
**Where.** "Snapped to field by" in the parcel panel; `PHASE2_GATE_EXPLANATION.md`.

### Voronoi fallback
**Meaning.** Fallback geometry. Each survey point gets the area closer to it than to any
other point in its village, clipped to a 30 m radius.
**Why it matters.** It gives a polygon to every point that FTW could not match, with no
double-counted area.
**Example.** 3,904 parcels use it. In the all-Voronoi layer the median parcel is 1,953 m²,
and the overlap check found 0 m² double-counted `[p2_ftw_delineation.json;
p2_parcel_layer.json]`.
**Where.** "Geometry source" in the parcel panel.

---

## 7. Validation and leakage

### Capture-event grouping
**Meaning.** Splitting folds so that all parcels from one photograph fall in the same fold.
**Why it matters.** This is the control that exposes the leak. Grouping by parcel does not,
because each parcel is already one row.
**Example.** LightGBM: 89.5% when grouped by parcel, 81.2% when grouped by capture event
(5-fold) `[p4_results.json → ladder]`.
**Where.** Leakage Ladder view; `06_LEAKAGE_PROTOCOL.md`.

### Diagnostic run (bag-only)
**Meaning.** A run grouped by `bag_id` alone, without the field union. It is not a regime
and never a headline. It exists only to price the field union.
**Why it matters.** It measures what joining shared fields costs.
**Example.** 82.0% ± 0.006 / 0.559, against `3-event` at 81.2% ± 0.022 / 0.528 (LightGBM,
5-fold) `[p4_results.json → group_structure]`.
**Where.** `p4_results.md` "Group structure behind regime 3".

### Field union (union-find)
**Meaning.** Joining `bag_id` and `field_id` into one group key. If parcel A shares a bag
with B, and B shares a field with C, all three land in one fold.
**Why it matters.** Parcels sharing a delineated field carry identical features and would
leak across folds.
**Example.** 2,921 bags collapse to 2,269 groups (22.3% fewer). The largest group spans 164
parcels across 25 bags. The union costs **0.8 points** (82.0% → 81.2%, LightGBM)
`[p4_results.json → group_structure]`.
**Where.** `kaval/splits.headline_groups`; talk §5.

### Fold
**Meaning.** One of the five parts the data is split into. Each part is held out once while
the model trains on the other four.
**Why it matters.** Every comparison uses the same five folds, so differences are paired.
**Example.** MLP fold accuracies under `3-event` range from 79.4% to 82.5%
`[p4_results.json → heads]`.
**Where.** Leakage Ladder view ("Folds ahead" in source comparisons).

### Fold SD
**Meaning.** The standard deviation of a metric across the five folds.
**Why it matters.** An effect smaller than the fold SD is noise. Correction #4 came from
ignoring this.
**Example.** ±0.004 (`1-random`), ±0.022 (`3-event`) and ±0.095 (`4-village`) for LightGBM
accuracy. ±0.012 for the MLP headline `[p4_results.json]`.
**Where.** Leakage Ladder view ("±" values).

### Group key
**Meaning.** The column that decides which rows must stay in the same fold.
**Why it matters.** The wrong key gives a leaky result that looks clean.
**Example.** `3-event` uses `bag_id` ∪ `field_id`. `4-village` uses the village the parcel
falls *inside*, not the recorded code (correction #6) `[p4_results.json → ladder]`.
**Where.** `kaval/config.py` `SPLIT_REGIMES`.

### Headline regime
**Meaning.** The one regime our reported result uses: `3-event`.
**Why it matters.** No number leaves the project without naming it.
**Example.** 81.7% / 0.564, MLP, `3-event`, 5-fold `[p4_results.json]`.
**Where.** Every metric in the app carries a regime chip; `meta.split_regime` in the API.

### Leakage
**Meaning.** Information from the evaluation data reaching training, so that the score
measures recall of near-duplicates rather than generalisation.
**Why it matters.** The brief says leakage "will invalidate the claimed result". It is why
we do not claim 95%.
**Example.** A random split puts parcels from the same photograph on both sides of the
split. Accuracy then reads 89.7% instead of 81.2% (LightGBM, 5-fold) `[p4_results.json]`.
**Where.** Leakage Ladder view; `06_LEAKAGE_PROTOCOL.md`.

### Leakage Ladder
**Meaning.** The same model, features and settings evaluated under four split regimes, with
only the split changing.
**Why it matters.** It is the project's honesty credential and appears early in the
product.
**Example.** LightGBM, 5-fold: 89.7% / 0.772 (`1-random`) → 89.5% / 0.769 (`2-parcel`) →
81.2% / 0.528 (`3-event`) → 70.8% / 0.326 (`4-village`). That is −18.9 points of accuracy
`[p4_results.json → ladder]`.
**Where.** Leakage Ladder view (a top-level tab); talk §5.

### Negative control
**Meaning.** A test where the answer should be "nothing here". It checks that a method does
not find things that are not there.
**Why it matters.** Reserve Forest should hold no farmland. Field-like patches there
measure false positives or boundary issues, not encroachment.
**Example.** 2,919 field-like patches covering 734.7 ha `[p2b_reserve_forest.json]`.
**Where.** Audit map; `02_DOMAIN_PRIMER.md` §5.

### Paired comparison
**Meaning.** Comparing two sources or heads fold by fold on identical rows, then looking at
the mean and SD of the differences.
**Why it matters.** It removes fold-to-fold noise that affects both sides equally.
**Example.** Presto against GSE: mean Δ macro F1 −0.1115, SD 0.0106, 0 of 5 folds favour
Presto (MLP, `3-event`) `[p4_results.json → source_comparisons]`.
**Where.** Leakage Ladder view, "Feature sources" verdict column.

### Spatial autocorrelation
**Meaning.** Nearby places tend to look alike.
**Why it matters.** Adjacent parcels have near-identical signatures. A shuffled split
therefore overstates accuracy.
**Example.** Parcels in one capture event are a median 117 m apart `[gt_forensics.json →
capture_event_parcel_spread_m]`.
**Where.** `02_DOMAIN_PRIMER.md` §4.

### Split regime
**Meaning.** The rule for assigning rows to folds. KAVAL has four:
- **`1-random`**: rows shuffled. Diagnostic only, never a headline.
- **`2-parcel`**: grouped by `parcel_id`. Changes nothing here.
- **`3-event`**: grouped by capture event ∪ delineated field. **The headline.**
- **`4-village`**: grouped by the village polygon the parcel falls inside. Tests
  geographic generalisation.

**Why it matters.** "81.7% accuracy" is incomplete without it. `make_splits()` refuses an
unknown regime name.
**Example.** `4-village` fold accuracies range from 57.1% to 81.9%, which is why we call it
too noisy to quote precisely (LightGBM) `[p4_results.json]`.
**Where.** Regime chips on every metric; "Split regime" in the app.

### Underpowered
**Meaning.** A computed verdict: the mean paired difference falls within fold noise, so no
effect can be claimed in either direction.
**Why it matters.** It stops us reporting noise as a finding (corrections #4 and #20).
**Example.** GSE + seasonal: +0.0008 macro F1 (SD 0.0081, 2 of 5 folds). GSE + Presto:
−0.0040 (SD 0.0064, 1 of 5). Both are underpowered (MLP, `3-event`) `[p4_results.json]`.
**Where.** Leakage Ladder view, verdict column.

---

## 8. Product and engineering

### Agentic analyst
**Meaning.** AI-5. An LLM that plans which typed tools to call, calls them, and writes an
answer using only their results, with citations.
**Why it matters.** It answers the brief's natural-language analysis requests without the
model ever computing a figure itself.
**Example.** 6 of 6 brief queries pass, and all 12 tools are exercised
`[p7_analyst_verification.json]`.
**Where.** Analyst view; `10_API_ANALYST.md`.

### calibration_report
**Meaning.** The analyst tool that reports how far the model's confidence can be trusted:
expected calibration error before and after isotonic calibration, and mean raw and
calibrated confidence against actual accuracy.
**Why it matters.** Before this tool existed, a calibration question was answered by
improvising from unrelated tools. Now it reads the calibration figures directly.
**Example.** Raw confidence averaged 94.2% against an actual accuracy of 81.7%; ECE 0.1247
raw → 0.0046 calibrated (`3-event`) `[p7_analyst_verification.json → offline_planner.extended]`.
**Where.** Analyst view; Leakage Ladder view, "Calibration".

### Citation
**Meaning.** The provenance attached to each analyst answer: source file, row count, split
regime, and the parcel IDs the tool returned (up to 50).
**Why it matters.** Every claim can be traced back to its source, with no unsourced
numbers.
**Example.** The brief's "highest confusion" query cites 40 parcel IDs
`[p7_analyst_verification.json → offline_planner]`.
**Where.** Analyst view, citation chips and tool-calls drawer.

### Colour-vision (CVD) check
**Meaning.** A test that status colours stay distinguishable under protanopia, deuteranopia
and tritanopia.
**Why it matters.** A map that colour-blind officers cannot read fails at its job.
**Example.** The light palette has a worst CVD ΔE of 9.1 (pass, with a contrast warning).
The retired green/red palette scores 4.1 (fail) `[p8_palette.json]`.
**Where.** Status colours everywhere; `12_PRODUCT_FRONTEND.md`.

### Envelope / `meta.split_regime`
**Meaning.** Every API response is `{data, meta}`. `meta` carries the split regime, sources,
row count, thresholds and notes.
**Why it matters.** `metric_response()` **raises an error** if a metric route omits
`split_regime`, so an unlabelled metric cannot leave the API.
**Example.** The registry delta response carries `split_regime: "3-event"` and the area
rule in `notes` `[p7_registry.json]`.
**Where.** Under each chart (provenance line and regime chip); `api/main.py`.

### Evidence file
**Meaning.** A JSON or Markdown file written by a script into `docs/evidence/`. It is never
edited by hand.
**Why it matters.** Every number in every document must trace to one. If a figure cannot
be regenerated, it is removed.
**Example.** `p4_results.json` holds the ladder, heads, sources and per-class metrics.
**Where.** `KAVAL/docs/evidence/`; this glossary's square-bracket citations.

### export_layer
**Meaning.** The analyst tool that prepares downloads of the parcel layer (GeoJSON or CSV),
the crop-area summary, or the routed worklist when given a budget.
**Why it matters.** The brief asks for downloadable predictions. Before this tool existed,
the LLM refused the export query and was still scored a pass, which an audit caught.
**Example.** A full layer of 14,310 rows, or a 500-row routed queue with `budget=500`
`[p7_analyst_verification.json]`.
**Where.** Analyst view; Field worklist Export buttons (`/export`).

### Fallback chain
**Meaning.** The order in which the analyst tries LLM providers: Anthropic (Claude) if a key
exists → Gemini free tier → Groq or OpenRouter → any OpenAI-compatible URL → local model →
offline planner.
**Why it matters.** The analyst always answers, and every answer names the planner that
produced it.
**Example.** The Gemini chain is 3.8-flash → 3-flash-preview → flash-lite-latest. Which of
them answers changes from run to run with Gemini's load; the evidence records it per
question `[p7_analyst_verification.json → llm_planner.answered_by]`.
**Where.** Analyst answer chip ("LLM · gemini:…" or "offline planner — not LLM");
`api/llm.py`.

### FastAPI
**Meaning.** The Python web framework that serves KAVAL's API, on port 8077.
**Why it matters.** The UI and the analyst read only from the API. No number is hard-coded
in the frontend.
**Example.** `/audit/worklist`, `/summary/registry-delta`, `/validation/ladder`, `/export`.
**Where.** `api/main.py`; `10_API_ANALYST.md`.

### Gemini free tier
**Meaning.** Google's no-cost Gemini API access.
**Why it matters.** It is the model on which the analyst's LLM planning is actually
verified, because an Anthropic key could not be funded.
**Example.** The 6 brief + 3 product questions pass 9/9, and the 2 extended questions
(parcel lookup, calibration) pass 2/2. A typical answer takes a few seconds
`[p7_analyst_verification.json → llm_planner]`.
**Where.** Analyst view; talk §4 AI-5.

### get_parcel
**Meaning.** The analyst tool that returns one parcel's full audit trail by its `parcel_id`:
declared and predicted crop, calibrated and raw confidence, P(label needs correction),
trust score and its components, capture event, bag size, photo distance and geometry
source.
**Why it matters.** Before this tool existed, a question about a named parcel came back
"not found". It is the analyst's version of the parcel panel.
**Example.** Parcel 152_399_1 is DISPUTED: calibrated confidence 97.1%, trust 0.85,
P(label needs correction) 81.7% (`3-event`) `[p7_analyst_verification.json →
offline_planner.extended]`.
**Where.** Analyst view; Parcel panel.

### Grounding check
**Meaning.** The verifier compares every number in an LLM answer with the tool results, and
screens the wording against banned terms.
**Why it matters.** It catches arithmetic slips and banned wording before anyone relies on
them.
**Example.** The model sometimes states a figure no tool returned: a mis-rounding, or a
number it derived itself. The check flags each one, per question, in
`[p7_analyst_verification.json → llm_planner]` (`ungrounded_numbers`,
`language_violations`).
**Where.** `scripts/p7_verify_analyst.py`; review Q7 in the talk.

### Leaflet
**Meaning.** The open-source JavaScript map library behind the Audit map.
**Why it matters.** It draws parcels coloured by agreement status over an OpenStreetMap
basemap. Parcels are sampled, not taken from the top of the file, which would bias the map
(correction #15).
**Example.** Clicking a parcel opens the parcel panel.
**Where.** Audit map.

### LLM
**Meaning.** A large language model.
**Why it matters.** In KAVAL it plans tool calls and writes prose. It never produces a
metric of its own.
**Example.** Claude is first in the chain whenever a key exists, but its planning is **not
verified** `[p7_analyst_verification.json → does_not_verify]`.
**Where.** Analyst view.

### Local model (llama.cpp / Qwen2.5-7B)
**Meaning.** An open-weight model (Qwen2.5-7B-Instruct) served by llama.cpp's
`llama-server` on this machine at port 8078. No key or cost is involved.
**Why it matters.** It is a keyless fallback. It works but is slow on a laptop CPU, and it
is labelled as such on each answer.
**Example.** Started with `KAVAL/scripts/serve_local_llm.sh`.
**Where.** Analyst answer chip; `api/llm.py`.

### Offline planner
**Meaning.** A keyword-based router that uses the same typed tools when no LLM is reachable.
**Why it matters.** The panel always works. It is labelled "offline planner — not LLM", and
it does not guess.
**Example.** 9 of 9 questions pass by function and over HTTP. "What is the capital of
France?" gets 0 tool calls and a list of what it can answer `[p7_analyst_verification.json
→ offline_planner]`.
**Where.** Analyst view.

### Parcel panel
**Meaning.** The side panel that opens on clicking a parcel. It shows the full audit trail:
declared and predicted crop, confidence, P(wrong), trust breakdown, capture event, photo
distance, geometry source and suggested correction.
**Why it matters.** Every status can be explained from one screen.
**Example.** "Parcels sharing this photograph" shows the bag size, which can be as high as
43 `[gt_forensics.json]`.
**Where.** Audit map; worklist rows.

### Planner
**Meaning.** The component that decides which tools to call, and in what order, for a
question.
**Why it matters.** Planning is what an LLM adds. Verification is recorded separately for
each planner.
**Example.** For "Compare GSE and Presto", the planner chose the `leakage_ladder` tool
`[p7_analyst_verification.json]`.
**Where.** Analyst answer chip.

### Provenance
**Meaning.** The record of where every file came from: source, date, licence, transform and
checksum, kept in `data/PROVENANCE.md`.
**Why it matters.** `provenance.require(path)` refuses to load any file without an entry.
Supplied and acquired data are kept clearly separate.
**Example.** The TN Agrisnet registry entry records that no licence statement was found and
that the data is treated as internal analysis only `[p1_registry_acquisition.json]`.
**Where.** Provenance line under each chart; `03_DATA_ACQUISITION.md`.

### React
**Meaning.** The JavaScript UI library for the frontend (React 18, TypeScript, Vite).
**Why it matters.** It hosts the six views and reads every number from the API.
**Example.** Tabs: Audit map, Village audit, Field worklist, Auto-clear, Leakage Ladder,
Analyst.
**Where.** `KAVAL/frontend/`; `12_PRODUCT_FRONTEND.md`.

### Thresholds rail
**Meaning.** The left-hand panel of sliders: `confidence_high` (default 0.80),
`trust_floor` (0.35) and `trust_high` (0.65). Defaults come from the API.
**Why it matters.** Thresholds you cannot see make an audit you cannot check. Moving one
re-derives the map, the worklist and the saving from the same server rule.
**Example.** Raise `trust_floor` and more parcels become UNVERIFIABLE. The chip "moved from
config" appears `[p6_audit.json → thresholds]`.
**Where.** Audit map, Field worklist and Auto-clear views.

### Typed tool
**Meaning.** A function with a fixed, validated input and output schema that the analyst
may call.
**Why it matters.** The LLM can only reach data through these tools, so every figure comes
from code.
**Example.** The twelve tools are `query_parcels`, `crop_area_summary`, `compare_to_registry`,
`confusion_report`, `leakage_ladder`, `route_verification_budget`, `auto_clear_summary`,
`status_summary`, `ground_truth_forensics`, `get_parcel`, `calibration_report` and
`export_layer`
`[p7_analyst_verification.json → tools_available]`.
**Where.** Analyst view, "Tools the analyst can call".

---

## 9. Project names, places and process

### AI-1 to AI-6
**Meaning.** KAVAL's six AI components: AI-1 FTW field delineation; AI-2 GSE and Presto
embeddings; AI-3 attention-MIL; AI-4 calibration, confident learning and trust; AI-5 the
agentic analyst; AI-6 vision-language photo check (conditional).
**Why it matters.** Each is load-bearing. Remove one and something downstream stops
working.
**Example.** AI-3 failed as a classifier and works as an audit signal (+16.2 pp)
`[p5_mil.json]`.
**Where.** `plan.md` §3; `01_ARCHITECTURE.md`; talk §4.

### Corrections log
**Meaning.** The numbered record of 23 mistakes we made in our own work and corrected.
**Why it matters.** For a project built on validation honesty, it is the strongest
evidence we have. We volunteer it.
**Example.** #2, the routing "lift" that was a tautology. #18, "within 8% of the registry",
which compared different footprints.
**Where.** `docs/team/13_CORRECTIONS.md`; `progress.md`.

### CropSight
**Meaning.** The team's earlier, superseded Task 3 proposal.
**Why it matters.** It is retained only as evidence. Its Earth Engine export of GSE and
seasonal features feeds the feature store.
**Example.** GSE held for all 14,611 parcels came from it.
**Where.** `plan.md` §12.

### DATA_REQUEST.md
**Meaning.** Our list of what FarmwiseAI could supply: FMB geometry, the survey photographs,
and confirmation of the 911/912 boundary. Real surveyor productivity is a lower priority.
**Why it matters.** None of these blocks the prototype, but each unlocks a specific result.
**Example.** 911/912: all 1,175 records coded 912 lie inside polygon 911 `[p7_registry.json →
attribution_test.pair_geometry]`.
**Where.** `KAVAL/docs/DATA_REQUEST.md`; talk §9.

### KAVAL
**Meaning.** The project name, from Tamil காவல், "vigil" or "keeping watch". An agentic
satellite audit system for India's Digital Crop Survey.
**Why it matters.** The name carries the thesis: the classifier is the instrument, and the
product is the audit.
**Where.** Everywhere.

### M1–M4
**Meaning.** Team role placeholders: M1 Data & Geospatial, M2 ML & Validation, M3 Audit &
Backend, M4 Product & Frontend. Names are to be confirmed.
**Why it matters.** M2 holds a veto over any number the project reports.
**Where.** `plan.md` §9; proposal §11; talk running order.

### Phase and phase gate
**Meaning.** The ten phases (0 evidence to 9 report), each closed by an acceptance gate that
must pass before the next phase opens.
**Why it matters.** Order prevents leaks. For example, Phase 4's out-of-fold probabilities
must exist before Phase 6 builds trust signals on them.
**Example.** The Phase 2 gate **failed**: match rate 73.3% against 80% required, and
one-point-per-field 20.4% against 60%. It was explained in writing, with the fallback in
place `[p2_ftw_delineation.json → gate]`.
**Where.** `plan.md` §6; `progress.md`; `PHASE2_GATE_EXPLANATION.md`.

### Sivagiri taluk, Tenkasi district
**Meaning.** The study area in southern Tamil Nadu: 25 supplied polygons, made up of 21
revenue villages and 4 Reserve Forests.
**Why it matters.** It is one taluk and one season, so we make no claim about transfer to
other regions.
**Example.** Bounding box 77.270–77.550° E, 9.174–9.420° N `[p1_stac_acquisition.json →
aoi_bounds_wgs84]`.
**Where.** Audit map; talk §1.

### Viswanathaperi 911/912
**Meaning.** Two revenue villages (Part-1, code 911; Part-2, code 912) where recorded codes
and supplied polygons disagree sharply.
**Why it matters.** The pattern suggests a boundary or labelling issue in the supplied
layer. It does not prove one. The registry cannot settle it, because it is compiled from
the recorded codes (correction #22).
**Example.** Records coded 911: 398 inside polygon 911 and 720 inside 912. Records coded
912: 1,175 inside 911 and 0 inside 912 `[p7_registry.json → attribution_test]`.
**Where.** Village audit; `DATA_REQUEST.md` §3; review Q5 in the talk.
