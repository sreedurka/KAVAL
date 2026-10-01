# 11 · Validation & Metrics

**Owner: M2 (ML & Validation) · Phase 9**

How we report results, and why the reporting conventions are themselves part of the
contribution.

---

## 1. Why accuracy alone is meaningless here

**63% of parcels are rice.** A model that ignores its input and always says "Rice (Paddy)"
scores 63% accuracy.

So accuracy answers almost nothing on this data. Every result carries **macro F1**
alongside it — the unweighted mean of per-class F1 — which is dragged down by any class
the model handles badly, regardless of how rare it is.

Notice the gap in our own ladder: accuracy falls 18.9 points from loosest to strictest
regime, but macro F1 falls **0.446** — proportionally far more. The leak was
disproportionately helping the minority classes, which is exactly where it does the most
damage.

## 2. What we always report together

| Metric | Why |
|---|---|
| Accuracy **and** macro F1 | Accuracy alone hides the minority classes |
| Per-class precision / recall / F1 | Where the model actually fails |
| **Effective n** (capture events) | See §3 — the habit that most distinguishes our reporting |
| Confusion matrix | The *shape* of the error, not just its size |
| ECE | Whether the confidence can be spent |
| Fold standard deviation | Whether a difference is a result at all |
| **The split regime** | Mandatory. A metric without it is incomplete. |

## 3. Effective n — the habit to demonstrate

Never print a per-class table with only a record count. Record counts are inflated ~4.57×
by capture-event label copying.

Regime `3-event`, MLP:

| Crop | Records | **Capture events** | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| Rice (Paddy) | 8,970 | **2102** | 0.865 | 0.916 | 0.890 |
| Coconut | 2,566 | **463** | 0.772 | 0.765 | 0.769 |
| Maize | 1,560 | **159** | 0.711 | 0.678 | 0.694 |
| Sugarcane | 429 | **117** | 0.781 | 0.667 | 0.719 |
| Banana | 653 | **64** | 0.440 | 0.254 | 0.322 |
| Other | 132 | **16** | 0.000 | 0.000 | 0.000 |

**Read the Banana row.** 653 records — which sounds like plenty — but **64 independent
observations**, and F1 0.322. The record count promises statistical power the data
does not have.

`Other` aggregates seven crops with between 1 and 4 capture events each. We make **no
per-class claim** for any of them. Mango has 6 records and **one** observation; an F1 for
it would be arithmetic, not measurement.

## 3b. When is a difference a result? The sources comparison

Two numbers side by side are not a comparison. We pair every source against GSE alone on
the **same folds and the same rows**, take the per-fold difference, and read its mean
against its own spread and against how many folds agree. The verdict is computed by
`scripts/p9_validation_report.py` from those deltas, never typed in (correction #20).

Regime `3-event`, MLP head, 14,310 parcels, 5-fold (`docs/evidence/p4_results.json` →
`sources`, `source_comparisons`):

| Source | Accuracy | Macro F1 | Mean Δ macro F1 | SD of Δ | Folds favouring | Verdict |
|---|---:|---:|---:|---:|---:|---|
| GSE only (64-d) | 81.5% | 0.563 | — | — | — | reference |
| GSE + seasonal (76) | 81.7% | 0.564 | +0.0008 | 0.008 | 2/5 | underpowered |
| Seasonal only (12) | 73.7% | 0.399 | −0.165 | 0.033 | 0/5 | worse |
| Presto (128-d) | 74.2% | 0.452 | −0.111 | 0.011 | 0/5 | worse |
| GSE + Presto (192) | 81.3% | 0.559 | −0.004 | 0.006 | 1/5 | underpowered |

**Two readings to be able to give.** Presto alone is a real gap: the mean difference is
ten times its spread and all five folds agree. Adding seasonal features or Presto to GSE is
not a result either way — the difference is inside fold noise and the folds split. "No
measurable gain" is the sentence; "slightly worse" is not. The Presto gap is a statement
about Presto as we fed it (L2A not L1C, taluk-scale meteorology, parcel-mean series, frozen
encoder), not about the model; doc 05 §3 has the caveats.

## 4. The error pattern

| Confusion | Parcels |
|---|---:|
| Coconut → Rice (Paddy) | 457 |
| Maize → Rice (Paddy) | 388 |
| Rice (Paddy) → Maize | 320 |
| Rice (Paddy) → Coconut | 280 |
| Banana → Rice (Paddy) | 270 |

**Everything collapses toward Rice.** That is the signature of class imbalance under a
strict split: when the model is uncertain, the prior wins.

It is also operationally informative. A department reading our output should know that
non-rice crops are *under*-called, so the parcels most worth visiting are the ones we call
rice with middling confidence — which is one reason the worklist ranks by calibrated
confidence rather than by raw class.

## 5. Calibration

| | Raw | Calibrated |
|---|---:|---:|
| ECE | 0.1247 | **0.0046** |
| Mean confidence | 0.942 | 0.817 |
| Actual accuracy | 0.817 | 0.817 |

Raw confidence claims 94.2% and delivers 81.7% — a twelve-point overstatement.
Full mechanism in doc 08; what matters here is that **ECE belongs next to accuracy in any
report where the probabilities are used downstream.**

## 6. How the report is generated

`scripts/p9_validation_report.py` reads **only** from `docs/evidence/*.json`. It never
recomputes and never accepts a hand-typed number.

**Sections whose phase has not run say so explicitly:**

```
> **Not yet produced.** Run `scripts/p5_mil.py` to generate this section.
```

They are not silently omitted. A reader can tell the difference between "we measured this
and it was uninteresting" and "we did not measure this", which a missing section destroys.

## 7. Threats to validity

The report ends with six, stated plainly:

- **Geometry is derived, not cadastral.** Area figures inherit that approximation.
- **One taluk, one season.** 21 villages, an 8-day window. Transfer is untested.
- **Seven crops are not evaluable.** Collapsed to `Other`; no per-class claim.
- **The registry comparison is not independent** — Agrisnet publishes the aggregate of the
  same survey.
- **The cost saving rests on a stated assumption** about surveyor productivity.
- **Confident learning identifies disagreement, not error.** Which side is right is what a
  field visit resolves.

*A report that lists no threats has not looked for them.* Volunteer this section.

---

## Questions you must be able to answer

**"Your macro F1 is 0.528. Isn't that poor?"**
> It is low and it is honest. Two things drive it. First, the strict split — the same
> pipeline reports 0.772 under a random one. Second, `Other` and Banana rest on very
> few independent observations, and macro F1 weights them equally with rice. That is the
> point of using it: it refuses to let a 63%-prevalence class hide the rest.

**"Why is Banana so much worse than Sugarcane, when it has more records?"**
> Because records are not observations. Banana has 653 records from **64** capture events;
> Sugarcane has 432 from **117**. Sugarcane has more independent evidence despite
> fewer rows. This is the single clearest illustration of why we report effective n.

**"How do I know these numbers weren't cherry-picked?"**
> Every one regenerates from a script into `docs/evidence/`, and the report reads only
> from those artefacts. Two of our own runs produced results we then had to retract — the
> GSE-versus-seasonal comparison flipped sign twice — which is documented rather than
> hidden. Cherry-picking would have been easier if we had not written the generator.

**"Why report the random-split number at all if it's misleading?"**
> Because the gap *is* the finding. Reporting only 81.2% tells you our model is
> mediocre. Reporting 89.7% beside it tells you what a team following standard
> practice on this data would have believed, which is the thing we want FarmwiseAI to take
> away.
