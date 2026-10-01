"""
KAVAL / Phase 2d — evidence for the shared-field double-counting correction.

p2_ftw_delineate.py gives a parcel that shares a physical FTW field the field's
POLYGON (right for drawing) but only an APPORTIONED share of its AREA. Handing each
sharing parcel the whole field's area would count the same land once per parcel.
This script measures that inflation from the feature store, plus what the
feature-store -> audit join drops, so the figures are regenerable rather than living
in a code comment.

Run:  .venv/bin/python KAVAL/scripts/p2d_shared_field_area.py
Out:  docs/evidence/p2d_shared_field_area.json
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kaval import provenance  # noqa: E402
from kaval.area import crop_area  # noqa: E402
from kaval.config import (DERIVED, EVIDENCE, KEY_FIELD, KEY_PARCEL,  # noqa: E402
                          SHARED_GEOMETRY_SOURCE)

FS = DERIVED / "feature_store.parquet"
AUDIT = DERIVED / "audit.parquet"
OUT = EVIDENCE / "p2d_shared_field_area.json"


def ha(x):
    return round(float(x) / 1e4, 1)


def main():
    provenance.require(FS)
    provenance.require(AUDIT)
    fs = pd.read_parquet(FS, columns=[KEY_PARCEL, "geometry_source", KEY_FIELD,
                                      "area_m2", "field_area_m2"])
    au = pd.read_parquet(AUDIT, columns=[KEY_PARCEL, "geometry_source", KEY_FIELD,
                                         "area_m2", "y_true", "y_pred"])

    sh = fs[(fs.geometry_source == SHARED_GEOMETRY_SOURCE) & fs[KEY_FIELD].notna()]
    unique_fields = sh.drop_duplicates(KEY_FIELD)

    dropped = fs[~fs[KEY_PARCEL].isin(au[KEY_PARCEL])]
    shared_dropped = dropped[(dropped.geometry_source == SHARED_GEOMETRY_SOURCE)
                             & dropped[KEY_FIELD].notna()]
    kept_fields = set(au.loc[(au.geometry_source == SHARED_GEOMETRY_SOURCE)
                             & au[KEY_FIELD].notna(), KEY_FIELD])
    partial = set(shared_dropped[KEY_FIELD]) & kept_fields

    ev = {
        "definitions": {
            "apportioned_total_ha": "sum of area_m2 over the feature store (field area "
                                    "divided among sharing parcels)",
            "inherited_total_ha": "sum of field_area_m2 over the feature store (every "
                                  "sharing parcel given the WHOLE field)",
            "shared_set_inherited_ha": "inherited area over parcels with geometry_source "
                                       "== ftw_shared",
            "shared_set_unique_field_ha": "the same shared set with each field counted "
                                          "once",
            "shared_set_inflation": "shared_set_inherited_ha / shared_set_unique_field_ha",
        },
        "n_feature_store_parcels": int(len(fs)),
        "n_audit_parcels": int(len(au)),
        "apportioned_total_ha": ha(fs.area_m2.sum()),
        "inherited_total_ha": ha(fs.field_area_m2.sum()),
        "shared_set_apportioned_ha": ha(sh.area_m2.sum()),
        "shared_set_inherited_ha": ha(sh.field_area_m2.sum()),
        "shared_set_unique_field_ha": ha(unique_fields.field_area_m2.sum()),
        "shared_set_inflation": round(float(sh.field_area_m2.sum()
                                            / unique_fields.field_area_m2.sum()), 2),
        "n_shared_fields": int(sh[KEY_FIELD].nunique()),
        "n_shared_parcels": int(len(sh)),
        "n_dropped_no_features": int(len(dropped)),
        "dropped_area_ha": ha(dropped.area_m2.sum()),
        "n_dropped_shared_parcels": int(len(shared_dropped)),
        "n_fields_partially_represented": int(len(partial)),
        "n_shared_fields_fully_lost": int(len(set(shared_dropped[KEY_FIELD]) - kept_fields)),
    }
    # Field-level aggregation over the AUDITED parcels (kaval/area.py): how much
    # area sits in shared fields whose records disagree on the crop, per label.
    ev["audited_total_ha"] = ha(au.area_m2.sum())
    ev["field_level_aggregation"] = {}
    for label in ("y_pred", "y_true"):
        t = crop_area(au, label)
        ev["field_level_aggregation"][label] = {
            "conflicted_area_ha": round(float(t.conflicted_area_ha.sum()), 1),
            "n_conflicted_fields": int(au[(au.geometry_source == SHARED_GEOMETRY_SOURCE)
                                          & au[KEY_FIELD].notna()]
                                       .groupby(KEY_FIELD)[label].nunique().gt(1).sum()),
            "area_ha_by_crop": {str(r[label]): round(float(r.area_ha), 1)
                                for _, r in t.iterrows()},
        }
    OUT.write_text(json.dumps(ev, indent=2))
    print(json.dumps(ev, indent=2))


if __name__ == "__main__":
    main()
