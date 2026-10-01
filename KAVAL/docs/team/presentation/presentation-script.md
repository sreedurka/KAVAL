# KAVAL: The 15-Minute Talk

**Audience:** FarmwiseAI reviewers who have not seen KAVAL before.
**Speakers:** M1 Data & Geospatial · M2 ML & Validation · M3 Audit & Backend · M4 Product &
Frontend. *(Placeholders. Swap in names when the team list is final.)*

This is a spoken script. The "Say" blocks are the words to use. Keep the sentences short and
say the numbers slowly. Every number below is taken from a file in `KAVAL/docs/evidence/`,
and every accuracy or F1 names its validation split regime. If you ad-lib, keep to the same
three rules:

1. **Name the split regime** whenever you say an accuracy or F1. Write the headline in full
   at least once: *81.7% accuracy, 0.564 macro F1, MLP head, capture-event grouped with
   shared fields joined in (regime `3-event`), 5-fold.*
2. **Never say a parcel is "wrong".** The survey and the satellite *disagree*, and a field
   visit decides which one is right.
3. **Never claim more than 95%.** We do not get close, and we explain why that is the point.

---

## Running order

| # | Section | Clock | Length | Speaker |
|---|---|---|---:|---|
| 0 | Opening hook | 0:00–0:30 | 0:30 | M4 |
| 1 | The brief and the task | 0:30–1:15 | 0:45 | M4 |
| 2 | What we found before modelling | 1:15–3:15 | 2:00 | M1 |
| 3 | The reframing | 3:15–4:00 | 0:45 | M4 |
| 4 | The six AI components | 4:00–7:15 | 3:15 | M1, M2, M3 |
| 5 | The Leakage Ladder and the honest headline | 7:15–9:00 | 1:45 | M2 |
| 6 | Agreement status and what the product produces | 9:00–11:15 | 2:15 | M3, then M4 (live) |
| 7 | What we got wrong and corrected | 11:15–12:45 | 1:30 | M2 |
| 8 | Results in one table | 12:45–13:30 | 0:45 | M2 |
| 9 | Limitations and what we need from FarmwiseAI | 13:30–14:30 | 1:00 | M1 |
| 10 | Close | 14:30–15:00 | 0:30 | M4 |
| | **Total** | | **15:00** | |

**Before you start.** Have the app running (API on port 8077, UI on 5173) and keep
`docs/evidence/` open in a second window. If the demo fails, every figure is also in the
evidence files. The argument does not depend on a live server.

---

## 0 · Opening hook (0:00–0:30) · M4

**Show:** Title slide. Large type: **"14,643 records. 3,204 observations."** Below it:
*KAVAL: an agentic satellite audit system for India's Digital Crop Survey.*

**Say:**

> The brief asked for a crop classifier above 95 percent accuracy.
> Before we trained anything, we measured the data.
> FarmwiseAI gave us 14,643 survey records.
> They come from 3,204 photographs.
> One photograph labels up to 43 parcels.
> That single measurement decided what we built.
> We are KAVAL. Kaval is Tamil for vigil, keeping watch.

**If short on time, cut:** the line about the Tamil meaning.

---

## 1 · The brief and the task (0:30–1:15) · M4

**Show:** The Task 3 requirements as a short list, with the leakage clause highlighted.
Then the **Audit map** tab, zoomed out to Sivagiri taluk.

**Say:**

> We chose Task 3, satellite-embedding-based crop classification.
> The study area is Sivagiri taluk, in Tenkasi district, Tamil Nadu.
> FarmwiseAI supplied ground-truth points from the Digital Crop Survey, and 25 village
> polygons.
> The brief asks for a crop and a confidence for every parcel.
> It asks for crop-wise area, a comparison of embedding sources, and a validation report.
> It sets a target above 95 percent.
> And it adds one clause we took very seriously:
> leakage between training and evaluation data invalidates the result.
> Why does this survey matter? Its numbers drive crop insurance, procurement and
> compensation.
> A crop label on a parcel is not just a metric. It is a payment.

**If short on time, cut:** the list of deliverables. Keep the leakage clause and the
"it is a payment" line.

---

## 2 · What we found in the data before modelling (1:15–3:15) · M1

