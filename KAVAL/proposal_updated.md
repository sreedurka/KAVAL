# KAVAL
## An Agentic Satellite Audit System for the Digital Crop Survey

**FarmwiseAI Campus Product Challenge — Task 3: Satellite-Embedding-Based Crop Classification**

*Proposal stage. A working prototype is not required at this stage; the measurements in
Section 2 were produced during proposal preparation and are reproducible from the scripts
cited.*

---

## 1. Challenge, Title and Objective

**Chosen challenge:** Task 3 — Satellite-Embedding-Based Crop Classification.

**Project title:** KAVAL — an agentic satellite audit system for the Digital Crop Survey.
*(Kaval — காவல் — Tamil for vigil, or keeping watch.)*

**Objective.** To build a system that classifies every agricultural parcel in the study
area from satellite foundation-model embeddings, and then uses that classification to do
something the classification alone cannot: decide, for each surveyor-submitted crop
record, whether to **trust it, re-verify it, or retire the field visit entirely**.

The deliverable is a parcel-level crop layer with calibrated confidence — everything Task 3
asks for — wrapped in the decision it was always meant to support: where to send a
limited field-verification budget, and what it is worth.

---

## 2. What We Measured — and Then Built

Most proposals to this challenge will describe what a team intends to do. We began by
measuring the data you supplied, because what we found changed what we think should be
built — and then we built enough of it to know the approach works.

Every figure in this document regenerates from a committed script in `KAVAL/scripts/`,
writing to `KAVAL/docs/evidence/`. Nothing here is an estimate unless it says so.

### 2.1 The 14,643 ground-truth records are 3,204 observations

Every record in `Ground_truth_Points.csv` carries an `image_path`. Grouping by it:

| | |
|---|---:|
| Survey records | 14,643 |
| Distinct capture events | **3,204** |
| Label inflation | **4.57×** |
| Maximum parcel labels from a single capture event | **43** |
| Records sitting inside a multi-parcel capture event | **93.8%** |
| Capture events containing more than one crop label | **0** of 3,204 |

Within a capture event, the crop, the stage, the village, the timestamp and the photograph
coordinates are identical — in all 3,204 groups, without a single exception. The label is
attached to the *event* and copied across its members. The parcels sharing a label sit a
median 117 m apart, so the label behaves as a spatially smoothed block rather than a
per-parcel observation.

The consequence for per-class evaluation is severe:

| Crop | Records | **Independent capture events** | Inflation |
|---|---:|---:|---:|
| Rice (Paddy) | 9,221 | 2,322 | 4.0× |
| Coconut | 2,633 | 517 | 5.1× |
| Maize | 1,568 | **162** | 9.7× |
| Banana | 655 | **66** | 9.9× |
| Sugarcane | 433 | 120 | 3.6× |
| Marigold | 36 | **3** | 12.0× |
| Sorghum | 30 | 4 | 7.5× |
| Cassava | 24 | 3 | 8.0× |
| Cotton | 19 | 2 | 9.5× |
| Groundnut | 16 | 2 | 8.0× |
| Mango | 6 | **1** | 6.0× |

A per-class F1 score for Marigold rests on three field observations. Reported without that
context, it is not a performance estimate.

### 2.2 The photograph does not document the parcel

Distance from each record's photograph coordinate to the parcel it labels:

| median | p90 | p99 | max | over 1 km |
|---:|---:|---:|---:|---:|
| **1,436 m** | 3,808 m | 6,582 m | 8,559 m | **62.3%** |

Photograph coordinates cluster at a small number of fixed points per village while the
parcels they label are scattered kilometres away — a pattern consistent with device sync
or upload-location capture rather than in-field geotagging. Whatever the cause, the
photograph cannot serve as per-parcel visual evidence, and any system treating it as such
is mistaken about what it holds.

Separately: 645 records store two coordinates in a single cell, and 13 geocode outside the
study area.

### 2.3 The Leakage Ladder

We acquired Google Satellite Embedding and seasonal Sentinel-1/2 features for all 14,611
parcels through Earth Engine and trained a classifier. We then held the model, the
features and the hyper-parameters **completely fixed**, and varied only the
cross-validation split.

| # | Validation split | Accuracy | Macro F1 | What it leaks |
|---|---|---:|---:|---|
| 1 | Random row split | **89.7%** | 0.772 | Near-duplicates from one capture event land on both sides |
| 2 | Grouped by parcel | **89.5%** | 0.769 | Capture-event siblings still span the split |
| 3 | **Grouped by capture event + shared field** | **81.2%** | **0.528** | Nothing from the same field visit or the same delineated field |
| 4 | Grouped by village (spatial) | **70.8%** ± 9.5% | 0.326 | Nothing; must generalise to unseen geography |

*LightGBM held fixed across all four rows, 76 features (64-d Google Satellite Embedding +
12 seasonal Sentinel-1/2), 14,310 parcels, 5-fold. Identical hyper-parameters
throughout — the model is held constant precisely so the split is the only variable.*

Accuracy falls **18.9 points** and macro F1 falls **0.446** across these rows, with no
change to the model whatsoever.

**Row 2 is the row we want to draw attention to.** Grouping by parcel is the obvious
leakage control, and it is what the brief's phrase *"parcel leakage"* naturally suggests.
It changes essentially nothing — 0.2 points — because parcels are already one-to-one with
rows, so the grouping has almost nothing to group. A team that applies the obvious control
will believe it is protected and will not be. Only grouping by capture event exposes the
drop.

### 2.4 More findings from building the pipeline

Since drafting this proposal we built the acquisition, geometry and modelling stages. Further
findings came out of that work, each reproducible from a script in `KAVAL/scripts/`.

**The geographic-generalisation figure is too noisy to quote precisely.** With only 21
villages split across 5 folds, the village-grouped regime has a fold-to-fold standard
deviation of ±9.5 points. We originally grouped it by the *recorded* village code and
measured 69.1%; after correcting it to group by the village each parcel physically falls
in, it reads 70.8%. That is 0.18 standard deviations apart — the correction was right on
principle, but its measured effect is indistinguishable from fold noise. We quote the
village regime as "roughly 70%, ±10" and treat the capture-event regime as the headline,
because it is the only one with enough groups to be stable.

