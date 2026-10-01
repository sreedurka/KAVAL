"""
KAVAL / Phase 1 — Ground-truth repair and canonicalisation.

Phase 0 found three defects in the supplied survey records that must be repaired
before anything joins to them:

  * 645 records store two coordinates in one cell, ';'-joined
  *  13 records geocode outside the study area
  * 283 records have a blank subdivision, which breaks the parcel key if dropped

This script produces the canonical record table every later phase reads. It repairs
what can be repaired, quarantines what cannot, and counts everything. Nothing is
silently coerced.

Run:  .venv/bin/python KAVAL/scripts/p1_repair_ground_truth.py
Out:  data/interim/records.parquet, data/interim/records_quarantined.csv
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kaval import provenance  # noqa: E402
from kaval.config import (EVIDENCE, GT_POINTS, INTERIM, KEY_BAG, KEY_PARCEL,  # noqa: E402
                          KEY_VILLAGE, LABEL, STAGE)

# Study-area envelope, generous around Sivagiri taluk. Anything outside is a defect.
BBOX = dict(lat=(8.0, 14.0), lon=(76.0, 81.0))
OUT = INTERIM / "records.parquet"
QUARANTINE = INTERIM / "records_quarantined.csv"


def split_multivalue(s):
    """'9.322743;9.32259' -> 9.322743. Returns (value, was_multivalued)."""
    t = str(s).strip()
    if ";" in t:
        head = t.split(";")[0]
        try:
            return float(head), True
        except ValueError:
            return np.nan, True
    try:
        return float(t), False
    except ValueError:
        return np.nan, False


def main():
    df = pd.read_csv(GT_POINTS)
    report = {"input_records": len(df)}

    # --- canonical keys ----------------------------------------------------
    # Blank subdivisions are normalised, never dropped: a parcel with no
    # subdivision is still a parcel (parcel-join skill).
    df["sub_divi_1"] = df["sub_divi_1"].fillna("").astype(str).str.strip()
    report["blank_subdivision"] = int((df["sub_divi_1"] == "").sum())

    df[KEY_PARCEL] = (df["village__1"].astype(str) + "_"
                      + df["survey_n_1"].astype(str) + "_"
                      + df["sub_divi_1"])
    df[KEY_BAG] = df["image_path"].astype(str)
    df[KEY_VILLAGE] = df["village__1"].astype(int)
    df[LABEL] = df["final_crop_name"].astype(str)
    df[STAGE] = df["final_crop_stage"].astype(str)

    # --- repair photo coordinates -----------------------------------------
    for src, dst in [("image_latitude", "photo_lat"), ("image_longitude", "photo_lon")]:
        vals = df[src].map(split_multivalue)
        df[dst] = [v[0] for v in vals]
        df[dst + "_was_multivalued"] = [v[1] for v in vals]

    df["photo_coord_multivalued"] = (df["photo_lat_was_multivalued"]
                                     | df["photo_lon_was_multivalued"])
    report["photo_coord_multivalued"] = int(df["photo_coord_multivalued"].sum())

    in_area = (df["photo_lat"].between(*BBOX["lat"])
               & df["photo_lon"].between(*BBOX["lon"]))
    df["photo_coord_out_of_area"] = ~in_area
    report["photo_coord_out_of_area"] = int((~in_area).sum())
    # Unusable photo coordinates become NaN rather than a wrong number. The
    # record survives; the photo-distance trust signal degrades gracefully.
    df.loc[~in_area, ["photo_lat", "photo_lon"]] = np.nan

    # --- parcel coordinates are the join geometry: defects here quarantine --
    parcel_ok = (df["final_lat"].between(*BBOX["lat"])
                 & df["final_long"].between(*BBOX["lon"]))
    report["parcel_coord_invalid"] = int((~parcel_ok).sum())
    quarantined = df.loc[~parcel_ok].copy()
    df = df.loc[parcel_ok].copy()

    # --- mixed-crop declarations ------------------------------------------
    df["mixed_crop"] = df["rabi_crop_classification"].astype(str).str.contains(";")
    report["mixed_crop_records"] = int(df["mixed_crop"].sum())

    # --- survey date -------------------------------------------------------
    # Defect found in Phase 1: the same row stores the same date in two different
    # formats. `timestamp` is MM-DD-YYYY ('11-08-2024') while `image_timestamp`
    # is DD-MM-YYYY ('08-11-2024 00:00'). The single value '13-11-2024' is DD-MM
    # in both, because month 13 is impossible and the collection app fell back.
    #
    # Naive dayfirst parsing of `timestamp` scatters a one-week survey across
    # June-December. We therefore take `image_timestamp` (unambiguously DD-MM)
    # as authoritative and cross-check `timestamp` against it.
    df["survey_date"] = pd.to_datetime(
        df["image_timestamp"].astype(str).str.slice(0, 10), dayfirst=True, errors="coerce")

    ts_monthfirst = pd.to_datetime(df["timestamp"], dayfirst=False, errors="coerce")
    ts_dayfirst = pd.to_datetime(df["timestamp"], dayfirst=True, errors="coerce")
    ts = ts_monthfirst.fillna(ts_dayfirst)
    report["survey_date_disagreement"] = int((ts.dt.date != df["survey_date"].dt.date).sum())
    report["timestamp_format_defect"] = (
        "`timestamp` is MM-DD-YYYY and `image_timestamp` is DD-MM-YYYY within the same "
        "row; '13-11-2024' is DD-MM in both. `image_timestamp` taken as authoritative.")
    report["survey_date_unparsed"] = int(df["survey_date"].isna().sum())
    report["survey_date_range"] = [str(df["survey_date"].min().date()),
                                   str(df["survey_date"].max().date())]
    report["survey_duration_days"] = int(
        (df["survey_date"].max() - df["survey_date"].min()).days) + 1

    # --- bag structure -----------------------------------------------------
    df["bag_size"] = df.groupby(KEY_BAG)[KEY_BAG].transform("size")
    report["capture_events"] = int(df[KEY_BAG].nunique())
    report["max_bag_size"] = int(df["bag_size"].max())

    # --- invariants (parcel-join skill) ------------------------------------
    assert df[KEY_PARCEL].notna().all()
    assert df[KEY_BAG].notna().all()
    assert df.groupby(KEY_BAG)[LABEL].nunique().max() == 1, \
        "a capture event carries more than one crop label — investigate before proceeding"

    # Duplicate parcel keys: a parcel surveyed twice. Keep the first, count them.
    dupes = int(df[KEY_PARCEL].duplicated().sum())
    report["duplicate_parcel_keys"] = dupes
    df = df.drop_duplicates(KEY_PARCEL, keep="first")

    keep = [KEY_PARCEL, KEY_BAG, KEY_VILLAGE, LABEL, STAGE, "final_lat", "final_long",
            "photo_lat", "photo_lon", "photo_coord_multivalued",
            "photo_coord_out_of_area", "mixed_crop", "survey_date", "bag_size",
            "survey_n_1", "sub_divi_1", "rabi_crop_classification"]
    out = df[keep].rename(columns={"final_lat": "lat", "final_long": "lon",
                                   "survey_n_1": "survey_no",
                                   "sub_divi_1": "subdivision"})
    out.to_parquet(OUT, index=False)
    quarantined.to_csv(QUARANTINE, index=False)
    report["output_records"] = len(out)
    report["quarantined_records"] = len(quarantined)
    provenance.record(
        QUARANTINE, classification="DERIVED",
        source="Records whose PARCEL coordinate falls outside the study area and "
               "therefore cannot be joined to geometry",
        licence="Derived from FarmwiseAI-supplied data — not for redistribution",
        produced_by="KAVAL/scripts/p1_repair_ground_truth.py",
        transform="filtered out of records.parquet, retained rather than discarded",
        inputs=[str(GT_POINTS.name)],
        notes=f"{len(quarantined)} records. Empty is the expected result; a non-empty "
              "file is a finding.", agent="data-acquisition")

    (EVIDENCE / "p1_repair.json").write_text(json.dumps(report, indent=2, default=str))

    provenance.record(
        OUT, classification="DERIVED",
        source="Repaired from FarmwiseAI-supplied Ground_truth_Points.csv",
        licence="Derived from FarmwiseAI-supplied data — not for redistribution",
        produced_by="KAVAL/scripts/p1_repair_ground_truth.py",
        temporal_extent="survey window November 2024 (Rabi 2024-25)",
        transform=("multi-valued photo coordinates split; out-of-area photo coordinates "
                   "nulled; blank subdivisions normalised; duplicate parcel keys dropped; "
                   "invalid parcel coordinates quarantined"),
        inputs=[str(GT_POINTS.name)],
        notes=f"{len(out):,} canonical records, {report['capture_events']:,} capture events.",
        agent="data-acquisition")

    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