**Show:** **Leakage Ladder** tab, scrolled to the forensics panel ("What the supplied survey
records actually contain"). Then the "Effective n per crop" table.

**Say:**

> Before modelling anything, we audited the ground truth. Three findings.
>
> First. The 14,643 records come from 3,204 capture events.
> A capture event is one surveyor, one photograph, one moment.
> One event supplies up to 43 parcel labels.
> 93.8 percent of records sit in an event that covers more than one parcel.
> And not one of the 3,204 events carries more than one crop.
> So the label belongs to the photograph. It is copied to every parcel in it.
>
> Second. That changes the real sample size.
> Maize has 1,568 records, from 162 capture events.
> Marigold has 36 records, from 3 events.
> Mango has 6 records, from 1 photograph.
> The honest sample is the number of places a surveyor actually stood.
>
> Third. We measured how far each photograph is from the parcel it documents.
> The median is 1,436 metres. 62.3 percent are more than a kilometre away.
> So the photograph cannot serve as evidence for an individual parcel.
>
> We found smaller things too. 647 records store two coordinates in one cell.
> One column stores dates month-first, another day-first, in the same row.
> 385 records declare more than one crop.
> And no parcel boundaries were supplied. We were given points, not polygons.
>
> Here is why this changes everything.
> If parcels from one photograph land on both sides of a train–test split,
> the model does not learn crops. It recognises the photograph.
> Hold one model fixed. Split randomly, and it scores 89.7 percent.
> Group by capture event, and the same model scores 81.2.
> We will come back to that.
>
> None of this is a criticism of the survey.
> It is a national programme, and at that scale artefacts like these are inevitable.
> What is missing is anything downstream that measures them.

**Numbers on this slide:** `gt_forensics.json` (records, events, 43, 93.8%, 0 mixed events,
per-crop effective n, 1,436 m, 62.3%, 647, 385); `p1_repair.json` (date-format defect);
`p4_results.json` → `ladder` (89.7% random, 81.2% `3-event`, LightGBM, 5-fold).

**If short on time, cut:** the "smaller things" paragraph.

---

## 3 · The reframing (3:15–4:00) · M4

**Show:** One line on a plain slide: **"The classifier is the instrument. The product is
the audit."** Then switch to the **Audit map**, coloured by agreement status.

**Say:**

> So we changed the question.
> A 95 percent classifier was a stand-in for something else.
> A department does not need an accuracy figure.
> It needs to know which survey records to trust, which to re-check,
> and which parcels never need a visit again.
> That is an audit.
> So: the classifier is the instrument. The product is the audit.
> Every parcel gets an agreement status, not just a crop.
> Where satellite and survey disagree, we do not say either one is wrong.
> We say they disagree, and a field visit decides.
> The disagreement is the product.

**If short on time, cut:** nothing. This is the thesis. At most, drop to the two lines
"The classifier is the instrument. The product is the audit."

---

## 4 · The six AI components (4:00–7:15)

**Show:** An architecture slide with six boxes in pipeline order: geometry → features →
learning → audit → surface. Highlight each box as its speaker talks.

### AI-1 · Field delineation (4:00–4:40) · M1

**Say:**

> AI-1 creates the parcels. We were given points, and "parcel-level" means nothing without
> shapes.
> We ran the pretrained Fields of The World U-Net, an EfficientNet-B7, on two Sentinel-2
> scenes from May and December 2024.
> It produced 64,708 field polygons.
> What it found matters: satellites see physical fields, not legal parcels.
> On average 1.94 survey parcels share one field, and one field holds 19.
> It failed our own gate: 73.3 percent of points matched a field, and we required 80.
> So we kept a fallback geometry, and we say so.
> Inside the 21 villages it finds 7,151 hectares. The registry says 12,097.
> That is 41 percent short.

*(Sources: `p2_ftw_delineation.json`, `p2a_ftw_inference.json`, `p2c_ftw_registry_area.json`.
1.94 = 10,707 matched points ÷ 5,528 fields hit, both in `p2_ftw_delineation.json` → `gate`.)*

### AI-2 · Two foundation-model embeddings (4:40–5:25) · M2

**Say:**

> AI-2 provides the features. The brief asks us to compare embedding sources, so we ran two
> foundation models.
> Google's Satellite Embedding, also called AlphaEarth, gives 64 numbers summarising each
> 10-metre pixel's year.
> Presto, from NASA Harvest, reads a monthly time series instead.
> Same parcels, same folds, capture-event grouped, MLP head.
> GSE: 81.5 percent accuracy, macro F1 0.563.
> Presto: 74.2 percent, macro F1 0.452. It is behind on all five folds.
> Combining the two adds nothing we can measure.
> We do not treat that as a verdict on Presto.
> We fed it corrected surface reflectance, but it was pretrained on top-of-atmosphere data.
> And in November, the survey month, cloud left only 38.1 percent of parcels visible to
> Sentinel-2.

*(Sources: `p4_results.json` → `sources`, `source_comparisons`; `p3b_presto.json`.)*

### AI-3 · Attention-MIL over capture events (5:25–6:05) · M2

**Say:**

> AI-3 makes the label defect part of the model.
> A capture event is a bag of parcels that share one label.
> That is exactly the setting multiple-instance learning was designed for.
> Our attention-MIL head learns which parcels in a bag actually support the label.
> As a classifier, it lost. On the same capture-event folds it is 3 points of accuracy below
> the per-parcel baseline. We report that.
> But the attention weights work.
> Parcels it attends to least agree with the survey 69.4 percent of the time.
> The rest agree 85.6 percent of the time.
> That is a 16.2-point gap, measured against an independent model.
> So it earns its place as an audit signal, not as a classifier.

*(Source: `p5_mil.json`, regime `3-event`, 5-fold.)*

### AI-4 · Calibration, confident learning, trust (6:05–6:40) · M3

**Say:**

> AI-4 makes confidence something you can act on.
> Raw model confidence averaged 94.2 percent. Actual accuracy was 81.7.
> You cannot spend a budget on a number that overstates itself by twelve points.
> Cross-fitted isotonic calibration cuts the expected calibration error from 0.125 to 0.005.
> Confident learning then estimates, for each record, the probability that the declared
> label needs correction. That estimate is discounted by the model's own accuracy.
> And the Record Trust Score grades the evidence behind each record:
> bag size, photo distance, attention support, stage plausibility, mixed crop, and geometry.

*(Source: `p6_audit.json` → `calibration`, `confident_learning`, `trust_weights_applied`;
regime `3-event`.)*

### AI-5 · The agentic analyst (6:40–7:00) · M3

**Say:**

> AI-5 is the analyst. A language model plans over twelve typed tools, including parcel queries,
> a single parcel's audit trail, crop area, registry comparison, calibration, routing and export.
> The model never calculates a number itself. It calls tools,
> and every answer cites its sources and its split regime.
> It answers all six of the brief's analysis requests.
> The provider chain starts with Claude when a key exists. Then it tries Gemini's free tier,
> a local Qwen model, and finally an offline planner.
> On Gemini, 9 out of 9 questions pass.

*(Source: `p7_analyst_verification.json` → `tools_available`, `brief_queries_passing`,
`llm_planner`.)*

### AI-6 · Photo verification, conditional (7:00–7:15) · M3

**Say:**

> AI-6 uses a vision-language model to check each survey photograph against the declared
> crop. It is conditional. We have the image paths, but not the images.
> The audit works without it, and it would get stronger with it.

**If short on time, cut (whole section 4):** drop the "what it found" detail from AI-1 and
the Presto caveats from AI-2. Do not drop AI-3's negative result. Saying it ourselves is the
point.

---

## 5 · The Leakage Ladder and the honest headline (7:15–9:00) · M2

**Show:** **Leakage Ladder** tab, the four-row table. Then scroll to per-class metrics, where
each row shows its capture-event count.

**Say:**

> If we could keep only one slide, it would be this one.
> Same model: LightGBM. Same 76 features. Same settings.
> Only the validation split changes.
>
> Random rows: 89.7 percent accuracy, macro F1 0.772.
> Grouped by parcel: 89.5. That obvious fix does nothing,
> because each parcel is already exactly one row.
> Grouped by capture event, with shared satellite fields joined in:
> 81.2 percent, macro F1 0.528.
> Grouped by village: 70.8, with a fold-to-fold spread of 9.5 points.
> Accuracy falls 18.9 points, and the model never changed.
>
> Our headline regime is capture-event grouping,
> because the photograph is the unit where a label was actually observed.
> We also join parcels that share a delineated field, using union-find,
> because they carry identical features.
> That costs a further 0.8 points. We accept that cost.
>
> Under that regime our best head, an MLP, scores 81.7 percent accuracy
> and 0.564 macro F1, over five folds. That is our headline.
> Please do not confuse it with the ladder's 81.2.
> The ladder holds LightGBM fixed. The headline is the best head.
>
> Why macro F1? Rice is 63 percent of parcels.
> A model that always says "rice" scores 63 percent and is useless.
> Macro F1 counts every crop equally.
> Banana, with only 64 independent capture events, pulls it down.
>
> We will not claim 95.
> On this data, you only reach it with a split that the brief itself says invalidates the
> result.

**Numbers:** `p4_results.json` → `ladder` (LightGBM, 5-fold), `group_structure` (diagnostic
bag-only 82.0% vs `3-event` 81.2%, the 0.8-point field-union cost), `heads` (MLP 81.7% /
0.564, `3-event`), per-class table (Banana 64 capture events, `3-event`, MLP). Rice share
= 8,970 of 14,310 evaluated parcels (`p4_results.json` → `classes`).

**If short on time, cut:** the macro F1 paragraph.

---

## 6 · Agreement status and what the product produces (9:00–11:15)

### Statuses (9:00–9:45) · M3

**Show:** **Audit map** with the status legend. Click one DISPUTED parcel to open the
parcel panel: declared crop, satellite crop, calibrated confidence, capture event, parcels
sharing the photograph, photo distance, geometry source.

**Say:**

> Here is what the audit produces. Every figure is under the headline regime.
> Five statuses.
> CONFIRMED: the satellite agrees, calibrated confidence is high, and the record is
> trustworthy. 4,825 parcels.
> DISPUTED: the satellite disagrees with high confidence. 784 parcels, at the top of the
> worklist.
> UNCERTAIN: the model cannot tell. 8,429.
> UNVERIFIABLE: the evidence is too weak to test. 272 records.
> For those, re-survey the record, not the field.
> UNSEEN: no survey record, satellite only. Zero in this sample.
> Overall, 18.3 percent of parcels carry a satellite–survey disagreement.
> About four in five need no attention at all.

### Live: worklist, auto-clear, village audit (9:45–11:15) · M4

**Show:** **Field worklist**, budget slider at 500. Then **Auto-clear**. Then **Village
audit**, sorted by share divergence. Finish by moving one slider on the thresholds rail.

**Say:**

> This is the field worklist. I set the budget to 500 visits.
> The router ranks parcels by the probability that the label needs correction,
> weighted by parcel area.
> It expects about 390 corrections. Random visits would expect about 54.
> Those are model estimates, not counts.
> To check the ranking itself: routed parcels have a mean calibrated confidence of 0.734,
> against 0.652 across all disagreements.
>
> Auto-clear. 4,825 parcels, 33.7 percent, need no visit next season.
> At an assumed 25 parcels per surveyor-day, that saves 193 surveyor-days
> out of a 572-day baseline.
> The assumption is shown on screen. FarmwiseAI's real figure would replace it.
>
> Village audit. We compare satellite crop shares with the TN Agrisnet registry,
> for all 21 villages.
> In Rayagiri Part 1, the registry says 58.2 percent sugarcane. The satellite says 23.7.
> That is a gap of 34.6 points.
> The registry is the survey's own published total,
> so this is a consistency check, not independent validation. The screen says so.
>
> Every threshold is here on the left rail.
> Move one, and the map, the worklist and the savings all update from the same rule on the
> server.

**Numbers:** `p6_audit.json` → `agreement_status_counts`, `budget_curve` (budget 500:
390.5 vs 53.9 estimated corrections, 0.734 vs 0.652), `auto_clear` (4,825, 33.7%, 193.0 of
572.4 surveyor-days, 25 parcels/day assumption); `p7_registry.json` → `largest_divergences`
(Rayagiri - Part-1, Sugarcane). All regime `3-event`.

**If short on time, cut:** the village audit demo. Replace it with one sentence: "We also
compare each village against the published registry, and label that comparison as not
independent."

---

## 7 · What we got wrong and corrected (11:15–12:45) · M2

**Show:** A five-row slide with three columns: *What we said · What was true · What we
report now.* Mention that the full log is `docs/team/13_CORRECTIONS.md`.

**Say:**

> We logged 23 corrections to our own work.
> Here are five, because each one is a mistake you could make too.
>
> One. We published a routing "lift" of 5.58 times.
> It was exactly one divided by the base disagreement rate.
> Any classifier can find its own disagreements.
> It measured coverage, not ranking. We now label it as capped by construction.
>
> Two. We reported 100 percent accuracy inside the auto-cleared set.
> But CONFIRMED is defined as the model agreeing. That made it a tautology.
> The real risk is satellite and surveyor making the same error,
> and that cannot be measured from this data.
> We give 7.6 percent as a rough proxy, not a bound, and we propose a field audit.
>
> Three. We said satellite delineation came within 8 percent of the registry.
> We had compared the whole taluk with just the 21 villages.
> Like for like, it is 41 percent short.
> The comparison that flattered us was the one we had not checked.
>
> Four. We said the registry proved the village boundary layer was in error.
> But the registry is compiled from the same recorded codes.
> The argument was circular, and we withdrew it.
>
> Five. We published that the embedding alone beat embedding plus seasonal features.
> The result flipped sign across three runs. It was noise.
> We retracted it, then found the report generator still printing it.
> A retraction has to reach the script, not just the prose.

*(Corrections #2, #1, #18, #22, #4 and #20 in `13_CORRECTIONS.md`. Current figures:
`p6_audit.json` → `budget_curve`, `auto_clear`; `p2c_ftw_registry_area.json`;
`p7_registry.json` → `attribution_test`; `p4_results.json` → `source_comparisons`.)*

**If short on time, cut:** keep One and Three only. They are the clearest.

---

## 8 · Results in one table (12:45–13:30) · M2

**Show:** This table, on one slide.

| Result | Value | Split regime / scope | Evidence |
|---|---|---|---|
| **Headline** | **81.7% accuracy, 0.564 macro F1** | MLP, `3-event` (capture event ∪ shared field), 5-fold | `p4_results.json` → `heads` |
| Ladder, random rows | 89.7% / 0.772 | LightGBM, `1-random`, 5-fold. Diagnostic only, never a claim | `p4_results.json` → `ladder` |
| Ladder, parcel-grouped | 89.5% / 0.769 | LightGBM, `2-parcel`, 5-fold | same |
| Ladder, capture-event | 81.2% / 0.528 | LightGBM, `3-event`, 5-fold | same |
| Ladder, village | 70.8% ± 9.5 pp / 0.326 | LightGBM, `4-village`, 5-fold. Too noisy to quote precisely | same |
| Cost of the field union | 82.0% → 81.2% (−0.8 pt) | LightGBM; bag-only diagnostic vs `3-event` | `p4_results.json` → `group_structure` |
| GSE vs Presto | 81.5% / 0.563 vs 74.2% / 0.452; GSE + Presto 81.3% / 0.559, underpowered | MLP, `3-event`, 5-fold, paired by fold | `p4_results.json` → `sources`, `source_comparisons` |
| Attention-MIL | 78.7% / 0.509; −3.00 pp vs per-parcel baseline | `3-event`, same folds | `p5_mil.json` |
| MIL attention signal | +16.2 pp agreement gap (69.4% vs 85.6%) | `3-event`, against an independent baseline | `p5_mil.json` → `attention_check` |
| Calibration | ECE 0.1247 → 0.0046 | `3-event` out-of-fold, cross-fitted isotonic | `p6_audit.json` → `calibration` |
| Base disagreement rate | 18.3% (2,617 of 14,310) | `3-event` | `p6_audit.json` → `budget_curve` |
| Agreement status | 4,825 / 784 / 8,429 / 272 / 0 | CONFIRMED / DISPUTED / UNCERTAIN / UNVERIFIABLE / UNSEEN; `3-event` | `p6_audit.json` |
| Auto-clear | 4,825 parcels (33.7%); 193.0 of 572.4 surveyor-days | `3-event`; assumes 25 parcels per surveyor-day | `p6_audit.json` → `auto_clear` |
| Field delineation | 73.3% matched at 20 m (gate 80%); 7,151 vs 12,097 ha (−40.9%) | Geometry, no train/test split | `p2_ftw_delineation.json`, `p2c_ftw_registry_area.json` |
| Analyst planning | 9/9 core and 2/2 extended questions pass on Gemini | Planning by that model only | `p7_analyst_verification.json` → `llm_planner` |

**Say:**

> Here is every number in one place, each with its regime.
> Headline: 81.7 percent, macro F1 0.564, MLP, capture-event grouped, five folds.
> The random-split 89.7 is shown for comparison. We do not claim it.
> Village-grouped is 70.8, too noisy to quote precisely.
> GSE beats Presto, 0.563 to 0.452 macro F1.
> Calibration error is 0.005. The disagreement rate is 18.3 percent.
> Every figure is regenerated by a script into our evidence folder.
> And our API will not serve a metric without its split regime.

**If short on time, cut:** leave the table up. Say only the first and last sentences.

---

## 9 · Limitations and what we need from FarmwiseAI (13:30–14:30) · M1

**Show:** Two columns. Left: *What we cannot claim.* Right: *What would make it stronger*
(from `docs/DATA_REQUEST.md`).

**Say:**

> What we cannot claim.
> This is one taluk and one eight-day survey window. Transfer to other regions is untested.
> Village grouping is our closest proxy, and it is noisy.
> Seven crops have fewer than five capture events each, so we make no per-class claim for
> them.
> Our geometry is derived from satellite, not cadastral.
> The saving depends on an assumed 25 parcels per surveyor-day.
> And we have verified the analyst's planning on Gemini only, not on Claude.
>
> What we would ask FarmwiseAI for.
> First, FMB cadastral geometry for Sivagiri. Then we can measure how well satellite
> delineation substitutes for survey geometry.
> Second, the survey photographs behind the image paths. That switches on AI-6.
> Third, a check of the Viswanathaperi 911 and 912 boundary.
> All 1,175 records coded 912 fall inside polygon 911.
> That suggests a boundary or labelling issue. It does not prove one.
> And, lower priority, your real surveyor productivity figure.
> None of these blocks the prototype.

**Numbers:** `p1_repair.json` (8-day window); `p3_feature_store.json` → `collapsed_to_other`
(seven crops); `p7_registry.json` → `attribution_test.pair_geometry` (1,175 coded 912, all
inside polygon 911); `p6_audit.json` → `visit_cost_assumption`.

**If short on time, cut:** reduce the limitations to "one taluk, one season, derived
geometry", and keep all three requests.

---

## 10 · Close (14:30–15:00) · M4

**Show:** Return to the title slide, with the line **"The classifier is the instrument. The
product is the audit."**

**Say:**

> We report 81.7 percent, capture-event grouped. Not 95.
> The honest number is lower, and the product is more useful because of it.
> Only 18.3 percent of parcels carry a disagreement.
> Knowing which ones is worth more than another point of accuracy.
> The classifier is the instrument. The product is the audit.
> Thank you.

**If short on time, cut:** nothing. This is thirty seconds.

---

## The 60-second version

Use this if the slot shrinks, or if one reviewer asks for "the short version".

> FarmwiseAI asked for a crop classifier above 95 percent. We measured the data first.
> The 14,643 survey records come from 3,204 photographs. One photograph labels up to 43
> parcels, and it sits a median 1,436 metres from the parcel it documents.
> Hold one model fixed: a random split scores 89.7 percent, and grouping by capture event
> scores 81.2.
> Our best head, an MLP, reaches 81.7 percent accuracy and 0.564 macro F1 under
> capture-event grouping, five folds. That is our honest number.
> So we built what the target was standing in for: an audit.
> Six AI components give every parcel an agreement status.
> Only 18.3 percent of parcels carry a satellite–survey disagreement. The router sends a
> limited budget there first. And 4,825 parcels, a third, can skip next season's visit,
> about 193 surveyor-days under our stated cost assumption.
> The classifier is the instrument. The product is the audit.

---

## The eight hardest reviewer questions

Answer in two or three sentences, then stop. Volunteer the weakness before they find it.

**1. "Why can't you hit 95%?"**
> Not without leakage. One photograph labels up to 43 parcels, so a random split puts
> near-identical parcels on both sides and the model recognises them instead of
> generalising. With LightGBM held fixed, a random split reports 89.7% and capture-event
> grouping reports 81.2%, with the same model and features. The brief itself says leakage
> invalidates the result. (`p4_results.json` → `ladder`, 5-fold.)

**2. "Isn't capture-event grouping, plus your field union, just too strict? And why 81.7
here but 81.2 on the ladder?"**
> The capture event is where the label was actually observed. One photograph is one
> judgement, even when it is copied to 43 parcels. We also join parcels that share a
> delineated field, because they carry identical features. That costs 0.8 points (82.0% to
> 81.2%, LightGBM, bag-only diagnostic against `3-event`) and widens fold SD from 0.006 to
> 0.022 (`p4_results.json` → `group_structure`). We pay that cost rather than report a leak.
> The ladder holds LightGBM fixed so that the split is the only thing that changes.
> 81.7% / 0.564 is the best head, MLP, under the same `3-event` regime.

**3. "How do you know auto-clearing is safe?"**
> We don't fully know, and we say so. Accuracy inside the cleared set is 100% by
> construction, because "cleared" means the model agreed, so we do not report it. The real
> risk is satellite and surveyor making the same error, and this data cannot identify that.
> We give 7.6% (about 365 parcels) as a rough proxy, not a bound. An independent field audit
> of a CONFIRMED sample is the way to settle it. (`p6_audit.json` → `auto_clear`, `3-event`.)

**4. "Your routing ratio: is it real?"**
> It is real arithmetic, and it tells you very little. It is capped at one over the base
> disagreement rate, 5.47×, and at 500 visits it reads 5.45× because 498 of 500 routed
> parcels are disagreements. It measures coverage, not ranking. That was correction #2: we
> first published it as a 5.58× "lift". The ranking check is mean calibrated confidence:
> 0.734 for routed parcels at budget 500, against 0.652 across all disagreements.
> (`p6_audit.json` → `budget_curve`, `3-event`.)

**5. "You say the boundary layer is wrong. Isn't the registry evidence circular?"**
> Yes, and we withdrew that argument (correction #22). The registry is compiled from the
> recorded village codes, so it agrees with them by construction. Across all villages the
> difference is small: mean |Δ share| 0.0569 by code against 0.0655 by polygon. What we do
> claim is geometric: all 1,175 records coded 912 fall inside polygon 911, and polygon 912
> contains none of them. That suggests a boundary or labelling issue but does not prove one.
> It is a question for you, and cadastral records would settle it.
> (`p7_registry.json` → `attribution_test`.)

**6. "Presto is far behind GSE. Did you set it up wrong?"**
> Possibly in part, and we list exactly how. Under the same rows and folds (MLP, `3-event`),
> Presto reaches 74.2% / 0.452 against GSE's 81.5% / 0.563, behind on all 5 folds. GSE +
> Presto is underpowered, within fold noise. Four things differ from Presto's pretraining:
> we used L2A input where it was trained on L1C, taluk-scale meteorology, one parcel-mean
> series rather than per-pixel series, and a frozen encoder. There is also a structural
> reason: only 38.1% of parcels were cloud-free to Sentinel-2 in November 2024, the survey
> month. So we claim the comparison, not a ranking of the two models.
> (`p4_results.json` → `source_comparisons`; `p3b_presto.json`.)

**7. "Is the analyst really an LLM agent? Why Gemini and not Claude?"**
> The tool layer passes all 6 brief queries and exercises all 12 tools. LLM planning is
> verified on Gemini's free tier: the 6 brief and 3 product questions pass 9 of 9, and the
> 2 extended questions, a parcel lookup and a calibration question, pass 2 of 2. The
> evidence records per question which model in the chain answered, the tools it chose and
> its time; those change from run to run, so we quote the stable result. The model
> sometimes skips a secondary tool call or states a figure no tool returned, a mis-rounding
> or a number it derived itself. The grounding check flags these, and that is why
> citations and tool calls appear on every answer. We could not fund an Anthropic key, so Claude's planning is not verified.
> Our Gemini result tells you nothing about Claude, and we do not claim it does.
> (`p7_analyst_verification.json` → `llm_planner`.)

**8. "MIL lost. Why is it still in the system?"**
> As a classifier it is 3.00 points of accuracy and 0.0565 macro F1 below the per-parcel
> baseline on the same `3-event` folds, and we report that. Its attention weights separate
> cleanly: low-support parcels agree with the survey 69.4% of the time against 85.6%, a
> 16.2-point gap measured against an independent model. Measured against MIL's own
> prediction the gap is 22.8, but that version is partly self-referential, so we do not use
> it. The trust score includes the signal only through a gate that would have removed it
> automatically if the separation had been weak. (`p5_mil.json`.)

**Also be ready for "Would this work outside Sivagiri?"**
> Untested. The village-grouped regime is our closest proxy: 70.8% ± 9.5 pp (LightGBM,
> `4-village`, 5-fold), from 21 villages in one taluk. We make no transfer claim.
