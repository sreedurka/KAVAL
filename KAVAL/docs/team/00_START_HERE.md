# 00 · Start Here

**Read this first. It takes ten minutes and everything else assumes it.**

You are defending KAVAL in a review. The people asking questions will be technical, will
know remote sensing and land administration better than we do, and will look for the
place where we overclaimed. This folder exists so that any of us can answer any question,
not only the ones about our own phase.

---

## The one-sentence version

> FarmwiseAI asked for a crop classifier at >95% accuracy. We measured the data, found
> that target is only reachable by cheating at validation, and built the thing the target
> was standing in for: a system that tells an agriculture department **which survey
> records to trust, which to re-verify, and which parcels never need visiting again.**

**The classifier is the instrument. The product is the audit.**

## The three numbers to memorise

| Number | What it is |
|---|---|
| **14,643 → 3,204** | Ground-truth records versus actual independent observations. One photograph labels up to 43 parcels. |
| **89.7% → 70.8%** | Same model, same features. Only the validation split changes. |
| **18.3%** | Share of parcels where satellite and survey disagree — i.e. the share that needs a human at all. |

If you remember nothing else, remember that the second row is the whole argument.

## Who owns what

| Member | Role | Phases | Their documents |
|---|---|---|---|
| **M1** | Data & Geospatial | 1, 2 | 03, 04 |
| **M2** | ML & Validation | 3, 4, 5, 9 | 05, 06, 07, 11 |
| **M3** | Audit Logic & Backend | 6, 7 | 08, 09, 10 |
| **M4** | Product & Frontend | 8, 9 | 12 |
| *All* | — | — | 00, 01, 02, 13, 14 |

**You must be able to explain your own documents in depth and everyone else's in outline.**

## Reading order

| # | Document | Who |
|---|---|---|
| 00 | Start Here — this file | everyone |
| 01 | [System Architecture](01_ARCHITECTURE.md) | everyone |
| 02 | [Domain Primer](02_DOMAIN_PRIMER.md) — crop surveys, land records, remote sensing | everyone |
| 03 | [Data Acquisition & Provenance](03_DATA_ACQUISITION.md) | M1 |
| 04 | [Parcel Geometry & Field Delineation](04_GEOMETRY.md) | M1 |
| 05 | [Features & Embeddings](05_FEATURES_EMBEDDINGS.md) | M2 |
| 06 | [The Leakage Protocol](06_LEAKAGE_PROTOCOL.md) — **the core contribution** | M2 |
| 07 | [Models & Multiple-Instance Learning](07_MODELS_MIL.md) | M2 |
| 08 | [Calibration, Confident Learning & Trust](08_AUDIT_LAYER.md) | M3 |
| 09 | [Verification Economics](09_VERIFICATION_ECONOMICS.md) | M3 |
| 10 | [API & Agentic Analyst](10_API_ANALYST.md) | M3 |
| 11 | [Validation & Metrics](11_VALIDATION_METRICS.md) | M2 |
| 12 | [Product & Interface](12_PRODUCT_FRONTEND.md) | M4 |
| 13 | [What We Got Wrong](13_CORRECTIONS.md) — **read before any review** | everyone |
| 14 | [Review Preparation](14_REVIEW_PREP.md) — questions and answers | everyone |

## The rule that governs everything

From `plan.md` §11:

1. **No number without a script.** Every figure in every document regenerates from
   `KAVAL/scripts/` into `KAVAL/docs/evidence/`.
2. **No result without its split regime.** "81.7% accuracy" is incomplete. "81.7%, MLP
   head, capture-event-grouped with shared delineated fields unioned in, 5-fold" is a
   result.
3. **Never claim >95%.** If a run produces it, that is a bug report.
4. **Report negative results.** Two of our components failed at the job they were designed
   for. We say so, and we explain what they are good for instead.

## The posture to take in review

Do not defend. Explain, and volunteer the weakness first.

If someone finds a flaw before you name it, you look like you were hiding it. If you name
it first, you look like you understand your own system. We have **twenty-three logged
corrections** in `progress.md` — including a metric that was a tautology and an area bug
that inflated a published figure by 3.88×. That log is not an embarrassment. For a project
whose entire thesis is validation honesty, it is the strongest evidence we have.

Read **[13 · What We Got Wrong](13_CORRECTIONS.md)** before you walk into the room.
