# 06 · The Leakage Protocol

**Owner: M2 (ML & Validation) · Phase 4**

**This is the project's central contribution.** Everyone should be able to explain the
ladder; M2 must be able to defend every row of it against someone who does this for a
living.

---

## 1. The problem: spatial autocorrelation

Nearby things are similar. Two adjacent parcels have nearly identical satellite
signatures, similar soil, the same weather, often the same crop.

If one is in the training set and its neighbour in the test set, a model can **retrieve**
rather than **generalise** — it recognises "I have seen something almost exactly like
this" and returns the answer. The reported accuracy measures memorisation, not skill.

Standard ML practice is shuffle-and-split. **On spatial data that is simply wrong**, and
the brief itself says so: *"spatial or parcel leakage between training and evaluation data
will invalidate the claimed result."*

## 2. This dataset's specific pathology

Phase 0 found something worse than ordinary spatial autocorrelation.

**14,643 ground-truth records trace back to 3,204 capture events** — 4.57× inflation.
One photograph supplies a crop label to up to **43** parcels. Within a capture event the
crop, stage, village, timestamp and photo coordinates are **identical in all 3,204 groups
without exception**, and **0** events contain more than one crop label.

The label is attached to the **event** and copied to its members. The parcels sharing a
label sit a median 117 m apart, so their embeddings are near-duplicates.

**Under a random split, those near-duplicates land on both sides of the fold.**

## 3. The four regimes

`kaval/splits.py` is the only place a split is created. `make_splits()` **raises** on an
unknown regime name rather than silently defaulting to random — which is precisely the
failure mode this module exists to prevent.

| # | Regime | Group key | Purpose |
|---|---|---|---|
| 1 | Random row | none | **Diagnostic only.** Never a headline. Reported to expose the gap. |
| 2 | Parcel | `parcel_id` | The obvious control. See §5. |
| 3 | **Capture event + field** | `bag_id` ∪ `field_id` | **The headline regime.** |
| 4 | Village (spatial) | `village_spatial` | Geographic generalisation. |

## 4. The ladder

LightGBM held fixed across all four rows. Same features, same hyper-parameters. **Only the
split changes.**

| Regime | Accuracy | Macro F1 | Log loss |
|---|---:|---:|---:|
| 1-random | 89.7% ± 0.004 | 0.772 | 0.343 |
| 2-parcel | 89.5% ± 0.005 | 0.769 | 0.343 |
| **3-event + field** | **81.2%** ± 0.022 | **0.528** | 0.823 |
| 4-village | 70.8% ± 0.095 | 0.326 | 1.459 |

**Accuracy falls 18.9 points and macro F1 falls 0.446, with no change to the model
whatsoever.**

*Careful:* the ladder's row 3 is **LightGBM** (81.2%), because the model is held fixed
to isolate the split. The **headline 81.7%** is the best head (MLP, §7). Do not
use them interchangeably.

## 5. Row 2 is the row that makes the argument land

Grouping by parcel is the **obvious** leakage control, and it is what the brief's own
phrase *"parcel leakage"* naturally suggests.

**It moves accuracy by -0.2 points. Nothing.**

Why: **parcels are already one-to-one with rows.** The grouping has almost nothing to
group. A team that applies the obvious control will believe it is protected and will not
be — and will report ~90% in good faith.

Only grouping by **capture event** — the unit at which the label was actually observed —
exposes the drop.

*This is the single most quotable result in the project. Lead with it.*

## 6. The composite group key

Phase 2 created a second leakage channel. Once satellite delineation assigns several legal
parcels to one physical field, those parcels carry **identical zonal features** — the same
problem as a shared capture event, from a different cause.

So the headline regime groups by **both**, merged with **union-find**:

```
A shares a bag with B.  B shares a field with C.
→ A, B and C are transitively linked and must travel together.
```

Grouping by each key separately would not be enough — transitivity is the whole point, and
`composite_group()` in `kaval/splits.py` is what enforces it.

**Measured cost:** 2,921 capture-event bags collapse into **2,269 components** (`docs/evidence/p4_results.json` → `group_structure`) — a 22% loss
of independent groups, one chain spanning 164 parcels — and about **0.8 of a point** of
accuracy that nobody would otherwise have subtracted. Fold SD nearly quadrupled
(±0.006 grouped by capture event alone, a labelled diagnostic, → ±0.022 with the field union; both in `group_structure`), because the grouping leaves fewer, larger, more variable groups.

## 7. Heads and sources, on identical folds (regime 3-event)

