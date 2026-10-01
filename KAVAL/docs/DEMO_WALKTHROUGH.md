# KAVAL — Demo Walkthrough

A twelve-minute route through the system, in the order that makes the argument. Every
number below is live from the running API, not copied in — if a figure here disagrees with
the screen, the screen is right and this file is stale.

**Setup**

```bash
cd /home/user/FM_AI
.venv/bin/uvicorn KAVAL.api.main:app --port 8077     # API + analyst
cd KAVAL/frontend && npm install && npm run dev       # UI on :5173
```

---

## 0 · The frame (30 seconds)

> "Task 3 asks for a crop classifier at 95% accuracy. We measured the data first, and what
> we found changed what we think should be built. The classifier is the instrument. The
> product is the audit."

---

## 1 · Why the target cannot be met honestly (2 min)

Open the **Validation** tab. It leads with the Leakage Ladder, deliberately — it is the
credential, not an appendix.

| Regime | Accuracy | Macro F1 |
|---|---:|---:|
| Random row | 89.7% | 0.772 |
| Grouped by parcel | 89.5% | 0.769 |
| **Grouped by capture event + shared field** | **81.2%** | **0.528** |
| Grouped by village | 70.8% | 0.326 |

**Say:** one model, one feature set, identical hyper-parameters. Only the split changes,
and accuracy moves 18.9 points.

**Then point at row 2.** Grouping by parcel is the obvious control and the one the brief's
own wording suggests. It moves accuracy -0.2 points — nothing. A team that applies
it will believe it is protected and will not be.

**Why:** 14,643 ground-truth records trace back to only **3,204 capture events**. One
photograph supplies a crop label to up to **43** parcels, and **0** of those events
contain more than one crop. The label is attached to the event and copied.

Scroll to per-class metrics. Every row carries **capture events** beside record count.
Banana has 653 records and 64 observations.

---

## 2 · The evidence is not where you think it is (1 min)

Still in Validation, the forensics panel. The photograph documenting each parcel sits a
median **1,436 m** away — 62.3% of records are documented by a photo taken over a
kilometre from the land in question.

**Say:** that is not an accusation. It is a measurement, and it means the photo cannot
serve as per-parcel evidence. A system that assumes it can is wrong about what it holds.

---

## 3 · The map, and the decision it encodes (2 min)

Open the **Audit map**. It is coloured by **agreement status**, not crop class.

**Say:** a map coloured by crop looks like every other classification demo. This is an
audit, so it is coloured by what to *do*.

| Status | Parcels |
|---|---:|
| `CONFIRMED` — skip next season | 4,825 |
| `DISPUTED` — top of the worklist | 784 |
| `UNCERTAIN` — route by budget | 8,429 |
| `UNVERIFIABLE` — re-survey the **record** | 272 |

**Click a DISPUTED parcel.** The panel shows the declared crop, the satellite's
prediction, calibrated confidence, and the full provenance: which capture event, how many
parcels shared that one photograph, how far away it was taken, where the geometry came
from.

**Dwell on `UNVERIFIABLE`.** It says the problem is the *evidence*, not the field. Nothing
downstream of the Digital Crop Survey reports that today.

**Move the threshold sliders.** Map, worklist and savings all move together, because the
rule lives in one place on the server.

---

## 4 · Confidence you can route on (1 min)

Validation → calibration.

| | Raw | Calibrated |
|---|---:|---:|
| Expected Calibration Error | 0.1247 | **0.0046** |
| Mean confidence | 0.942 | 0.817 |
| Actual accuracy | 0.817 | — |

**Say:** raw confidence claims 94.2% and delivers 81.7% (capture-event-grouped). You cannot spend a
budget on a number that overstates itself by twelve points. After calibration mean
confidence lands on the accuracy itself.

---

## 5 · What it is worth (2 min)

Open the **Worklist** and drag the budget slider.

**The honest framing, and say it in this order:**

1. Only **18.3%** of parcels carry a satellite–survey disagreement at all. Four in
   five need no attention.
2. Routing puts essentially every visit on one of those, against 91 for random
   visiting at budget 500 — a 5.45× ratio. **Then immediately say it is pinned by
   construction**: it equals 1 ÷ 0.183 for any budget below the number of
   disagreements. It measures coverage, not ranking. Any classifier can enumerate its own
   disagreements.
3. The metric that *is* informative: routed parcels carry mean calibrated confidence
   **0.734** against **0.652** across all disagreements. The queue
   puts better-evidenced cases first.

Then **Auto-clear**: **4,825 parcels (33.7%)** need no visit next season —
**193 surveyor-days** of a 572-day baseline.

**Volunteer the weakness before anyone asks:** we do not claim accuracy *within* the
cleared set, because it is 100% by construction. The quantity that matters — how often
satellite and surveyor are wrong the same way — is unidentified from this data. We offer
7.6% as a proxy and say only a field audit can settle it.

---

## 6 · Three things it found that nobody asked for (2 min)