**Survey village codes and the supplied village polygons disagree, almost entirely in one pair.**
Spatially joining each survey point to the supplied village polygons, 1,930 of 14,611
points (13%) fall inside a different village than their record's code
(`p7_registry.json`, `attribution_test.pair_geometry`). 1,895 of those are a single pair
— Viswanathaperi Part-1 and Part-2 (codes 911 and 912).

Our first reading was that the survey had mis-recorded the codes. We then reversed that,
on the grounds that the Tamil Nadu Agrisnet registry agrees with the recorded codes. That
reversal overreached, and we have withdrawn it. The registry is the survey's own published
aggregate, compiled by the **recorded** village code, so it agrees with the recorded codes
by construction. Its numbers — mean |Δ share| **0.0183** by recorded code against
**0.1053** by polygon membership across the pair, and **0.0569** against **0.0655** across
all villages (`attribution_test`, Rabi 2024, 3-event split regime) — cannot tell us which
attribution is right. They also show the gap is a two-village effect, not a taluk-wide one.

The only independent evidence is geometric. Every one of the 1,175 records coded 912 falls
inside polygon 911 (Part-1), and polygon 912 contains none of them; of the records coded
911, 398 fall inside 911 and 720 inside 912 (`pair_geometry`). That pattern **suggests** a
boundary or labelling error in the supplied layer, but it does not prove it. Settling it needs
cadastral records or a field check, which only FarmwiseAI can supply.

We present it as a question for FarmwiseAI, not a finding against anyone. Mismatches like
this are inherent when survey records and boundary layers are maintained at national scale
by different processes, and nothing downstream of the survey currently flags them. It
matters operationally: village-level crop-area statistics come out differently depending on
which attribution is used, and today nobody would notice.

Two consequences we act on. The registry comparison attributes by recorded code, because
that is how the registry itself is compiled — a like-for-like choice, not a verdict. The
leakage protocol still groups by polygon membership, because spatial blocking depends on
where a parcel physically *is*, not on which label the polygon carries.

**The same row stores the same date in two different formats.** `timestamp` is MM-DD-YYYY
while `image_timestamp`, in the same row, is DD-MM-YYYY. Parsed naively, a survey that ran
for eight days appears to span June to December. The survey actually ran **6–13 November
2024**.

**We compared the two foundation embeddings the brief names, and GSE wins clearly.** Under
capture-event-grouped validation (regime 3-event), MLP head, identical rows and folds for
every source (14,310 parcels, 5-fold; `p4_results.json` → `sources`):

| Feature source | Features | Accuracy | Macro F1 |
|---|---:|---:|---:|
| Google Satellite Embedding (GSE) only | 64 | 81.5% | 0.563 |
| GSE + seasonal Sentinel-1/2 | 76 | 81.7% | 0.564 |
| Seasonal Sentinel-1/2 only | 12 | 73.7% | 0.399 |
| Presto only | 128 | 74.2% | 0.452 |
| GSE + Presto | 192 | 81.3% | 0.559 |

Each source is paired against GSE only, fold by fold (`source_comparisons`):

| Source | Mean Δ macro F1 | SD of Δ | Folds favouring | Reading |
|---|---:|---:|---:|---|
| Presto only | −0.111 | 0.011 | 0/5 | A real gap: ten times its own spread, and every fold agrees |
| GSE + Presto | −0.004 | 0.006 | 1/5 | Underpowered; no measurable gain from combining |
| GSE + seasonal | +0.0008 | 0.008 | 2/5 | Underpowered; no measurable gain |
| Seasonal only | −0.165 | 0.033 | 0/5 | A real gap |

As a standalone source, the annual Google embedding beats Presto on this data, and adding
Presto to it adds nothing we can measure. That is a statement about Presto *as we could
feed it here*, not a verdict that Presto is the weaker model. Four things limit it
(`p3b_presto.json`):

- **Processing level.** Presto was pretrained on Sentinel-2 L1C top-of-atmosphere
  reflectance; we feed L2A surface reflectance. A small systematic shift, reported rather
  than corrected.
- **Coarse meteorology.** Temperature and precipitation come from reanalysis grids, so each
  is constant across the taluk within a month. They carry seasonality, not spatial signal.
- **Parcel means, not pixels.** Each parcel gets one monthly series, the mean over its
  pixels. Presto was pretrained on per-pixel series.
- **Frozen encoder.** We use the pretrained 128-d embedding with no fine-tuning, fed to the
  same MLP head and folds as GSE.

Terrain comes from the Copernicus DEM (GLO-30), substituted for SRTM in Presto's static
input; temperature from NASA POWER, substituted for ERA5-Land.

One structural reason stands out, and it is useful to FarmwiseAI in its own right.
Sentinel-2 had a cloud-free observation for **92.2%** of parcel-months across the year, but
only **38.1%** in November 2024 — the survey month itself, in the north-east monsoon
(`s2_observed_fraction`, `s2_worst_month`). Any optical time-series model is missing most of
its evidence exactly when the survey is taken. GSE's annual summary, which draws on several
sensors including radar, is less exposed to that gap. For a crop survey timed to the
monsoon season, that is a practical reason to prefer the annual embedding.

**Twelve hand-engineered seasonal features buy nothing detectable.** The +0.0008 above is
well inside fold noise. We want to be precise about this one, because an earlier draft of
this proposal claimed the opposite: a first run had GSE-only *ahead* of GSE+seasonal, we
wrote it up as a finding, and re-running after a validation fix reversed the sign. **Neither
direction was a result.** The report generator now computes this verdict from the paired
per-fold deltas, so it cannot be restated by hand. Seasonal features *alone* are clearly much
worse, so the foundation embedding is doing the work.

We report this rather than quietly dropping it, because a comparison that flips sign
between runs is exactly the kind of thing the Leakage Ladder exists to catch.

We also found that a small MLP head beats gradient-boosted trees on these embeddings
(macro F1 0.564 versus 0.528, regime 3-event, 76 features; `p4_results.json` → `heads`),
which is consistent with the embedding being a learned continuous space rather than a set
of independent tabular features.

