# 09 · Verification Economics

**Owner: M3 (Audit Logic & Backend) · Phase 6b**

**This is the most delicate document in the set.** It describes the layer where the
product's value is claimed, and where we published a number that was a tautology. Read it
until you can explain the mathematics, not just the conclusion.

---

## 1. What this layer is for

Everything upstream — the classifier, calibration, trust — exists to make **this** layer
trustworthy. The product decision is: *given a fixed number of field visits, which
parcels should a surveyor go to?* And its converse: *which parcels never need visiting
again?*

## 2. The routing objective

```
priority(parcel) = P(survey label is wrong) × area_weight
```

`area_weight` (clipped to 0.25–4×) reflects that a wrong label on a large parcel distorts
the crop-area statistic more. **Area steers the ranking but is deliberately excluded from
the count of corrections**, so it cannot inflate any figure we report.

## 3. The tautology we published

**This is the story to tell, and tell it before anyone asks.**

Our first version reported that routing beat random visiting by **5.58×**, and we put it in
the proposal as the *more defensible* number, because it was a count of parcels rather than
a sum of probabilities.

**It was constant.** Identical to six decimal places at budgets of 100, 250, 500 and 1,000.
A real measure of ranking quality does not do that.

### Why it was pinned — the mathematics

Let *d* be the base disagreement rate (the fraction of parcels where satellite and survey
disagree). Here d = 0.183.

- A **random** visit lands on a disagreement with probability *d*, so a random budget of N
  finds **N·d** disagreements.
- A **routed** visit ranks by `p_label_wrong`, which is exactly zero for 98.8% of agreeing
  parcels. So while N is below the number of available disagreements, the router *always*
  finds one. It finds **N**.
- The ratio is N ÷ N·d = **1/d**, for every N below the number of disagreements.

1 ÷ 0.183 = 5.47. That is the "lift". **It contains no information about ranking quality.** It says
only that a classifier can enumerate its own disagreements — which is true of every
classifier ever built.

### How it was caught

An adversarial audit noticed the number was suspiciously constant across budgets, then
verified it: computing 1/0.179 by hand reproduced it to six decimal places.

### What we report now

| Budget | % of parcels | Routed hits | Random expected | Targeting |
|---:|---:|---:|---:|---:|
| 100 | 0.7% | 100 | 18 | 5.47x |
| 250 | 1.75% | 250 | 46 | 5.47x |
| 500 | 3.49% | 498 | 91 | 5.45x |
| 1,000 | 6.99% | 972 | 183 | 5.31x |
| 2,000 | 13.98% | 1,882 | 366 | 5.15x |

**Labelled `targeting_efficiency`, and flagged in the payload as
`targeting_is_pinned_by_construction: true`.** It measures coverage, not ranking. Say that
the moment you show it.

## 4. The metric that *is* informative

Ranking quality is whether the queue puts better-evidenced disagreements first.

| | Mean calibrated confidence |
|---|---:|
| **Routed (budget 100)** | **0.758** |
| All disagreements | 0.652 |

Routed parcels are systematically better-evidenced than disagreements in general. This is
**not pinned**: it would equal the all-disagreements figure if the ranking were arbitrary.
It is the only number here that says anything about ranking, and it is the one to defend.

## 5. The number that was useful all along

**Only 18.3% of parcels** — 2,617 of 14,310 — carry a satellite–survey disagreement.

Four parcels in five need no attention. That is the operational value, and it never
depended on the ratio. It is a direct count, needs no probability model, and cannot be
inflated.

*Lesson:* the tautology was hiding a perfectly good result behind a flattering one.

## 6. Auto-clear, and the second circularity

`CONFIRMED` parcels — satellite and survey agree at high calibrated confidence on a
record we trust — need not be revisited.

**4,825 parcels (33.7%), 871 ha, 193 surveyor-days saved** of a 572-day baseline.

### The circularity

We originally reported *"accuracy within the auto-cleared set: 100%"*. **It is 100% by
construction.** `CONFIRMED` is *defined* as the model agreeing with the survey; of course
accuracy within it is perfect. It is a tautology, and we were presenting it as a safety
claim.

### What is actually unknown

Auto-clearing fails only where **satellite and surveyor are wrong in the same way**. That
quantity is **unidentified** from this data, for a subtle reason:

> The calibrator was fitted against the declared label. So `1 − calibrated confidence`
> estimates the probability of an event that `CONFIRMED` **already conditions on**. It
> estimates something you have already selected against.

