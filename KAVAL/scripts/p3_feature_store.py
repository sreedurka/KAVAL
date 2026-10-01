"""
KAVAL / Phase 3 — Feature store.

Joins the Phase 2 parcel layer to satellite features and produces the single table
every downstream phase reads. One row per parcel, with every leakage group key
intact — Phase 4 is impossible without them.

Feature source: the Earth Engine export from prior work (plan.md §12), which carries
the 64-d Google Satellite Embedding plus 12 seasonal Sentinel-1/2 bands for 14,611
parcels. When `p1_acquire_gee.py` has run against the FTW parcel layer, point
--features at its output instead; the schema is identical.

Also computes the stage-plausibility and heterogeneity signals the Record Trust
Score needs (audit-signals), because they derive from the same join.

Run:  .venv/bin/python KAVAL/scripts/p3_feature_store.py
Out:  data/derived/feature_store.parquet
"""

import argparse
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kaval import provenance  # noqa: E402
from kaval.config import (CRS, DERIVED, EVIDENCE, GSE_BANDS, INTERIM, KEY_BAG,  # noqa: E402
                          KEY_PARCEL, KEY_VILLAGE, LABEL, MIN_EVENTS_PER_CLASS,
                          OTHER_CLASS, PRIOR_FEATURES, ROOT, SEASONAL_BANDS,
                          STAGE)

OUT = DERIVED / "feature_store.parquet"
PARCELS = INTERIM / "parcels.gpkg"
RECORDS = INTERIM / "records.parquet"

FEATURES = GSE_BANDS + SEASONAL_BANDS


def _repo_rel(p):
    """Path relative to the repository root (config.ROOT) when it lies inside it."""
    p = Path(p).resolve()
    return str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)