### 2.5 We built it, and here is what it does

The pipeline described in this proposal is running end to end. All figures below are at
the headline regime — capture-event-grouped, with parcels sharing a delineated field
unioned into the same group. Four results decide whether the product works.

**The MIL head loses as a classifier and wins as an audit instrument.** Treating each
capture event as a bag (§4, AI-3) made the classifier *worse*: -3.00 points of
accuracy and -0.0565 macro F1 against the per-parcel baseline, on identical folds.
We report that plainly. But the attention weights it produces are strongly informative:
among parcels sharing a photograph, those the model attends to least agree with the
surveyor's label **69.4%** of the time against **85.6%**
for the rest — a **+16.2 point gap**. The model learned which parcels in a
photo-bag are passengers.

We measure that gap against the **independently trained baseline**, not against MIL's own
prediction. Measuring it the obvious way gives a flattering **+22.8 points**, but
attention is the mechanism that produced MIL's prediction, so the model would be partly
agreeing with itself. The honest number is +16.2, and it is the one the system
actually gates on — had it fallen below two points, `bag_support` would have been dropped
from the trust score automatically.

**Confidence becomes trustworthy after calibration.** Raw model confidence averages
0.942 against an actual accuracy of 0.817 (MLP, regime 3-event) — it overstates by twelve
points, and nothing can be routed on it. Cross-fitted isotonic calibration brings Expected
Calibration Error from **0.1247 to 0.0046**, with mean confidence landing on
0.817 — the accuracy itself.

**Only 18.3% of parcels need looking at.** 2,617 of 14,310 carry a satellite
prediction differing from the declared crop. Routing a budget of 500 visits lands
essentially all of them on a disagreement, against 91 for random visiting — a
5.45× ratio.

We are careful about what that ratio means, because it is easy to oversell. It is pinned
at 1 ÷ 0.183 by construction for any budget below the number of available
disagreements: it measures **coverage, not ranking quality**, and any classifier can
enumerate its own disagreements. The operational value is the 18.3% itself —
four in five parcels need no attention at all. The part that *is* informative about
ranking is that routed parcels carry a mean calibrated confidence of **0.734**
against **0.652** across all disagreements, so the queue does put the
better-evidenced cases first.

**4,825 parcels (33.7%) can be cleared without a visit** — satellite and survey
agree at high calibrated confidence on a record whose provenance we trust — worth
**193 surveyor-days** of a 572-day baseline under a stated
productivity assumption.

We do not claim accuracy *within* that cleared set, because it is 100% by construction:
cleared means the model agreed. The quantity that matters — how often satellite and
surveyor are wrong in the *same* way — is **unidentified from this data**, since the
calibrator was fitted against the very label the status conditions on. We offer
7.6% as a rough proxy and say plainly that only an independent field audit
of a cleared sample can settle it. Designing that audit is work we would want to do in the
prototype period.

### 2.6 What follows from this

The brief sets a target of more than 95% accuracy, and states that spatial or parcel
leakage "will invalidate the claimed result". Our measurements say those two sentences are
in tension on this data. We could not reach 95% even under a random split, and the honest
figure is 81.7% (best head, MLP, capture-event-grouped with shared delineated fields unioned
in, 5-fold; `p4_results.json` → `headline`).

We think the right response is not to chase the number by loosening the validation. It is
to build the thing the number was a proxy for. So:

> **The classifier is the instrument. The product is the audit.**

Three consequences run through the rest of this proposal. **Disagreement between satellite
and survey is the product, not the error.** **We report the honest number and show the
dishonest one beside it.** **Weak performance on rare crops is a finding about the data,
not a modelling failure.**

A note on how we intend this. The Digital Crop Survey is a national-scale data collection
achievement, covering 461 districts and over 23 crore plots in Rabi 2024-25 [^dcs]. Provenance
artefacts are inherent to field programmes at that scale. What does not exist today is
anything downstream that detects them. That gap is the opportunity, and it is what we
propose to build.

---

## 3. Our Understanding of the Problem

In our own words.

The dataset you supplied is a Digital Crop Survey extract — village LGD codes, survey
numbers and subdivisions, declared crop, crop stage, and a geotagged photograph, collected
across Sivagiri taluk in November 2024, the Rabi 2024-25 season. This survey exists because
crop-area statistics have to come from somewhere, and they are load-bearing: they drive
crop insurance settlement, procurement planning, and drought and flood compensation. A
wrong crop label on a parcel is not a metric; it is a payment.

Producing those statistics currently requires a human to visit every parcel every season.
That is the cost the state carries. Satellite embeddings offer a way to reduce it — but not
by replacing the survey, because as Section 2.3 shows, a satellite classifier generalising
to unseen geography is right about 71% of the time (70.8%, village-grouped, regime 4, 5-fold),
and no department will settle insurance on that.

What a satellite classifier *can* do, reliably, is compare itself against each survey record
and flag where the two disagree. That is a much easier problem than being right in absolute
terms, and it is worth more, because it tells a department where to spend its next thousand
field visits.

So the technical problem is Task 3 as specified — link embeddings to parcels, aggregate,
train, predict class and confidence, validate without leakage. The product problem is what
to do with the output, and our answer is: triage the survey.

We note that we also have to solve a problem the brief assumes away. Task 3 asks for
parcel-level classification, but the supplied data contains ground-truth **points** and
village boundaries — no cadastral parcel geometry. Without polygons there is no parcel-level
area statistic, no zonal aggregation and no map. Section 4 explains how we generate them.

---

## 4. What We Propose to Build

KAVAL has six AI components. Each is load-bearing: remove any one and the system stops
working. We state this explicitly because a crop-classification demo can easily become a
map with a model behind it, and that is an explicit non-goal.

### AI-1 — Parcel delineation from satellite *(run; result below)*

We generate the parcel layer ourselves, running the pretrained **Fields of The World**
U-Net (EfficientNet-B7, CC-BY checkpoint) over bi-temporal Sentinel-2 across the taluk.

**We have run it on real imagery.** It produced **64,708 field polygons, median 0.11 ha,
13,062 ha across the whole taluk.**

