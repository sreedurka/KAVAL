---
name: leakage-protocol
description: The canonical validation-split rules for KAVAL. Load before training, evaluating, tuning, or reporting ANY model result. Use whenever you touch cross-validation, train/test splits, hyper-parameter search, or write an accuracy/F1 number into a document. Triggers: "split", "cross-validation", "CV", "train/test", "fold", "accuracy", "macro F1", "evaluate", "tune", "benchmark".
---

# Leakage Protocol

KAVAL's central claim is that headline accuracy on this dataset is mostly a property of
the split, not the model. That claim obliges us to be stricter than anyone else.

## The four regimes

Always identified by number and name. Never report a metric without naming its regime.

| # | Regime | Group key | Use |
|---|---|---|---|
| 1 | Random row | none (stratified) | **Diagnostic only.** Report to expose the gap. Never as a headline. |
| 2 | Parcel | `parcel_id` | Sanity floor. |
| 3 | **Capture event** | `image_path` | **The headline regime.** All primary results use this. |
| 4 | Village (spatial) | `village__1` | Geographic generalisation. Report beside the headline. |

## Why regime 3 is the headline

One survey photograph supplies up to 43 parcel labels. Those parcels sit a median 117 m
apart, share one crop label, and their embeddings are near-duplicates. Under a random
split they land on both sides of the fold. The model retrieves a neighbour rather than
generalising.

Group key is `image_path`. Use `sklearn.model_selection.GroupKFold` or
`StratifiedGroupKFold`. Never `KFold` or `train_test_split` on rows.

## Hard rules

1. **Name the regime with every number.** "81.7% accuracy" is incomplete.
   "81.7% accuracy (regime 3, capture-event-grouped, 5-fold)" is a result.
2. **Tune inside the training folds only.** Hyper-parameter search runs on train/validation.
   The held-out fold is scored once, after tuning is frozen.
3. **Calibrate on validation, never on test.** Isotonic/Platt fitting is model fitting.
4. **The group key must survive every transform.** Carry `image_path`, `parcel_id` and
   `village__1` through joins, aggregations and feature engineering. Assert they are
   present before splitting.
5. **A class with fewer than 5 capture events is not evaluable.** Collapse it to `Other`
   and say so. Do not report an F1 for it.
6. **>95% accuracy is a bug report.** If a run produces it, stop and find the leak before
   reporting anything.
7. **Oversampling, SMOTE and augmentation happen inside the training fold**, after the
   split, never before.

## Required check before reporting

```python
assert len(set(groups[train]) & set(groups[test])) == 0, "group leak across split"
```

Run it. Put it in the script, not in your head.

## Reporting template

> Model X, features Y, **regime 3 (capture-event-grouped, 5-fold)**:
> accuracy A ± s, macro F1 F ± s.
> Regime 1 (random row) for the same configuration: accuracy A'. The gap is the leak.
