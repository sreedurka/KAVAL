# 14 · Review Preparation

**Audience:** everyone. Work through this the night before.

---

## The 60-second answer

If you get one question and one minute:

> "The brief asked for a crop classifier at 95% accuracy. We measured the data first and
> found that the 14,643 ground-truth records are really 3,204 observations — one
> photograph labels up to 43 parcels. Once you validate without that leak, the honest
> accuracy is **81.7%** (our best head, capture-event-grouped), not 95%. So we built what the accuracy target was standing
> in for: a system that tells a department which survey records to trust, which to
> re-verify, and which parcels never need visiting again. It turns out only **18.3%** of
> parcels need a human at all — and knowing *which* 18% is worth more than another
> point of accuracy."

## Numbers to have memorised

| | |
|---|---|
| Records → observations | 14,643 → **3,204** (4.57×) |
| Max parcels per photograph | **43** |
| Photo-to-parcel distance | median **1,436 m**, 62.3% over 1 km |
| The ladder | 89.7% → 89.5% → **81.2%** → 70.8% |
| Headline | **81.7% / 0.564** (MLP, 3-event) |
| Calibration | ECE 0.125 → **0.005** |
| Base disagreement rate | **18.3%** |
| Auto-clear | 4,825 parcels (33.7%), 193 surveyor-days |
| Fields delineated | 64,708 raw; **7,151 ha inside the 21 villages vs registry 12,097 ha (41% short)** |
| Legal parcels per physical field | **1.94**, max 19 |
| MIL attention gap | **+16.2 pp** (independent baseline) |
| GSE vs Presto | macro F1 **0.563 vs 0.452** (MLP, 3-event); combined 0.559, no measurable gain |
| Survey-month Sentinel-2 cover | **38.1%** of parcel-months in 2024-11, against 92.2% over the year |

**Careful with two of these.** The ladder holds **LightGBM** fixed so the split is the only
variable — its capture-event row is 81.2%. The **headline 81.7%** is the best
head, MLP. They measure different things; do not use them interchangeably.

---

## Questions you will get

### On the core argument

**"Why can't you hit 95%?"**
> Not without leaking. One photograph labels up to 43 parcels, so under a random split
> near-identical parcels land on both sides and the model retrieves rather than
> generalises. The brief itself says leakage invalidates the result. With LightGBM held
> fixed, a random split reports 89.7%; capture-event grouping, 81.2%. Same model,
> same features.

**"Isn't 81.7% just a weak model?"**
> It is our best head (MLP) under a strict regime. The comparison that matters is not
> against 95%, it is what one fixed model reports as only the split changes: LightGBM
> gives 89.7% under a random split and 81.2% under capture-event grouping. The
> difference is the split, not the model. And macro F1 matters more
> here than accuracy, because 63% of parcels are rice: a model that always says "rice"
> scores 63% and is useless.

**"Couldn't you just get more data?"**
> More *records* would not help — they would mostly be more parcels per photograph. What
> is scarce is **independent observations**, and those are limited by how many places a
> surveyor actually stood. That is a property of how the survey is conducted, not of the
> dataset size.

**"How do you know capture-event grouping isn't too strict?"**
> It is the unit at which the label was actually observed. A photograph produced one
> judgement about one crop; attributing it to 43 parcels does not create 43 judgements.
> Village grouping is the stricter test and we report it too (70.8%), with the caveat
> that 21 villages across 5 folds gives ±9.5 pp fold variance — too noisy to quote
> precisely.

### On the product

**"Your routing ratio — is it real?"**
> Answer it before they push. We first published it as a 5.58× "lift". It is
> arithmetically real and analytically weak: it is capped at 1 ÷ base-disagreement-rate
> (5.47×) and reaches the cap whenever every routed parcel is a disagreement. At a
> 500-visit budget it reads 5.45×, because 498 of the 500 routed parcels are
> disagreements. Either way it measures coverage, not ranking quality, and we label it
> as pinned by construction. The number that does reflect ranking is that routed
> parcels carry mean calibrated confidence 0.734 against 0.652 across all
> disagreements. And the operationally useful figure was always the base rate itself:
> only 18.3% of parcels need looking at.