We checked that against the Tamil Nadu Agrisnet registry, which we downloaded ourselves (it
is the survey's own published aggregate, not an independent measurement of the land), and the
first comparison we made was wrong, so we are stating the corrected one. The registry
reports 12,097 ha cropped across the 21 revenue villages. FTW's 13,062 ha looks close to
that, but it is a different footprint: it includes 736 ha inside Reserve Forest and all
non-village land. Restricted to the same 21 villages, FTW delineates **7,151 ha, which is
41% less than the registry**, and 26% less than the registry's annual-crop area
alone (9,602 ha).

So the delineation under-recovers cropped land even where it should be strongest. We cannot
isolate why with this data. The candidates are Rabi-only imagery windows that miss fallow or
late-sown fields, cloud-affected scenes, the Sentinel-2 processing-baseline mismatch, and
fields below our 500 m² floor. We report the shortfall rather than the coincidence.

The interesting part is where it does *not* work, and it gives FarmwiseAI a precise answer
to the question behind this component:

> **Satellite delineation recovers *physical fields*, not *legal parcels*.** Our 10,707
> matched survey points map onto 5,528 distinct fields — a mean of **1.94 legal parcels per
> physical field**, up to 19 in one. 46% of matched fields carry more than one parcel.

That is not a model deficiency. A survey record is a legal unit created by inheritance and
registration; a delineated field is the unit that is *farmed*. In smallholder Tamil Nadu
several legal parcels are routinely worked as one field, and no optical sensor can see a
boundary that exists only in a land register.

The per-crop pattern corroborates the mechanism: Sugarcane 56.5% on 432 points and Rice
41.4% on 9,201 (annual arable, cleanly bounded) against **Coconut 23.6%** on 2,627 — a perennial
tree crop, which a model trained on annual cropland does not bound as a field at all.
Coconut is 18% of this dataset.

So the honest verdict is that satellite delineation is a **strong substitute for land-use
mapping and a weak one for parcel mapping**, and that in this landscape the two differ by
about 2×. Points we cannot match keep a village-constrained Voronoi geometry, flagged as
such and never dropped; `geometry_source` carries the distinction into every downstream
output and into the Record Trust Score.

Two consequences we handle rather than note. Parcels sharing a delineated field carry
identical zonal features, so `field_id` is unioned into the leakage group key — measured
cost, about 0.8 accuracy points (82.0% grouped by capture event alone vs 81.2% with the field union, LightGBM, `p4_results.json` → `group_structure`). And a shared field is counted **once** in crop area. Taking the
whole field's area for each sharing parcel would have inflated the shared set 3.88× and the
feature-store total from 2,250 ha to 4,801 ha (`p2d_shared_field_area.json`). Apportioning
the field among its parcels fixes the total but still splits one physical field across
several crops, so crop area is aggregated at **field** level: each of the 2,545 shared
fields takes the crop with the largest apportioned area inside it, totals are unchanged,
and a `conflicted_area_ha` column exposes the fields whose records disagree, so the
majority rule does not hide them. Audited crop area is 2,137.6 ha, not 2,250 ha: 301
parcels (112.6 ha) have no satellite features and never reach the audit
(`p2d_shared_field_area.json`; audited total is the sum of `agreement_status_area_ha` in
`p6_audit.json`).

The full gate analysis, including the snap-tolerance trade-off curve, is in
`docs/PHASE2_GATE_EXPLANATION.md`. If FarmwiseAI can supply cadastral or FMB geometry we
will report IoU against it, which would put a number on how far this substitutes for
survey geometry beyond our study area.

### AI-2 — Satellite foundation-model embeddings, compared

**Google Satellite Embedding / AlphaEarth** (64-dimensional, 10 m, annual, 2017–2025) and
**Presto** (NASA Harvest's pretrained remote-sensing time-series transformer, MIT licence),
evaluated head to head and in combination, with seasonal Sentinel-1/2 features as a third
arm. This is the comparison the brief asks for, and the two models carry genuinely
different inductive biases — one an annual spatial summary, one a time-series encoder — so
the comparison is informative rather than ceremonial.

**It has run.** Under capture-event-grouped validation on identical folds, GSE alone reaches
81.5% / 0.563 macro F1 and Presto alone 74.2% / 0.452; combining them gives 81.3% / 0.559,
no measurable gain (`p4_results.json` → `sources`, `source_comparisons`). We read this as a
result about Presto as we could feed it here — L2A rather than L1C input, taluk-scale
meteorology, parcel-mean rather than per-pixel series, a frozen encoder — and not as a
verdict on the model. Section 2.4 gives the paired deltas and the caveats in full.

### AI-3 — Multiple-Instance Learning over capture-event bags

This is our methodological core, and it follows directly from Section 2.1.

A capture event is not 43 independent labelled examples. It is a **bag** of parcels
carrying a single bag-level label, and some members are passengers. So we model it as
what it is: an attention-based MIL head that learns which bag members actually support
the declared crop.

This does two things. It should improve the classifier, because it stops treating copied
labels as independent evidence. More importantly, it produces something a per-parcel
classifier cannot — a **per-parcel attention weight** measuring how much each parcel
actually resembles the crop the surveyor declared. That weight is an audit signal, and we
expect it to be worth more than the accuracy gain.

The dataset's central defect becomes the modelling framework.

### AI-4 — Confident learning, calibration and the Record Trust Score

**Confident learning** over out-of-fold probabilities estimates P(observed label ≠ true
label) per record — which lets KAVAL say *which* records are likely wrong, not merely that
some are. **Isotonic calibration**, fitted on validation folds only, turns model scores
into probabilities; we report Expected Calibration Error alongside accuracy, because an
uncalibrated confidence cannot route a budget.

These combine into a published, interrogable **Record Trust Score** built from: bag size,
photograph distance, MIL attention weight, stage–crop plausibility, mixed-crop declaration,
geometry source, and within-parcel embedding heterogeneity. The weights are published. A
trust score nobody can interrogate is not an audit.

### AI-5 — Agentic analyst

The product surface is a natural-language agent planning over twelve typed tools
(`query_parcels`, `crop_area_summary`, `compare_to_registry`, `confusion_report`,
`leakage_ladder`, `route_verification_budget`, `auto_clear_summary`, `status_summary`,
`ground_truth_forensics`, `get_parcel`, `calibration_report`, `export_layer`) that wrap the
API. `export_layer` prepares a download (URL, row count, columns); the file itself streams
from `/export`. `get_parcel` returns one parcel's full audit trail by `parcel_id`, and
`calibration_report` returns expected calibration error before and after calibration.
`query_parcels` filters on the satellite-predicted crop (`crop`) and on the declared crop
(`declared_crop`), and `crop_area_summary` takes a `village`. We added the last two tools
and the two parameters after live testing showed three failures: crop area for a named
village often failed because the model saw a truncated village table, a parcel lookup came
back "not found", and a calibration question was answered by improvising from unrelated
tools.

It answers every analysis request listed in the brief, end to end, and **every answer cites
the parcels it used**. An audit system whose analyst asserts numbers without provenance
defeats its own purpose. The agent never computes metrics itself; it calls tools, because
model arithmetic is not evidence.

**Which model plans.** The planner layer does not depend on one vendor. It uses the first
available of: Claude (if an Anthropic key is set); Gemini's free tier, falling through
`gemini-3.8-flash` → `gemini-3-flash-preview` → `gemini-flash-lite-latest`; Groq or
OpenRouter; any OpenAI-compatible URL; a local, keyless Qwen2.5-7B served by llama.cpp;
and finally an offline keyword planner. Every answer names the model that produced it, and
the offline planner is labelled "not LLM" on every reply. The analyst therefore runs on a
free tier or on a keyless local model, which matters for a department with no LLM budget.

**What we measured.** Planning is verified on Gemini's free tier: the 6 brief and 3 product
questions pass 9/9, and the 2 extended questions (parcel lookup, calibration) pass 2/2
(`scripts/p7_verify_analyst.py --llm` → `docs/evidence/p7_analyst_verification.json` →
`llm_planner`, which records per question which model in the fallback chain answered, the
tools it chose, its time, and any figure not traceable to a tool result). Which model
answers and how long it takes change from run to run; a typical answer takes a few
seconds. The weakness is stable: the model sometimes skips a secondary tool call or states
a figure no tool returned (a mis-rounding, or a number it derived itself). The grounding
check flags these, and every answer shows its tool calls so they can be checked. **Scope:** this verifies
planning by Gemini. It is not evidence about Claude, which we could not test because the
Anthropic account could not be funded, and it is not evidence about the local model, which
has not been scored and is slow on a laptop CPU.

### AI-6 — Vision-language photo verification *(conditional)*

If FarmwiseAI can supply the photographs behind `image_path`, we run a vision-language
model to test whether each image depicts the declared crop and stage — closing the audit
loop with independent multimodal evidence. We hold paths, not pixels, so this component is
clearly marked conditional and the audit is designed to work without it.

### The output vocabulary

Every parcel gets an **agreement status**. This, not the crop class, is what the product
is organised around:

| Status | Meaning | Action |
|---|---|---|
| `CONFIRMED` | Satellite agrees with survey, high calibrated confidence and trust | Auto-clear — skip next season's visit |
| `DISPUTED` | Satellite disagrees at high confidence | Top of the field worklist |
| `UNCERTAIN` | Model cannot separate | Route by remaining budget |
| `UNVERIFIABLE` | Provenance too weak to test — huge bag, distant photo, mixed crop | Re-survey the **record**, not the parcel |
| `UNSEEN` | No survey record exists | Satellite-only prediction |

`UNVERIFIABLE` is the status we are most interested in. It is the one that says the problem
is with the evidence rather than the field, and no existing system reports it.

---

## 5. What We Will Demonstrate

A live walkthrough over Sivagiri taluk:

1. **The audit map** — every parcel coloured by agreement status, clicking through to the
   full audit trail: prediction, calibrated confidence, declared crop, bag size, photograph
   distance, trust components.
2. **Village audit panel against a real registry.** We acquired the Tamil Nadu Agrisnet
   village-wise Digital Crop Survey report — 21 villages, Rabi 2024, 12,097 ha — and
   compare the satellite's crop mix against it, sorted by divergence.

   Two caveats travel with that panel in the API payload itself, not just the
   documentation, so neither the interface nor the agentic analyst can overstate it.
   **It is compared as crop *share*, not hectares**, because our parcel sample covers a
   fraction of each village and an absolute comparison would measure sampling coverage
   rather than agreement. And **the registry is not independent**: Agrisnet publishes the
   aggregate of the same Digital Crop Survey whose parcel sample was supplied to us. So
   this audits the survey's own published numbers against satellite, which is genuinely
   useful, but it is not validation against a second survey and we do not present it as
   one.
3. **The field worklist with a budget slider** — move it to N visits, watch expected
   corrections update, with the random-baseline counterfactual shown beside it. The gap
   between routed and random visits is what KAVAL is worth.
4. **The auto-clear list** — parcels safe to skip next season, with the saving quantified
   in surveyor-days and every cost assumption stated.
5. **The Leakage Ladder, in-product** — not buried in an appendix. It is the credential.
6. **A negative control on protected land.** 25 polygons were supplied; 21 are revenue
   villages carrying ground truth. The remaining four are **Reserve Forest**
   (`village_co = 'YYY'`) — protected land, not unsurveyed farmland, as an earlier draft
   of this proposal wrongly assumed.

   Intersecting the field delineation with them, **734.7 ha (4.0%)** of
   18,385 ha of protected land is delineated as field-like, and one polygon
   (Naranapuram R.F) reads **37%**. We deliberately do **not** report this as encroachment.
   There is no ground truth inside these polygons, and the number is equally consistent
   with cultivation, with delineation false positives on canopy gaps and fire lines, or
   with another error in the supplied boundaries — 37% looks more like a mislabelled
   polygon than a third-encroached forest. What it produces is a bounded, ranked list of
   places worth a field visit, which is the whole thesis in miniature.

   The stronger test — running the classifier over those patches and confirming it returns
   *low* confidence — needs embeddings for geometry outside the surveyed parcels, and so
   needs Earth Engine access. We record it as not done rather than approximate it.
7. **The agentic analyst**, answering the brief's queries conversationally with citations.
8. **Exports** — classified parcel layer, confidence values, crop-area summary, worklist,
   as CSV and GeoJSON.

---

## 6. Architecture

```
                     ┌───────────────────────────────────────────┐
   ACQUISITION       │ GEE · Presto · FTW · registry · boundaries │
                     └──────────────────┬────────────────────────┘
                                        ▼
   GEOMETRY          AI-1  field-boundary segmentation → parcel polygons
                                        ▼
   LINKAGE           point → polygon → survey number; capture-event bags
                                        ▼
   FEATURES          AI-2  GSE (64-d) ‖ Presto ‖ seasonal S1/S2 → feature store
                                        ▼
   LEARNING          AI-3  attention-MIL over bags  +  baseline heads
                                        ▼
   AUDIT             AI-4  confident learning · isotonic calibration
                     AI-6  VLM photo check (conditional)
                                        ▼
                          Record Trust Score  +  agreement status
                                        ▼
   ECONOMICS         verification routing under a budget of N visits
                                        ▼
   SURFACE           FastAPI  ←  AI-5 agentic analyst  →  React + Leaflet
```

### Technology stack

| Layer | Choice | Why |
|---|---|---|
| Data acquisition | Google Earth Engine (Python API) | Where GSE, Sentinel-1/2 and agro-climate all live |
| Geospatial | geopandas, shapely, rasterio | Standard, well-documented for point/polygon work |
| Segmentation | PyTorch + FTW pretrained U-Net (EfficientNet-B7) | Pretrained; avoids training a segmenter from scratch |
| Embeddings | Google Satellite Embedding; Presto (NASA Harvest) | Both named in the brief; both pretrained |
| Baseline heads | LightGBM, Random Forest, logistic regression, MLP | Fast, strong on dense embeddings, easy to compare fairly |
| MIL head | PyTorch, gated attention pooling | Small model; the bag structure is the point, not the depth |
| Label audit | cleanlab-style confident learning; scikit-learn isotonic | Well-understood, defensible methods |
| Backend | FastAPI + Pydantic v2 | Typed endpoints double as the agent's tool surface |
| Agent | Provider-agnostic tool calling: Claude if a key exists, else Gemini free tier, Groq/OpenRouter, a local Qwen2.5-7B (llama.cpp), or an offline keyword planner | Planning over tools with cited answers; every answer names the model that wrote it |
| Frontend | React + TypeScript + Vite + Leaflet | Map-first product interface |
| Reproducibility | Committed scripts writing to `docs/evidence/`; `PROVENANCE.md` | Every number regenerable; every file sourced |

Compute is modest. The heaviest step is FTW inference over the taluk; everything else runs
on CPU. No large-scale training is proposed.

---

## 7. Capabilities Mapped to the Brief

Every capability Task 3 requires, and where we deliver it.

| Required capability | Where KAVAL delivers it |
|---|---|
| Inspect embeddings; associate with parcels and labels | Phase 3 feature store, on the Phase 2 parcel layer, with invariant assertions on every join |
| Aggregate multiple observations per parcel | Zonal mean **and** standard deviation per parcel; the std is retained as a heterogeneity audit signal; alternatives tested and justified |
| Train and compare classifiers / lightweight heads | LightGBM, RF, logistic, MLP, and the attention-MIL head, all on identical folds |
| Predict crop class, probability and confidence per parcel | Calibrated per-class probabilities for every parcel, with ECE reported |
| Identify low-confidence or unusual embedding patterns | `UNCERTAIN` and `UNVERIFIABLE` statuses, plus MIL attention weight and within-parcel heterogeneity as separate "unusual" signals |
| Validate without parcel, neighbourhood, geography or season leakage | The Leakage Ladder; capture-event grouping as the headline regime; village grouping reported beside it |
| Parcel-level output with identifier, crop, confidence, review status | Parcel export with agreement status as the review status |
| Map or analytical view of classes and low-confidence parcels | React + Leaflet audit map |
| Crop-wise area and class-distribution summary | Village and taluk area summaries, against the registry |
| Comparison of embedding sources / model heads | GSE, Presto, seasonal and their combinations, five sources paired fold by fold (§2.4); four baseline heads plus the attention-MIL head on identical folds |
| Validation report: accuracy, macro F1, per-class P/R/F1, confusion matrix | Phase 9, under every split regime, with per-class effective n |
| Reproducible embedding-to-label pipeline | Scripts + `PROVENANCE.md`; no manual steps |
| Downloadable predictions | CSV and GeoJSON exports |

On the performance target: we will report accuracy, macro F1 and per-class metrics under
all four split regimes. **We will not claim more than 95%.** Our measured expectation is
81.7% (MLP head) under capture-event-grouped validation, and we would rather submit a
number we can defend than one we cannot.

---

## 8. Data and Access Required

The supplied files are a reference sample, not the working dataset. The table distinguishes
FarmwiseAI-provided resources from what we source ourselves, as the challenge requires.

| Need | Source | Class |
|---|---|---|
| Satellite embeddings, 64-d, 10 m | `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`, Earth Engine | **Held** |
| Presto embeddings | `github.com/nasaharvest/presto` (MIT), run over monthly Sentinel-1/2 series from STAC, Copernicus DEM GLO-30 terrain, CHIRPS and NASA POWER meteorology | **Acquired and run** — 128-d embedding for all 14,611 parcels |
| Sentinel-2 L2A, Sentinel-1 GRD | **STAC — Element84 / Planetary Computer, no credentials needed** | **Acquired** |
| Field-boundary model | Fields of The World pretrained U-Net (CC-BY B7) | **Acquired and run** |
| Agro-climate | CHIRPS (public HTTP) | **CHIRPS acquired**; ERA5-Land needs a CDS key we lack |
| Village crop registry | **TN Agrisnet village-wise Digital Crop Survey report** | **Acquired** — 21 villages, Rabi 2024 |
| DCS methodology and schema | AgriStack / DA&FW published documentation | Acquired |
| Ground-truth points | **FarmwiseAI** | Supplied |
| Administrative boundaries (25 villages, taluk, district) | **FarmwiseAI** | Supplied |
| **Cadastral / FMB parcel geometry** | **Request to FarmwiseAI** | Requested — AI-1 is our primary path regardless |
| **Survey photographs behind `image_path`** | **Request to FarmwiseAI** | Requested — AI-6 is conditional on this |

**What we no longer need.** Phase 1 was planned around Google Earth Engine access. That
turned out to be unnecessary for most of it: Sentinel-1 and Sentinel-2 are served through
public STAC endpoints (Element84 on AWS Open Data, Microsoft Planetary Computer) with no
credentials at all, which is how the field delineation above was actually run. Only
Google's Satellite Embedding is Earth-Engine-only, and we already hold it for every parcel.

**Access we would still need:** an Earth Engine account to extend embeddings beyond the
14,611 surveyed parcels (needed for the reserve-forest control and for any new geometry),
and a CDS key for ERA5-Land. The agentic analyst needs no paid model access: it runs on
Gemini's free tier or a keyless local model (§AI-5); Anthropic credit would let us verify
Claude's planning as well. No GPU cluster is required; the FTW inference above ran on CPU.

**Two requests.** Cadastral geometry would let us measure how well satellite delineation
substitutes for survey geometry — a result we think is valuable to FarmwiseAI independent
of this challenge. The photographs would enable AI-6. Neither is a blocker; both make the
result stronger.

---

## 9. Project Plan

Phases are gated: no phase opens until its predecessor's acceptance criteria pass. The
full plan, with gates and the risk register, is `KAVAL/plan.md`; live status is
`KAVAL/progress.md`.

**Most of this is already built.** We did not want to propose an architecture we had not
tested, so we implemented the pipeline end to end on the supplied reference sample.

| Phase | Status | What exists |
|---|---|---|
| 0 Evidence and framing | **Done** | Forensics and Leakage Ladder, §2 |
| 1 Acquisition and provenance | **Done**, one caveat | Record repair, provenance system; GSE, Sentinel-1/2 monthly series, FTW, registry, CHIRPS, NASA POWER, Copernicus DEM all acquired. Only MODIS LST needs credentials we lack, and nothing depends on it |
| 2 Parcel geometry | Gate **failed**, explained | FTW run on real Sentinel-2 (64,708 fields); it recovers physical fields, not legal parcels, so the gate failed. Village-constrained fallback in place; `docs/PHASE2_GATE_EXPLANATION.md` |
| 3 Feature store | **Done** | 14,611 parcels, 76 features, rebuilds from scripts alone |
| 4 Ladder, heads, sources | **Done** | Four regimes, four heads, five feature sources including GSE vs Presto, all on identical folds |
| 5 Attention-MIL | **Done** | Trained; negative result on accuracy, strong positive on the attention signal |
| 6 Trust, calibration, economics | **Done** | Calibration, confident learning, trust score, agreement status, budget router |
| 7 API and agentic analyst | **Done** | FastAPI, 17 routes; analyst over twelve typed tools. Planning verified on Gemini (9/9 core questions, 2/2 extended, `p7_analyst_verification.json` → `llm_planner`); Claude not verified |
| 8 React + Leaflet | **Done** | Six views, map coloured by agreement status; Playwright e2e across desktop, phone and dark (`frontend/e2e/`) |
| 9 Validation report | **Done** | Generated from evidence artefacts |

**What the three weeks after shortlisting would buy**, given the above:

| Week | Work | Milestone |
|---|---|---|
| **1** | Close the gaps in the GSE-vs-Presto comparison: per-pixel Presto series pooled to the parcel, L1C input to match Presto's pretraining, and a fine-tuned rather than frozen encoder; cadastral IoU for FTW if FMB geometry is supplied | A comparison that tests Presto on its own terms rather than ours; a delineation figure against legal parcels |
| **2** | Re-run the full stack on acquired data; AI-6 vision-language photo verification if images are supplied; extend beyond Sivagiri to test geographic transfer | Every result reproduced on independently sourced data; the village-grouped regime tested across taluks rather than within one |
| **3** | Product hardening, the demo, and an independent field-audit design for a CONFIRMED sample | A walkthrough a district officer could act on, and a protocol for measuring the one thing we cannot measure ourselves |

**The two research-risk phases were 2 and 5, and both have now resolved.** MIL did not beat
the baseline — we report it as a negative result and keep the component for its attention
signal, which does work. Satellite delineation has run on real imagery and failed its gate
for a reason we can explain (it finds physical fields, not legal parcels); the fallback is in
place.

---

## 10. Innovative Ideas — and What Happened to Them

We proposed six ideas and built them. Reporting how each turned out, including the two
that did not work, is more useful than restating the intentions.

### Worked

**1. Capture-event grouping as the correct leakage control.** The headline contribution.
Grouping by parcel — the obvious control, and what the brief's own wording suggests —
moves accuracy by -0.2 points. Grouping by capture event moves it by
-8.5. We believe this is a new observation about this dataset, and it changes
what any honest result on it should look like.

**2. `field_id` as a second leakage key.** Emerged from the work rather than the plan.
Once satellite delineation assigns several legal parcels to one physical field, those
parcels carry identical zonal features and leak exactly as capture-event siblings do. A
union-find over both keys collapses 2,921 bags into 2,269 components (`docs/evidence/p4_results.json` → `group_structure`) — a 22% loss of
independent groups — and costs a further 0.8 accuracy points that nobody would otherwise
have subtracted.

**3. The Record Trust Score.** Scores the record's *provenance* — bag size, photograph
distance, MIL attention, stage plausibility, mixed-crop declaration, geometry source,
within-parcel heterogeneity — with published weights. Nothing downstream of the Digital
Crop Survey appears to do this today.

**4. Satellite parcel delineation.** Ran on real Sentinel-2: 64,708 fields. Inside the 21
registry villages it delineates 7,151 ha against the registry's 12,097 ha, a
41% shortfall we cannot fully explain. The finding is sharper than the intention
was: it recovers **physical fields, not legal parcels**, at 1.94 parcels per field, and
matches annual arable about 2.4× better than perennial tree crops (Sugarcane 56.5% on 432 points against Coconut 23.6% on 2,627; `docs/evidence/p2e_ftw_match_detail.json`).

### Worked, but not the way we expected

**5. Multiple-Instance Learning over capture events.** As a classifier it **failed**:
-3.00 points of accuracy, -0.0565 macro F1 against the per-parcel baseline. We
report that as a negative result.

Its attention weights, however, separate cleanly: parcels the model attends to least agree
with the surveyor 69.4% of the time against 85.6% for the rest, a
**+16.2 point gap** measured against an independently trained model. So the component
earns its place as an *audit signal* while failing at the job we designed it for, and the
trust score consumes it through a gate that would have dropped it automatically had the
separation been weak.

**6. Verification economics.** Built, then substantially rewritten after we caught
ourselves overclaiming. Our first version reported a 5.58× "lift" from routing. It was
**exactly 1 ÷ base-disagreement-rate**, identical at every budget — a tautology that says
only that a classifier can enumerate its own disagreements. It is now reported as
*targeting efficiency*, explicitly labelled as pinned by construction, alongside the
measure that genuinely reflects ranking quality: routed parcels carry mean calibrated
confidence 0.734 against 0.652 across all disagreements. The operationally
useful number was never the ratio — it is that only **18.3% of parcels** need looking
at.

### Found without looking

**7. A village-code versus boundary-layer disagreement, for FarmwiseAI to resolve.** 1,895
of the 1,930 records whose code differs from their containing polygon sit in the
Viswanathaperi 911/912 pair, and all 1,175 records coded 912 fall inside polygon 911
(`p7_registry.json`, `attribution_test.pair_geometry`). That suggests a boundary or
labelling error in the supplied layer. We first argued the registry confirmed it; it
cannot, because the registry is compiled from the same recorded codes (correction #22).
Cadastral or field confirmation would settle it.

### Still open

**8. Presto on its own terms.** The GSE-vs-Presto comparison has run (§2.4): GSE wins
clearly as a standalone source and combining adds nothing measurable. What remains open is
whether that gap survives per-pixel input, L1C reflectance and fine-tuning. Until then we
claim the comparison, not a ranking of the two models.

**9. Vision-language verification of survey photographs** (AI-6) — conditional on
FarmwiseAI supplying the images behind `image_path`.

**10. Cross-season change detection and mixed-crop parcels** — GSE runs annually from 2017,
and 385 records declare more than one crop. Both are natural next steps that we
deliberately did not start, because finishing the audit loop mattered more than widening it.

---

## 11. Team and Responsibilities

Four members. *(Names to be filled in on submission.)*

| Member | Role | Owns | Phases |
|---|---|---|---|
| **M1** | Data & Geospatial | Earth Engine acquisition, provenance discipline, FTW parcel delineation, spatial linkage and invariants | 1, 2 |
| **M2** | ML & Validation | Embeddings and feature store, attention-MIL, enforcement of the leakage protocol across the project, metrics and the validation report | 3, 4, 5, 9 |
| **M3** | Audit Logic & Backend | Confident learning and calibration, Record Trust Score, verification economics, FastAPI, the agentic analyst | 6, 7 |
| **M4** | Product & Frontend | React + Leaflet interface, the agreement-status design language, demo, documentation and this proposal | 8, 9 |

Validation integrity is deliberately held by one owner (M2) with veto power over any number
the project reports, including numbers produced by other members. Given that our central
claim is about validation honesty, we did not want that responsibility diffused.

---

## 12. What We Will Not Attempt

Stated up front, so the scope is legible.

- We will not train a remote-sensing foundation model. We use pretrained GSE and Presto.
- We will not process raw imagery beyond what AI-1 and AI-2 require.
- We will not claim above 95% accuracy, and we will not reach it by loosening validation.
- We will not report per-class metrics for crops with fewer than five independent capture
  events. Mango has one. We will say so rather than print a number.
- We will not write back to survey records. KAVAL audits; the department decides.
- We will not build a mobile interface. Field officers act on the exported worklist.

---

## 13. Summary

Task 3 asks for a parcel-level crop classifier validated without leakage. We measured the
supplied data and found that its 14,643 ground-truth records are 3,204 observations, that
the photographic evidence sits a median 1.4 km from the parcels it documents, and that the
difference between a 90% system and a 71% system on this data is entirely the choice of
validation split.

We built the classifier the brief asks for, validated it the way the brief's own
anti-leakage clause demands, and report **81.7%** (best head, capture-event-grouped) rather than 95%. Then we used it to do
what the accuracy target was standing in for.

On the supplied study area it finds that only **18.3% of parcels** carry a
satellite–survey disagreement worth investigating at all, ranks those so the
better-evidenced cases come first, and clears **33.7% of parcels** as not needing a
visit next season — roughly 193 surveyor-days of a 572-day baseline.

Along the way it found things nobody was looking for: that the 14,643 ground-truth records
are 3,204 observations; that survey village codes and the supplied village polygons
disagree for one village pair, in a pattern that suggests a boundary or labelling error
FarmwiseAI can confirm; that satellite
delineation recovers farmed fields rather than legal parcels, at about two parcels per
field; and that four in five of those parcels need no attention at all.

Those are measurements, not projections. Every script that produced them is in the
repository, and where a number could not be honestly established — whether a cleared
parcel is genuinely correct, whether field-like patches inside reserve forest are
encroachment — we say so rather than estimating it.

The classifier is the instrument. The product is the audit.

---

*Authoritative plan: `KAVAL/plan.md`. Live status: `KAVAL/progress.md`.
Full validation report: `KAVAL/docs/VALIDATION_REPORT.md`.
Evidence artefacts: `KAVAL/docs/evidence/`. Every number above regenerates from
`KAVAL/scripts/`. Data requests to FarmwiseAI: `KAVAL/docs/DATA_REQUEST.md`.*

---

[^dcs]: Digital Crop Survey coverage figures, Department of Agriculture & Farmers
Welfare / AgriStack, Rabi 2024-25. See agristack.gov.in and DA&FW published statements.

[^ftw]: Kerner et al., *Fields of The World: A Machine Learning Benchmark Dataset for
Global Agricultural Field Boundary Segmentation*, AAAI 2025. arXiv:2409.16252.