We offer **7.6%** as a **rough proxy, explicitly not a bound.** Only an independent
field audit of a random sample of `CONFIRMED` parcels can settle it — designing that audit
is the work we would most want to do next.

**Wording discipline:** never say "bounds", "guarantees" or "accuracy within the cleared
set". "Rough proxy" and "unidentified" are the correct words.

## 7. The cost assumption

The saving rests on **25 parcels per surveyor per day**, inferred from 14,310 parcels across an
8-day survey window in 21 villages. **It is an assumption**, stated wherever the saving
appears, and FarmwiseAI's actual productivity figure should replace it. A department will
check it, so do not present the 193 days as anything firmer.

## 8. The registry comparison

`scripts/p7_registry_comparison.py` compares the satellite crop mix against the Tamil Nadu
Agrisnet village-wise report for Rabi 2024.

**Compared as crop *share*, not hectares.** Our parcels cover only a fraction of each
village — the supplied points are a sample — so an absolute comparison would measure
sampling coverage, not agreement. Both sides are also renormalised over the same five
evaluable crops, so we do not manufacture a deficit by comparing our five to their
everything.

**It is not independent.** Agrisnet publishes the aggregate of the same Digital Crop Survey
whose sample we audit. It audits the survey's *published numbers* against satellite —
useful, but not a second survey. That caveat travels **in the API payload**, so neither the
UI nor the analyst can overstate it.

### The attribution test, and why it cannot settle attribution

We compared the registry against satellite shares attributed two ways
(`p7_registry.json` → `attribution_test`; Rabi 2024, 3-event split regime):

| Attribution | Mean \|Δ share\| (Viswanathaperi pair) | Mean \|Δ share\| (all villages) |
|---|---:|---:|
| By the village code the survey **recorded** | **0.0183** | 0.0569 |
| By the polygon each point falls **inside** | 0.1053 | 0.0655 |

The pair figure moved from 0.0163 to 0.0183 when crop area became field-level aggregated.

We once read this table as the registry "siding with" the recorded code, and so blaming the
boundary layer. **That was circular** (correction #22). The registry is compiled by the
recorded village code, so it agrees with the recorded codes by construction; the table
cannot show which attribution is right. The all-village columns also show the gap is a
two-village effect, not taluk-wide.

The only independent evidence is geometric (`attribution_test.pair_geometry`): all 1,175
records coded 912 fall inside polygon 911, and polygon 912 contains none of them. That
suggests a boundary or labelling error in the supplied layer, but it is a question for
FarmwiseAI to confirm with cadastral records or a field check, not a finding.

---

## Questions you must be able to answer

**"So is the 5.58× real or not?"**
> Arithmetically real, analytically empty. It equals 1 divided by the base disagreement
> rate for any budget below the number of disagreements, so it measures coverage, not
> ranking quality. We caught it ourselves, replaced it with `targeting_efficiency` flagged
> as pinned, and added a metric that isn't — routed parcels carry mean calibrated
> confidence 0.758 against 0.652 across all disagreements. The number that mattered was
> always that only 18.3% of parcels need looking at.

**"How do you know auto-clearing is safe?"**
> We do not, fully, and we say so. Accuracy within the cleared set is 100% by construction.
> The real risk — satellite and surveyor wrong together — is unidentified, because the
> calibrator was fitted against the very label the status conditions on. 7.6% is a rough
> proxy, not a bound. An independent field audit of a cleared sample is what would settle
> it, and we would run that first.

**"Isn't your registry comparison circular?"**
> Partly, and it is labelled that way in the API response itself. Agrisnet publishes the
> aggregate of the same survey we audit. It audits the survey's published numbers, which is
> useful, but it is not a second independent source. We also compare crop share rather than
> hectares because our sample covers only part of each village.

**"Where does 25 parcels per day come from?"**
> It is an assumption, inferred from the survey's own throughput, and stated wherever the
> saving is quoted. We would replace it with FarmwiseAI's real figure immediately; the
> saving scales linearly with it.

**"Why is DISPUTED bigger relative to CONFIRMED than you'd expect?"**
> Deliberate asymmetry. CONFIRMED requires high trust; DISPUTED does not. We are
> conservative about clearing and liberal about flagging, because wrongly clearing puts a
> bad record into a statistic that settles insurance, while wrongly flagging costs one
> visit.