def stage_plausibility(df):
    """
    Is the declared crop stage plausible for that crop in a single 8-day survey?

    The signal is confounded by design: Coconut is a perennial and is ~99%
    'full_growth', Marigold is 100% 'flowering'. So we do not ask whether the stage
    is *typical* — that would just re-encode the crop. We ask whether it is RARE for
    the crop, which is what would make a record worth a second look.
    """
    share = (df.groupby([LABEL, STAGE]).size()
             / df.groupby(LABEL).size()).rename("share")
    df = df.merge(share, left_on=[LABEL, STAGE], right_index=True, how="left")
    # Rare stage for that crop -> low plausibility. Clipped so a genuinely rare but
    # legitimate stage does not dominate the trust score on its own.
    df["stage_plausibility"] = df["share"].fillna(0.0).clip(0, 0.5) / 0.5
    return df.drop(columns="share")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", default=str(PRIOR_FEATURES),
                    help="CSV of per-parcel satellite features")
    args = ap.parse_args()

    provenance.require(PARCELS)
    provenance.require(RECORDS)

    parcels = gpd.read_file(PARCELS)
    assert parcels.crs.to_epsg() == 4326, "parcel layer must be EPSG:4326"
    rec = pd.read_parquet(RECORDS)

    feats = pd.read_csv(provenance.require(args.features))
    feats[KEY_PARCEL] = feats["parcel_id"].astype(str)

    report = {"parcels": len(parcels), "feature_rows": len(feats)}

    # --- join --------------------------------------------------------------
    # Composite key only. Never lat/lon rounding (parcel-join skill).
    df = parcels.merge(
        feats[[KEY_PARCEL] + [c for c in FEATURES if c in feats.columns]],
        on=KEY_PARCEL, how="left", validate="one_to_one")

    present = [c for c in FEATURES if c in df.columns]
    missing_feats = [c for c in FEATURES if c not in df.columns]
    report["features_present"] = len(present)
    report["features_missing"] = missing_feats

    unmatched = df[present].isna().all(axis=1)
    report["parcels_without_features"] = int(unmatched.sum())
    report["parcels_without_features_pct"] = round(100 * unmatched.mean(), 2)
    # Flagged and counted, never silently dropped.
    df["has_features"] = ~unmatched

    # --- record-level signals for the trust score --------------------------
    keep_rec = [KEY_PARCEL, "photo_lat", "photo_lon", "mixed_crop", "bag_size",
                "photo_coord_multivalued", "photo_coord_out_of_area", "survey_date"]
    df = df.merge(rec[keep_rec], on=KEY_PARCEL, how="left", validate="one_to_one")

    # Photo-to-parcel distance, the evidence-quality signal from Phase 0.
    m = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat),
                         crs=CRS).to_crs("EPSG:32643")
    p = gpd.GeoSeries(gpd.points_from_xy(df.photo_lon, df.photo_lat),
                      crs=CRS).to_crs("EPSG:32643")
    df["photo_distance_m"] = m.geometry.distance(p, align=False)
    # Computed as a PROJECTED distance over the joined parcel set. gt_forensics.py
    # reports the canonical figure (1,436 m) as a haversine distance over all valid
    # records. The ~3 m difference is method and population, not disagreement; the
    # published number is the forensics one.
    report["photo_distance_m_median"] = round(float(df.photo_distance_m.median()), 1)
    report["photo_distance_method"] = (
        "projected (EPSG:32643) over joined parcels; the canonical published figure "
        "is the haversine median in gt_forensics.json")
    report["photo_distance_missing"] = int(df.photo_distance_m.isna().sum())

    df = stage_plausibility(df)

    # Within-parcel heterogeneity. The prior export carries only parcel means, so
    # the embedding-std channel is unavailable here; we substitute the spread of the
    # seasonal NDVI series, which captures a parcel whose signal moves inconsistently.
    ndvi_cols = [c for c in df.columns if c.endswith("_NDVI")]
    if len(ndvi_cols) >= 2:
        df["heterogeneity"] = df[ndvi_cols].std(axis=1)
        report["heterogeneity_source"] = "std across seasonal NDVI windows"
    else:
        df["heterogeneity"] = np.nan
        report["heterogeneity_source"] = "unavailable"

    # --- evaluable classes (leakage-protocol rule 5) -----------------------
    events = df.groupby(LABEL)[KEY_BAG].nunique()
    evaluable = set(events[events >= MIN_EVENTS_PER_CLASS].index)
    df["y"] = np.where(df[LABEL].isin(evaluable), df[LABEL], OTHER_CLASS)
    report["evaluable_classes"] = sorted(evaluable)
    report["collapsed_to_other"] = sorted(set(events.index) - evaluable)
    report["class_events"] = events.sort_values(ascending=False).to_dict()
    report["class_records"] = df[LABEL].value_counts().to_dict()

    # --- invariants (parcel-join skill) ------------------------------------
    assert df[KEY_PARCEL].notna().all()
    assert df[KEY_BAG].notna().all(), "leakage group key lost in the join"
    assert df[KEY_VILLAGE].notna().all()
    assert df.groupby(KEY_BAG)[LABEL].nunique().max() == 1, "a bag carries >1 label"
    assert df[KEY_PARCEL].is_unique

    report["bags"] = int(df[KEY_BAG].nunique())
    report["villages"] = int(df["village_spatial"].nunique())
    report["rows"] = len(df)

    df.drop(columns="geometry").to_parquet(OUT, index=False)
    # Geometry kept separately so the API can serve it without loading 76 features.
    geom_path = DERIVED / "parcel_geometry.gpkg"
    parcels[[KEY_PARCEL, "geometry"]].to_file(geom_path, driver="GPKG", layer="parcels")
    provenance.record(
        geom_path, classification="DERIVED",
        source="Parcel geometry split out of the Phase 2 layer for API serving",
        licence="Derived from FarmwiseAI-supplied data — not for redistribution",
        produced_by="KAVAL/scripts/p3_feature_store.py", crs=CRS,
        transform="geometry column only, keyed by parcel_id",
        inputs=["KAVAL/data/interim/parcels.gpkg"],
        notes="Served by GET /geo/parcels.", agent="embedding-engineer")

    (EVIDENCE / "p3_feature_store.json").write_text(json.dumps(report, indent=2, default=str))
    provenance.record(
        OUT, classification="DERIVED",
        source="Phase 2 parcel layer joined to Google Satellite Embedding + seasonal "
               "Sentinel-1/2 features",
        licence="Derived from FarmwiseAI-supplied data and Google Earth Engine exports",
        produced_by="KAVAL/scripts/p3_feature_store.py",
        temporal_extent="GSE annual 2024; seasonal S1..S4 windows as recorded in the "
                        "--features source entry (calendar-2024 quarters for the "
                        "default CropSight export, not config.SEASON_WINDOWS)",
        # Repo-relative, derived from config.ROOT, so the entry does not carry
        # whichever machine's absolute path the script happened to run on.
        inputs=["KAVAL/data/interim/parcels.gpkg",
                "KAVAL/data/interim/records.parquet", _repo_rel(args.features)],
        transform="one-to-one join on parcel_id; photo distance, stage plausibility and "
                  "heterogeneity computed; classes with <"
                  f"{MIN_EVENTS_PER_CLASS} capture events collapsed to '{OTHER_CLASS}'",
        notes=f"{len(df):,} parcels, {len(present)} features, "
              f"{report['bags']:,} capture-event bags.",
        agent="embedding-engineer")

    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