**a. Village codes and village polygons disagree, in one pair.** Village audit tab. 1,930
records (13%) sit in a different village polygon than their code claims, 1,895 of them in
the Viswanathaperi 911/912 pair. All 1,175 records coded 912 fall inside polygon 911, and
polygon 912 contains none of them. That suggests a boundary or labelling error in the
supplied layer, which FarmwiseAI can confirm from cadastral records. Say plainly that the
registry cannot settle it: it is compiled from the recorded codes, so it agrees with them by
construction. Across all villages the difference is small (`p7_registry.json` →
`attribution_test`).

**b. Satellite delineation recovers farmed fields, not legal parcels.** Fields of The
World over real Sentinel-2 produced 64,708 fields. **Up to 19 legal parcels can share one
physical field**, averaging 1.94. Sugarcane matches 56.5% (432 points), **Coconut 23.6%** (2,627), because a model
trained on annual cropland does not bound a tree crop.

**Say:** that is the answer to "can satellite replace cadastral survey?" It recovers the
farmed unit, not the ownership unit, and here they differ by about 2×.

**Volunteer this before anyone asks:** it also under-recovers total cropped area. Inside the
21 registry villages it delineates 7,151 ha against the registry's 12,097 ha, 41% short.
An earlier version of this walkthrough said "within 8%", which compared the whole-taluk
figure to a villages-only registry. We caught that and corrected it.

**c. Field-like land inside protected forest.** 734.7 ha (4.0%) of reserve forest is
delineated as field-like. **Do not call this encroachment.** There is no ground truth
inside those polygons; it is equally consistent with delineation error or another boundary
problem. It produces a ranked list of places worth a visit — which is the thesis.

---

## 7 · Ask it a question (1 min)

Open the **Analyst** panel.

> "Which villages differ most from the registry, and where should I send 200 surveyors?"

Every answer cites the parcels it used; the agent never computes a number itself, it calls
tools. Every metric carries its split regime, because the API cannot serve one without it.

Point at the chip on the answer. It names the model that wrote it ("LLM · gemini:…"), or
says "offline planner — not LLM" if no model is reachable.

**Volunteer the weakness:** planning is verified on Gemini's free tier — the 6 brief + 3
product questions pass 9/9, and the 2 extended questions (parcel lookup, calibration) pass
2/2 — but it sometimes skips a secondary tool call or states a figure no tool returned (a
mis-rounding, or a number it derived itself). Our grounding check flags these, and every
answer shows its tool calls. That is why the citations and the tool-calls drawer are on
screen: check it. A typical answer takes a few seconds. Claude's planning is **not verified**; the
Anthropic account could not be funded. The keyless local model works but is slow on a
laptop CPU. (`p7_analyst_verification.json` → `llm_planner`.)

---

## Closing (30 seconds)

> "We report **81.7%** (capture-event-grouped), not 95%. The honest number is lower and the product is better,
> because 18.3% of parcels is what actually needs a human — and knowing *which*
> 18% is worth more than another point of accuracy."

**If asked what you got wrong:** open `progress.md`. Twenty-three logged corrections,
including a tautological lift metric, a 3.88× area double-count, a retracted finding, and
a bug that would have crashed the analyst on five of six demo queries. For a project whose
thesis is validation honesty, that log is the point.

---

## Questions to expect

| Question | Answer |
|---|---|
| *Why not 95%?* | Reachable only by validating in a way the brief itself says invalidates the result. Show the ladder. |
| *Is 81.7% good?* | It is the honest number under capture-event grouping. Under a random split the same pipeline reports 89.7%. |
| *Why did MIL fail?* | It is a worse classifier (-3.00 pp) and we report that. Its attention weights work: +16.2 pp separation on survey agreement, measured against an independent model. |
| *Presto vs GSE?* | It ran. Regime 3-event, MLP head, identical 5 folds (`docs/evidence/p4_results.json` → `sources`, `source_comparisons`): Presto alone reaches 74.2% accuracy / 0.452 macro F1 against GSE's 81.5% / 0.563, and is behind GSE in all 5 folds on both metrics. GSE + Presto (81.3% / 0.559, Δ macro F1 -0.0040, 1 of 5 folds favouring) is underpowered: within fold noise, so no gain can be claimed. This is not a verdict on Presto as a model (`docs/evidence/p3b_presto.json`): we fed it L2A surface reflectance where it was pretrained on L1C; one parcel-mean series per parcel where it was pretrained per pixel; taluk-constant reanalysis meteorology that carries seasonality, not spatial signal; and a frozen encoder with no fine-tuning. November 2024 was only 38.1% Sentinel-2-observed. |
| *Would this scale beyond Sivagiri?* | Untested. The village-grouped regime (70.8% ± 9.5%) is the closest proxy, and with 21 villages it is too noisy to quote precisely. |
| *What do you need from us?* | `docs/DATA_REQUEST.md`: cadastral geometry for an IoU benchmark, cadastral or field confirmation of the 911/912 (Viswanathaperi) village boundary, and the survey photographs for the vision-language check. None blocks. |
