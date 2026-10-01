# 13 · What We Got Wrong

**Audience:** everyone. **Read this before any review.**

---

## Why this document exists

Our thesis is that validation honesty matters more than a headline number. A project
making that claim has to be willing to show its own errors, or the claim is just a
posture.

So here they are — twenty-three of them, including a metric that was a mathematical
tautology, an area bug that inflated a published figure by 3.88×, and a finding we
published and then retracted.

**Use this offensively, not defensively.** If a reviewer finds a flaw before you name it,
you look like you were hiding it. If you name it first, you look like someone who
understands their own system. The correct move when asked "what went wrong?" is to open
this file, not to reach for a success.

---

## The five you must know cold

These are the ones most likely to come up, and the ones that most reveal understanding. They are lettered A–E so they do not collide with the numbers in the full log below; each heading gives its log number. The last, E, was found while writing these very documents, which is the point of it.

### A. The routing "lift" was a tautology (#2)

**What we published:** routing a field-verification budget beats random visiting by
**5.58×**. We put it in the proposal as the *more defensible* number, because it was a
count rather than a probability sum.

**What was wrong:** it was **exactly 1 ÷ base-disagreement-rate**, identical to six decimal
places at every budget below the number of available disagreements. Of course it was —
routing always lands on a disagreement, and random lands on one at the base rate. It
measured **coverage, not ranking quality**. Any classifier can enumerate its own
disagreements.

**How we found it:** an adversarial audit noticed the number was suspiciously constant
across budgets. Verified by computing 1/0.183 by hand.

**What we report now:** `targeting_efficiency`, explicitly labelled as pinned by
construction, plus the metric that genuinely reflects ranking — routed parcels carry mean
calibrated confidence **0.734** against **0.652** across all disagreements. And the
number that was actually useful all along: **only 18.3% of parcels** need looking at.

**The lesson:** a metric that is constant across a parameter it should depend on is
algebra, not measurement.

**Follow-up note on the wording (not a separate numbered correction):** "identical at every
budget" was true of the routing rule that produced 5.58×. With routing by P(label wrong) ×
area, a few agreeing parcels can enter the routed set, so `targeting_efficiency` is a
**cap** at 1 ÷ base rate that the routing reaches or sits just under, not an identity. In
`docs/evidence/p6_audit.json` → `budget_curve` (3-event split regime, 5-fold) the base
disagreement rate is 0.183, so the cap is **5.47×**; at a budget of 100 or 250 parcels every
routed parcel is a disagreement and the efficiency equals the cap (5.47×); at 500 it is
**5.45×** (498 of 500 routed parcels are disagreements). Either way it measures coverage,
not ranking quality. The docs now say "capped at", not "equal to".

### B. Accuracy within the auto-cleared set was circular (#1)

**What we published:** "accuracy within the auto-cleared set: 100%".

**What was wrong:** `CONFIRMED` is *defined* as the model agreeing with the survey. Of
course accuracy within it is 100%. It is a tautology, not evidence.

**What we report now:** a residual-risk proxy (7.6%), explicitly **not a bound**. The
quantity that matters — how often satellite and surveyor are wrong in the *same* way — is
**unidentified** from this data, because the calibrator was fitted against the very label
the status conditions on. Only an independent field audit of a CONFIRMED sample settles it.

**The lesson:** if a metric conditions on the outcome it claims to measure, it measures
nothing.

### C. "GSE alone beats GSE + seasonal" — published, then retracted (#4)

**What we published:** that the 64-d foundation embedding alone outperformed the embedding
plus twelve hand-engineered seasonal features, framed as "the opposite of what we
expected".

**What was wrong:** it flipped sign across three runs.

| Run | GSE only | GSE + seasonal |
|---|---:|---:|
| First (broken folds) | 0.607 | 0.598 |
| Second (corrected folds) | 0.587 | 0.597 |
| Third (with `field_id`) | 0.563 | 0.564 |

Every gap is under a third of the fold-to-fold standard deviation. **There was never an
effect.** We had reported noise as a finding.

**What we report now:** that the comparison is underpowered and the twelve features make
no measurable difference — *and* that an earlier draft claimed the opposite. A comparison
that flips sign between runs is exactly what the Leakage Ladder exists to catch.

**The lesson:** always check an effect against fold variance before naming it.

**Follow-up — correction #20:** the retraction reached the prose but not the generator.
`scripts/p9_validation_report.py` hard-coded "adding seasonal features makes the model
slightly worse" as a finding, so every regeneration of `VALIDATION_REPORT.md` put the
retracted claim back. The source verdict is now computed from paired per-fold deltas
(`docs/evidence/p4_results.json` → `source_comparisons`; 3-event split regime, MLP, 5-fold):
GSE + seasonal against GSE only is **+0.0008** macro F1 (SD of Δ 0.0081, 2 of 5 folds
favouring), flagged `underpowered`. A retraction has to reach the script, not just the prose.

