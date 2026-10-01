"""
KAVAL / crop-area aggregation — the ONE place crop area is summed.

plan.md Phase 2: "A polygon holding several records with conflicting labels has no
defensible area figure; Phase 7 aggregates at field level for
geometry_source == 'ftw_shared'."

`area_m2` on a shared-field parcel is an apportioned share of the field, so a
per-parcel sum is correct in total but splits one physical field across several
crops. Here every shared field gets one crop:

  * field crop  = the label holding the largest apportioned area within the field
                  (across all groups); ties break to the alphabetically first label.
  * field area  = sum of its records' area_m2 PRESENT in `df` (not field_area_m2,
                  so records dropped upstream do not inflate totals).
  * a field that straddles two groups (e.g. two villages by polygon membership)
    keeps its single crop and contributes to each group the area of its records
    in that group, so per-group totals are unchanged.
  * `conflicted_area_ha` = area of fields whose records disagree on the label.

Non-shared parcels are summed as before. Pure function; does not mutate `df`.
"""

import numpy as np
import pandas as pd

from .config import AREA_CHECK_TOL_HA, KEY_FIELD, SHARED_GEOMETRY_SOURCE


def crop_area(df, label_col, group_cols=()):
    group_cols = list(group_cols)
    d = df[[c for c in dict.fromkeys(group_cols + [label_col, "area_m2", KEY_FIELD,
                                                   "geometry_source"])]].copy()
    shared = d["geometry_source"].eq(SHARED_GEOMETRY_SOURCE) & d[KEY_FIELD].notna()

    d["_crop"] = d[label_col]
    d["_conflict"] = False
    if shared.any():
        s = d.loc[shared]
        by_label = (s.groupby([KEY_FIELD, label_col])["area_m2"].sum()
                    .reset_index()
                    .sort_values([KEY_FIELD, "area_m2", label_col],
                                 ascending=[True, False, True]))
        winner = by_label.drop_duplicates(KEY_FIELD).set_index(KEY_FIELD)[label_col]
        d.loc[shared, "_crop"] = s[KEY_FIELD].map(winner)
        nuniq = s.groupby(KEY_FIELD)[label_col].transform("nunique")
        d.loc[shared, "_conflict"] = (nuniq > 1).to_numpy()

    d["_conflict_m2"] = np.where(d["_conflict"], d["area_m2"], 0.0)
    keys = group_cols + ["_crop"]
    out = (d.groupby(keys, dropna=False)
           .agg(area_m2=("area_m2", "sum"), conflicted_m2=("_conflict_m2", "sum"))
           .reset_index().rename(columns={"_crop": label_col}))
    out["area_ha"] = out["area_m2"] / 1e4
    out["conflicted_area_ha"] = out["conflicted_m2"] / 1e4
    out = out.drop(columns=["area_m2", "conflicted_m2"])

    # Invariant: aggregation moves area between crops, never creates or destroys it.
    old = d.groupby(group_cols, dropna=False)["area_m2"].sum() / 1e4 if group_cols \
        else pd.Series({"all": d["area_m2"].sum() / 1e4})
    new = out.groupby(group_cols, dropna=False)["area_ha"].sum() if group_cols \
        else pd.Series({"all": out["area_ha"].sum()})
    if not np.allclose(old.sort_index().to_numpy(), new.sort_index().to_numpy(),
                       atol=AREA_CHECK_TOL_HA, rtol=0):
        raise AssertionError("crop_area changed group totals")
    return out
