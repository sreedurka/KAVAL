"""
KAVAL — the leakage protocol, in code.

plan.md §11 rule 3: no result without its split regime named. This module is the
only place splits are created, so that rule is enforced structurally rather than
by discipline.
"""

import numpy as np
from sklearn.model_selection import GroupKFold, StratifiedGroupKFold, StratifiedKFold

from .config import (HEADLINE_REGIME, KEY_BAG, KEY_PARCEL, N_FOLDS, SEED,
                     SPLIT_REGIMES)


def make_splits(df, regime, y=None, n_folds=N_FOLDS):
    """
    Yield (train_idx, test_idx) for a named regime.

    Regimes are positional indices into `df` as passed. `regime` must be a key of
    config.SPLIT_REGIMES — an unknown name raises rather than silently defaulting
    to a random split, which is the failure mode this module exists to prevent.
    """
    if regime not in SPLIT_REGIMES:
        raise ValueError(
            f"unknown split regime {regime!r}. Known: {list(SPLIT_REGIMES)}")

    y = df["y"].values if y is None else y
    key = SPLIT_REGIMES[regime]

    if key is None:                                   # regime 1, diagnostic only
        splitter = StratifiedKFold(n_folds, shuffle=True, random_state=SEED)
        splits = list(splitter.split(np.zeros(len(df)), y))
    else:
        # The headline regime also unions in the delineated field id when AI-1 has
        # produced one: parcels sharing a polygon carry identical zonal features,
        # which leaks exactly as a shared capture event does.
        groups = (headline_groups(df) if regime == HEADLINE_REGIME
                  else df[key].to_numpy())
        try:
            # Stratified where possible so rare classes appear in every fold.
            splitter = StratifiedGroupKFold(n_folds, shuffle=True, random_state=SEED)
            splits = list(splitter.split(np.zeros(len(df)), y, groups))
        except ValueError:
            splits = list(GroupKFold(n_folds).split(np.zeros(len(df)), y, groups))

        # The check the leakage-protocol skill requires. A bare `assert` would be
        # stripped by `python -O`, and this is the project's single central
        # integrity guarantee, so it raises unconditionally.
        for tr, te in splits:
            overlap = set(groups[tr]) & set(groups[te])
            if overlap:
                raise RuntimeError(
                    f"regime {regime}: {len(overlap)} groups appear in both train "
                    "and test. This is the leak the protocol exists to prevent.")
    return splits


def describe(regime, df=None):
    """
    Human-readable account of a regime. Pass `df` so the description states what
    actually happened rather than what the code is capable of — the field-id union
    only occurs once AI-1 has produced a `field_id` column.
    """
    extra = ""
    if regime == HEADLINE_REGIME and df is not None and "field_id" in df.columns:
        extra = (" Unioned with the delineated field id, since AI-1 has assigned "
                 "several parcels to one polygon.")
    return {
        "1-random": "Stratified row-wise k-fold. Diagnostic only — never a headline.",
        "2-parcel": "Grouped by parcel id. The obvious control; on this data it "
                    "changes nothing, because parcels are already 1:1 with rows.",
        "3-event": "Grouped by survey capture event (one photograph, up to 43 "
                   "parcels). THE HEADLINE REGIME.",
        "4-village": "Grouped by the village the parcel actually falls in "
                     "(village_spatial, not the recorded code). Geographic "
                     "generalisation.",
    }[regime] + extra


def effective_n(df, label_col="y"):
    """Records and INDEPENDENT capture events per class (metrics-report skill)."""
    return (df.groupby(label_col)
            .agg(records=(KEY_PARCEL, "size"), capture_events=(KEY_BAG, "nunique")))


# ---------------------------------------------------- composite grouping ---
def _union_find(n):
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
    return find, union


def composite_group(df, keys):
    """
    Merge several grouping keys into connected components.

    Two parcels that share a capture event must not be split across folds. So
    must two parcels that share a DELINEATED FIELD — once AI-1 assigns several
    survey points to one polygon they carry identical zonal features, which is a
    second leakage channel with exactly the same effect as the first.

    Grouping by each key separately would not be enough: parcel A shares a bag
    with B, B shares a field with C, so A and C are transitively linked and all
    three must travel together. Union-find is what makes that transitivity hold.

    Returns an integer component label per row.
    """
    keys = [k for k in keys if k in df.columns]
    if not keys:
        raise ValueError("no grouping keys present")
    n = len(df)
    find, union = _union_find(n)
    for k in keys:
        first = {}
        for i, v in enumerate(df[k].to_numpy()):
            if v is None or (isinstance(v, float) and np.isnan(v)):
                continue
            if v in first:
                union(first[v], i)
            else:
                first[v] = i
    return np.array([find(i) for i in range(n)])


def headline_groups(df):
    """
    The group key for the headline regime: capture event, unioned with delineated
    field where AI-1 has produced one. Falls back to capture event alone before
    Phase 2's primary path has run.
    """
    return composite_group(df, [KEY_BAG, "field_id"])