| Head | Accuracy | Macro F1 | Log loss |
|---|---:|---:|---:|
| MLP | 81.7% ± 0.012 | 0.564 | 1.048 |
| LogisticRegression | 80.6% ± 0.025 | 0.537 | 0.655 |
| LightGBM | 81.2% ± 0.022 | 0.528 | 0.823 |
| RandomForest | 79.1% ± 0.021 | 0.469 | 0.658 |

**MLP wins.** On dense unit-length embeddings a small neural head beats gradient
boosting — consistent with GSE being a *learned continuous space* rather than a set of
independent tabular columns, which is the structure trees exploit.

| Feature source | Features | Accuracy | Macro F1 |
|---|---:|---:|---:|
| GSE only | 64 | 81.5% | 0.563 |
| GSE + seasonal | 76 | 81.7% | 0.564 |
| Seasonal only | 12 | 73.7% | 0.399 |

## 8. The retraction — be ready to discuss this

We published a finding and withdrew it.

**What we claimed:** GSE alone beats GSE + seasonal, framed as "the opposite of what we
expected".

**What happened across three runs:**

| Run | GSE only | GSE + seasonal |
|---|---:|---:|
| First (broken folds) | 0.607 | 0.598 |
| Second (corrected folds) | 0.587 | 0.597 |
| Third (with `field_id`) | 0.563 | 0.564 |

**The sign flipped twice, and every gap is under a third of the fold standard deviation
(0.035).** There was never an effect. We had reported noise as a finding.

What we say now: the comparison is **underpowered**, the twelve engineered features make
no measurable difference, and seasonal features *alone* are clearly worse — so the
foundation embedding is doing the work.

**Why we published the retraction rather than quietly dropping it:** a comparison that
flips sign between runs is exactly what the ladder exists to catch. Showing that our own
protocol caught our own error is stronger evidence for the protocol than the original
claim ever was.

## 9. Enforcement — why this is code, not discipline

| Guarantee | Mechanism |
|---|---|
| A split cannot be made by an unknown regime | `make_splits()` raises on an unrecognised name |
| No group overlaps train and test | Explicit check that **raises**, not `assert` — a bare assert is stripped by `python -O`, and this is the one guarantee the project rests on |
| A metric cannot be served without its regime | `metric_response()` in `api/main.py` raises if `split_regime` is absent |
| Tuning cannot touch the held-out fold | Hyper-parameters fixed in `config.LGBM_PARAMS`; the fold is scored once |
| A class with too few observations cannot be reported | Collapsed to `Other` in Phase 3 |

An auditor tried to break the overlap check with a deliberately leaky splitter. It fired.
Then it tried under `python -O`, and the original `assert` vanished — which is why it now
raises.

## 10. The village regime is too noisy to quote precisely

21 villages across 5 folds gives a fold standard deviation of **±9.5 points**.

We originally grouped it by the *recorded* village code and measured 69.1%; correcting it
to the village each parcel physically falls in gives 70.8%. That is **0.18 standard
deviations** apart. The correction was right on principle — the recorded code leaked 15 of
21 villages — but its measured effect is indistinguishable from noise.

So we quote it as "roughly 71%, ±10" and treat capture-event grouping as the
headline, because it is the only regime with enough groups to be stable.

---

## Questions you must be able to answer

**"Isn't 81.7% just a bad model?"**
> The comparison that matters is not against 95%, it is against what the *same pipeline*
> reports under a looser split — 89.7%. Identical model, identical features. The
> difference is the split. And accuracy is the wrong lens here anyway: 63% of parcels are
> rice, so a model that always says "rice" scores 63%. Macro F1 is what separates a real
> model from that.

**"Why not just get more data?"**
> More *records* would not help — they would mostly be more parcels per photograph. What is
> scarce is **independent observations**, and those are limited by how many places a
> surveyor actually stood. That is a property of how the survey is conducted, not of
> dataset size. It is also exactly why the effective-n habit matters.

**"How do you know capture-event grouping isn't too strict?"**
> It is the unit at which the label was observed. One photograph produced one judgement
> about one crop; attributing it to 43 parcels does not create 43 judgements. If anything
> the stricter test is village grouping, and we report that too. We are not choosing the
> harshest regime for effect — we are choosing the one that matches how the data was made.

**"Couldn't the drop just be because grouped splits have fewer training samples?"**
> Group sizes are comparable across regimes — 5-fold in every case, so ~80% of data trains
> each time. What changes is *which* rows are held out, not how many. And row 2 is the
> control for exactly this: parcel grouping also constrains the split and changes nothing.

**"What would convince you the protocol is wrong?"**
> If capture-event-grouped and random splits agreed on this data, the premise would be
> wrong. They differ by 8.5 points. Separately, if a held-out *second taluk* scored
> near the capture-event number, that would show our regime is well-calibrated to real
> transfer — and it is the test we would most want to run with more data.