### D. The village-boundary finding reversed — and the reversal corrected (#8, #22)

**What we first concluded:** 1,930 records (13%) sit in a different village polygon than
their code claims, so the *survey* mis-recorded village codes.

**What reversed it:** we acquired the Tamil Nadu Agrisnet registry independently. Its crop
mix agrees with the village code the survey **recorded** (mean |Δ share| 0.0163) far better
than with the polygon each point falls **inside** (0.1053). The geometry clinches it: all
1,175 records coded 912 fall inside polygon 911, and polygon 912 contains none of them.

**What we concluded then (superseded by correction #22 below):** the error is most likely in the **supplied boundary layer**, not
the survey records. For a company whose business is cadastral data, that is more useful
than the original reading — and it is the kind of thing nothing downstream of the survey
currently detects.

**The lesson (as first written):** a second independent source can invert an
interpretation, not just confirm it. We had one plausible story and stopped; acquiring the
registry is what tested it.

#### Follow-up — correction #22: the reversal itself overreached

**What we published:** that the registry "sides with" the recorded village code (pair
mean |Δ share| 0.0163 against 0.1053), that it was "sourced independently", and so that two
independent sources pointed at the supplied boundary layer as the error.

**What was wrong:** the argument was circular. The Agrisnet registry is the Digital Crop
Survey's own published aggregate, compiled by the **recorded** village code, so it agrees
with the recorded codes by construction. Its agreement cannot show which attribution is
right. We had also quoted the pair gap as if it were the whole story; across all villages
the difference is small. An audit caught it; the conclusion text now lives in the evidence
itself.

**What we say now** (`docs/evidence/p7_registry.json` → `attribution_test`; Rabi 2024,
3-event split regime):

- Registry vs satellite, mean |Δ share|: **0.0183** by recorded code against **0.1053** by
  polygon for the Viswanathaperi pair; **0.0569** against **0.0655** across all villages. The
  pair figure moved from 0.0163 because crop area is now aggregated at field level. The gap
  is a two-village effect, not taluk-wide.
- The only independent evidence is geometric (`pair_geometry`): all 1,175 records coded 912
  fall inside polygon 911 and polygon 912 contains none; of the records coded 911, 398 fall
  inside 911 and 720 inside 912. That **suggests** a boundary or labelling error in the
  supplied layer. It does not prove it.
- It is therefore a data-quality **question for FarmwiseAI**, to be settled with cadastral
  records or a field check. The discrepancy is real and concentrated in the 911/912 pair; only
  the attribution of blame was overstated. Mismatches between survey records and boundary
  layers are inherent at national scale, and nothing downstream currently flags them —
  flagging them is the useful part.

**The lesson, corrected:** a second source is only a second source if it was produced
independently of the first. Acquired separately is not the same as compiled separately.

### E. "FTW is within 8% of the registry" compared two different footprints (#18)

**What we published, in five places:** that satellite delineation found 13,062 ha against
the Agrisnet registry's 12,097 ha, "within 8%, from an independent source", and that this
"says the delineation itself is sound". It was our main evidence that AI-1 worked.

**What was wrong:** FTW covers the **whole taluk**. The registry covers **only the 21
revenue villages**. Of FTW's 13,062 ha, only **7,151 ha** lies inside those villages;
736 ha is inside Reserve Forest and the rest is non-village land. The "8%" was a
coincidence between mismatched footprints.

**How we found it:** cross-checking every number in the new team documents against
evidence. Two documents quoted different FTW areas (13,062 and 12,247 ha) for the *same*
claim, which prompted us to ask what the comparison was actually against.

**What we report now:** like for like, FTW delineates 7,151 ha inside the villages against
12,097 ha, **41% short**, and 26% short of the annual-crop area alone. So it under-recovers
cropped land even where it should be strongest, and we cannot isolate why with this data.
`scripts/p2c_ftw_registry_area.py` reproduces it.

**The lesson, and it is the sharpest one in the set:** a comparison that flatters you needs
*more* scrutiny than one that does not. We had checked the calculation and never checked
that both sides described the same land. Agreement is not evidence unless the two numbers
measure the same thing.

---

## The full log

| # | What was wrong | What it would have cost |
|---|---|---|
| 1 | Accuracy within CONFIRMED was circular | A safety claim that proved nothing |
| 2 | Routing "lift" was 1÷base-rate | A headline product claim that was algebra |
| 3 | `p_label_wrong` asserted ~98% certainty from an 82%-accurate model on uncalibrated probabilities | Routing a budget on false confidence |
| 4 | "GSE beats GSE+seasonal" retracted | Reporting noise as a finding |
| 5 | Attention gap was ⅓ self-reference (+22.8 → **+16.2 pp** against an independent model) | Overstating our own novel signal |
| 6 | Regime 4 grouped by recorded village code, leaking 15 of 21 villages | An optimistic geographic-generalisation figure |
| 7 | "4 unlabelled villages" were Reserve Forest | A demo built on a misread of the data |
| 8 | Village-code discrepancy blamed on surveyors; reversed when the registry agreed with the recorded code (0.0163 vs 0.1053), pointing at the supplied boundary layer instead — a reversal that itself overreached (see #22; story D above) | Blaming the survey's field staff for what may be a boundary-layer or labelling issue |
| 9 | Shared-field area double-counted 3.88× — 2,250 ha published as 4,801 ha (`p2d_shared_field_area.json`). Apportioning fixed the total but split one field across several crops; the fix is now field-level aggregation (one crop per shared field, totals unchanged, `conflicted_area_ha` exposed; rule in `p7_registry.json` → `area_rule`) | A wrong number in a headline product output |
| 10 | `METRIC_CRS` was UTM 44N; the AOI is 43N | Every area inflated 0.218% |
| 11 | Two contradictory Leakage Ladders published simultaneously | A reviewer opening both and seeing us disagree with ourselves |
| 12 | Analyst would have crashed on 5 of 6 brief queries (`Query(...)` defaults unresolved outside HTTP) | A failed live demo |
| 13 | `GEOMETRY_TRUST` had no `ftw_shared` entry — 54% of parcels silently defaulting to 0.4 | Systematically depressed trust on half the data |
| 14 | Phase 6 not carrying Phase 2 geometry fields into `audit.parquet` | Fields the UI needed could never have arrived |
| 15 | `/geo/parcels` used `head(limit)` — file order is geographically clustered | A silently biased map |
| 16 | Bare `assert` for the central leakage check — stripped by `python -O` | The one guarantee the project rests on, removable by a flag |
| 17 | Two processes writing the same parquet concurrently | Silent data corruption |
| 18 | "FTW within 8% of the registry" compared whole-taluk area to a villages-only registry | Our main evidence that AI-1 worked was a footprint artefact; like for like it is 41% short |
| 19 | Sentinel-1 download failing on expired SAS tokens, read as "slow" | Two hours of monitoring a job that had already failed; Presto blocked until it was fixed |
| 20 | Correction #4 retracted in the docs but not in `p9_validation_report.py`, which hard-coded the GSE-vs-seasonal claim so every regeneration reinstated it; now computed from paired per-fold deltas (`p4_results.json` → `source_comparisons`: GSE + seasonal +0.0008 macro F1, underpowered; 3-event, MLP, 5-fold) | A retracted finding silently returning in the generated report |
| 21 | "All sources anonymous" held only on the first machine: the Copernicus DEM read needs anonymous S3 (`AWS_NO_SIGN_REQUEST=YES`), which that machine had set outside the repo; now set in the script | A reproducibility claim that failed on the second machine |
| 22 | Registry "confirmed" the boundary layer was wrong — circular, since the registry is compiled from the recorded codes (follow-up to #8; story D above) | Blaming FarmwiseAI's boundary layer on evidence that could not support it |
| 23 | Phase 4 results predated a `splits.py` edit by 108 seconds; fold agreement 23% | Numbers not reproducible from the committed code |

---

## What the pattern says

Read the list again and notice what kind of error dominates. Almost none are coding
mistakes. They are **measurement mistakes** — numbers that looked meaningful and were not:
a tautology, a circularity, noise mistaken for signal, a self-referential comparison, a
metric conditioning on its own outcome.

That is the actual difficulty in this problem domain, and it is why the project is built
the way it is: the protocol is enforced in code rather than by discipline, the evidence
regenerates from scripts rather than being hand-edited, and a metric cannot leave the API
without naming its split regime.

**If asked "what did you learn?"** — this. Not that satellites can classify crops. That
the hard part of applied machine learning on this kind of data is knowing whether your own
numbers mean anything.

---

## How to answer "what went wrong?"

> "Quite a lot, and we logged all of it. The one I'd single out is that we published a
> routing lift of 5.58× and later found it was exactly one over the base disagreement
> rate — a tautology. It measured coverage, not ranking quality. We replaced it with a
> metric that isn't pinned, and we kept the correction in the record because a project
> arguing for validation honesty doesn't get to hide its own."

Then offer the file.
