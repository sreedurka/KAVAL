---
name: metrics-report
description: How KAVAL computes and presents model metrics, per-class results, confusion matrices and effective sample size. Load when producing any validation report, results table, confusion matrix, or per-class precision/recall/F1 breakdown. Triggers: "metrics", "per-class", "confusion matrix", "precision recall", "validation report", "results table", "F1".
---

# Metrics & Reporting

## Always report together

- Overall accuracy **and** macro F1. Accuracy alone hides the minority classes; this
  dataset is 63% rice, so accuracy is nearly meaningless on its own.
- Per-class precision, recall, F1 **and effective n**.
- Confusion matrix, raw counts and row-normalised.
- Expected Calibration Error (ECE) wherever probabilities are used downstream.
- Fold standard deviation, not just the mean.

## Effective n is mandatory

Never print a per-class table with only a record count. The record count is inflated
~4.6x by capture-event label copying. Every per-class row carries both:

| Crop | Records | **Capture events** | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|

Add this note under any per-class table containing a class with <30 capture events:

> Classes with few independent capture events have metrics with very wide error bars.
> Marigold's 36 records are 3 field observations; its F1 should not be read as a
> performance estimate.

## Comparison tables

When comparing embedding sources or model heads, vary exactly one thing per table and
hold the split regime fixed. State the regime in the caption.

## Never

- Report a metric without its split regime (see `leakage-protocol`).
- Round away a fold standard deviation.
- Present regime-1 numbers as a headline.
- Report per-class F1 for a class with <5 capture events; collapse it to `Other`.
