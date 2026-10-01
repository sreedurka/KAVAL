"""
KAVAL / Phase 2e — evidence for the Phase 2 figures that lived only in prose.

A reproducibility audit found three sets of Phase 2 numbers quoted in the documents
with no evidence file behind them:

  (a) the per-crop FTW match table (Groundnut 62.5% ... Coconut 23.6%), which carries
      the "physical fields, not legal parcels" argument;
  (b) the distance from unmatched survey points to the nearest field (median 14 m,
      61% within 20 m, 0.9% beyond 200 m), which justifies the 20 m snap tolerance;
  (c) the raw versus post-processed size of the FTW layer.

This script recomputes all three READ-ONLY from the files Phase 2 used, through
p2_ftw_delineate.py's own functions (load_fields, clean_fields, snap_points,
measure), so every definition is the one the gate uses rather than a lookalike.

Definition of the per-crop rate: the gate's `match_rate` (point inside exactly one
delineated field) computed within each crop, at strict containment (tolerance 0) and
at the applied snap tolerance. The published table is the strict one; that is what
the overall 36.4% strict figure decomposes into.

Run:  .venv/bin/python KAVAL/scripts/p2e_ftw_match_detail.py
Out:  docs/evidence/p2e_ftw_match_detail.{json,md}
"""

import importlib.util
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))
from kaval import provenance  # noqa: E402
from kaval.config import (CRS, EVIDENCE, FTW_SNAP_TOLERANCE_M, INTERIM,  # noqa: E402
                          KEY_PARCEL, METRIC_CRS)

_spec = importlib.util.spec_from_file_location("p2", HERE.parent / "p2_ftw_delineate.py")
p2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p2)

RAW_FIELDS = INTERIM / "ftw_run" / "polygons.parquet"
RECORDS = INTERIM / "records.parquet"
OUT = EVIDENCE / "p2e_ftw_match_detail"


def per_crop(snapped, crops):
    rows = []
    n_fields = snapped["n_fields"].fillna(0).astype(int)
    for crop, idx in crops.groupby(crops).groups.items():
        k = n_fields.loc[idx]
        rows.append({"crop": crop, "points": int(len(k)),
                     "match_rate": round(float((k == 1).mean()), 4),
                     "unmatched_rate": round(float((k == 0).mean()), 4),
                     "ambiguous_rate": round(float((k > 1).mean()), 4)})
    return sorted(rows, key=lambda r: -r["match_rate"])


def main():
    for p in (RAW_FIELDS, RECORDS):
        provenance.require(p)
    rec = pd.read_parquet(RECORDS)
    raw = p2.load_fields(RAW_FIELDS)
    fields, fstats = p2.clean_fields(raw)

    pts = gpd.GeoDataFrame(rec[[KEY_PARCEL]],
                           geometry=gpd.points_from_xy(rec.lon, rec.lat),
                           crs=CRS).to_crs(METRIC_CRS)
    crops = pd.Series(rec["crop"].values, index=rec[KEY_PARCEL].values)

    strict = p2.snap_points(pts, fields, 0.0)
    snapped = p2.snap_points(pts, fields, FTW_SNAP_TOLERANCE_M)
    g_strict, *_ = p2.measure(strict, fields, None)
    g_snap, *_ = p2.measure(snapped, fields, None)

    # (b) distance from each strictly-unmatched point to the nearest cleaned field.
    miss = strict.index[strict["n_fields"].fillna(0).astype(int) == 0]
    near = gpd.sjoin_nearest(pts[pts[KEY_PARCEL].isin(miss)][[KEY_PARCEL, "geometry"]],
                             fields[["field_id", "geometry"]], how="left",
                             distance_col="d_m").drop_duplicates(KEY_PARCEL)
    d = near["d_m"].to_numpy()

    ev = {
        "definitions": {
            "match_rate": "share of survey points inside exactly one cleaned FTW field "
                          "(p2_ftw_delineate.measure), strict = no snapping",
            "unmatched_distance": "metres from each strictly-unmatched survey point to "
                                  "the nearest cleaned field, in " + METRIC_CRS,
        },
        "n_points": int(len(pts)),
        "overall": {
            "strict_match_rate": g_strict["match_rate"],
            f"snapped_{int(FTW_SNAP_TOLERANCE_M)}m_match_rate": g_snap["match_rate"],
        },
        "per_crop_strict": per_crop(strict, crops),
        f"per_crop_snapped_{int(FTW_SNAP_TOLERANCE_M)}m": per_crop(snapped, crops),
        "unmatched_distance_m": {
            "n_unmatched_strict": int(len(d)),
            "median": round(float(np.median(d)), 1),
            "p90": round(float(np.percentile(d, 90)), 1),
            "share_within_20m": round(float((d <= 20).mean()), 4),
            "share_beyond_200m": round(float((d > 200).mean()), 4),
        },
        # (c) the two layers, so documents say which one a figure describes.
        "layers": {
            "raw": {"polygons": int(len(raw)),
                    "total_ha": round(float(raw.geometry.area.sum() / 1e4), 1)},
            "post_processed": {"polygons": int(len(fields)),
                               "total_ha": round(float(fields.geometry.area.sum()
                                                       / 1e4), 1),
                               "cleaning": fstats},
        },
    }
    OUT.with_suffix(".json").write_text(json.dumps(ev, indent=2, default=str))

    L = ["# Phase 2e — FTW match detail\n",
         "Recomputed read-only through `p2_ftw_delineate.py`'s own functions.\n",
         f"Strict match rate {ev['overall']['strict_match_rate']:.1%}; at the "
         f"{FTW_SNAP_TOLERANCE_M:.0f} m snap tolerance "
         f"{list(ev['overall'].values())[1]:.1%}.\n",
         "## Per crop, strict containment\n",
         "| Crop | Points | Match | Unmatched | Ambiguous |", "|---|---:|---:|---:|---:|"]
    for r in ev["per_crop_strict"]:
        L.append(f"| {r['crop']} | {r['points']:,} | {r['match_rate']:.1%} "
                 f"| {r['unmatched_rate']:.1%} | {r['ambiguous_rate']:.1%} |")
    u = ev["unmatched_distance_m"]
    L += ["", "## Unmatched points: distance to the nearest field\n",
          f"{u['n_unmatched_strict']:,} points: median **{u['median']} m**, p90 "
          f"{u['p90']} m; {u['share_within_20m']:.1%} within 20 m, "
          f"{u['share_beyond_200m']:.1%} beyond 200 m.", "",
          "## Layers\n", "| Layer | Polygons | Hectares |", "|---|---:|---:|"]
    for k, v in ev["layers"].items():
        L.append(f"| {k} | {v['polygons']:,} | {v['total_ha']:,} |")
    OUT.with_suffix(".md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