**"How do you know auto-clearing is safe?"**
> We don't, fully, and we say so. Accuracy within the cleared set is 100% by construction
> because cleared *means* the model agreed. The real risk is satellite and surveyor being
> wrong the same way, which is **unidentified** from this data — the calibrator was fitted
> against the very label the status conditions on. We offer 7.6% as a rough proxy
> and propose an independent field audit of a cleared sample as the way to settle it.

**"Isn't the registry comparison circular?"**
> Partly, and it is labelled that way in the API payload itself. Agrisnet publishes the
> aggregate of the *same* Digital Crop Survey we audit. So it audits the survey's own
> published numbers against satellite — useful, but not validation against a second
> independent survey. We compare crop *share* rather than hectares, because our parcel
> sample covers only part of each village.

**"Your registry says the boundary layer is wrong — isn't that circular?"**
> Yes, and we withdrew that argument (correction #22). The registry is compiled by the
> recorded village code, so it agrees with the recorded codes by construction; its pair
> figures (0.0183 by code, 0.1053 by polygon) cannot tell us which attribution is right, and
> across all villages the difference is small (0.0569 against 0.0655). What we actually
> claim is narrower. 1,930 records sit in a different village polygon than their code, 1,895
> of them in the Viswanathaperi 911/912 pair, and all 1,175 records coded 912 fall inside
> polygon 911 while polygon 912 contains none. That geometry suggests a boundary or labelling
> error in the supplied layer, but it does not prove it. It is a question for you — cadastral
> records or a field check would settle it — and it is the kind of mismatch nothing
> downstream of the survey flags today. (`p7_registry.json` → `attribution_test`; Rabi 2024,
> 3-event split regime.)

### On the technical choices

**"Why did MIL fail?"**
> As a classifier it lost: -3.00 points of accuracy. We report that. But its attention
> weights separate cleanly — parcels it attends to least agree with the surveyor
> 69.4% of the time against 85.6% for the rest, a **+16.2 point gap**
> measured against an independently trained model. So it earns its place as an audit
> signal while failing at the job we designed it for. The trust score consumes it through
> a gate that would have dropped it automatically had the separation been weak.

**"Why measure the attention gap against a different model?"**
> Because measuring it against MIL's own prediction is partly self-referential — attention
> is the mechanism that produced that prediction. That version reads +22.8 pp. The
> honest number is +16.2, and it is the one we gate on.

**"Why is your field delineation only matching 73%?"**
> Two different things are going on, and only one is a shortfall. Points that miss a field
> sit a median 15 m away — GPS error, one or two Sentinel-2 pixels, which we handle with a
> snap tolerance chosen from the measured offset distribution. The real finding is the
> other criterion: **satellite delineation recovers physical fields, not legal parcels**.
> 1.94 legal parcels share each physical field. Coconut matches 23.6% (2,627 points), Sugarcane 56.5% (432) —
> a model trained on annual cropland does not bound a tree crop.

**"Presto vs GSE — you were asked for that."**
> We ran it. Capture-event-grouped, MLP head, identical rows and folds, 14,310 parcels:
> GSE alone 81.5% / 0.563 macro F1, Presto alone 74.2% / 0.452. Paired fold by fold,
> Presto is behind by 0.111 macro F1 with an SD of 0.011, on all five folds — a real gap.
> GSE + Presto gives 81.3% / 0.559: −0.004, within fold noise, so combining adds nothing
> we can measure. (`p4_results.json` → `sources`, `source_comparisons`.)

**"Why is Presto so much worse — did you set it up wrong?"**
> Possibly in part, and we name how before you ask. We used the maintainers' own
> normalisation through a wrapper that loads the checkpoint with a strict state-dict match,
> fed 12 monthly steps as Presto was pretrained, and masked cloud-gapped months rather than
> inventing values. But four things differ from its pretraining, and each could cost it:
> we feed L2A surface reflectance where it was pretrained on L1C top-of-atmosphere; our
> temperature and rainfall are taluk-scale, constant across parcels within a month; each
> parcel gets one series, the mean over its pixels, where Presto was pretrained per pixel;
> and the encoder is frozen, not fine-tuned. Terrain came from the Copernicus DEM in place
> of SRTM. So we claim the comparison, not a ranking of the two models.
>
> There is also a structural reason that is not a set-up error. Sentinel-2 was observed for
> 92.2% of parcel-months over the year but only 38.1% in 2024-11, the survey month, because
> of north-east monsoon cloud (`p3b_presto.json`). Any optical time-series model is short
> of evidence exactly when the crop is surveyed; GSE's annual multi-sensor summary is less
> exposed. That is useful for FarmwiseAI on its own: for a monsoon-season survey, the
> annual embedding is the safer default.

### The uncomfortable ones

**"What did you get wrong?"**
> Open `13_CORRECTIONS.md`. Lead with the tautological lift. Twenty-three logged corrections.

**"Would this work outside Sivagiri?"**
> Untested, and the village-grouped regime is the closest proxy we have — 70.8% with
> ±9.5 pp fold variance. With 21 villages in one taluk and one 8-day survey window,
> we cannot make a claim about transfer, and we do not.

**"Is this really AI, or a classifier with a map?"**
> Six components, each load-bearing: a segmentation foundation model for geometry, two
> remote-sensing foundation models for features, an attention-MIL head for the bag
> structure, confident learning plus calibration for the audit signals, and an LLM agent
> planning over typed tools. Remove any one and something downstream stops working.

**"How much of this actually runs?"**
> All of it. The pipeline runs end to end on real acquired data; every figure in every
> document regenerates from a script in `scripts/` into `docs/evidence/`. The analyst's
> **tool layer** is verified — 6/6 brief queries, 12/12 tools. Its **planning is verified on
> Gemini's free tier**: the 6 brief + 3 product questions pass 9/9, and the 2 extended
> questions (parcel lookup, calibration) pass 2/2. It sometimes skips a secondary tool call
> or states a figure no tool returned (a mis-rounding, or a number it derived itself); the
> grounding check flags these, and that is why every answer shows its citations and tool
> calls. The scope is Gemini only: Claude's planning is not verified, and a small local
> model or the offline keyword planner is labelled as such on every answer.
> (`p7_analyst_verification.json` → `llm_planner`, which records per question which model in
> the fallback chain answered, the tools it chose, its time, and any figure not traceable
> to a tool result.)

**"Why Gemini and not Claude?"**
> The Anthropic account could not be funded, so we could not run Claude. The provider
> layer is model-agnostic: Claude is first in the chain whenever a key exists, then
> Gemini's free tier, Groq or OpenRouter, a keyless local Qwen2.5-7B, and finally the
> offline planner. Each model's planning is verified separately, and the evidence file
> records a result only for the model that produced it. Our Gemini result says nothing
> about Claude, and we do not claim it does. A useful side effect: the analyst runs with no
> LLM budget at all.

---

## Three traps

**Do not claim the reserve-forest result is encroachment.** 734.7 ha of protected land
reads as field-like. There is no ground truth inside those polygons; it is equally
consistent with delineation error or another boundary problem. It produces a ranked list of
places worth a visit. That *is* the thesis — say it that way.

**Do not say a parcel is "wrong".** The survey and the satellite *disagree*. Which is right
is what a field visit determines. This is not pedantry; the whole product rests on it.

**Do not quote a metric without its regime.** If you find yourself saying a bare accuracy
figure, stop and add the split. The API physically cannot serve one unlabelled; neither
should you.

---

## If the demo breaks

Open `docs/evidence/`. Every figure in the walkthrough exists as a generated artefact
independent of the running system. The argument does not depend on a live server.
