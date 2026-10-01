"""
KAVAL / Phase 2 — Parcel geometry.

The challenge asks for parcel-level classification but supplied ground-truth POINTS
and village boundaries. No cadastral geometry. Without polygons there is no
parcel-level area statistic, no zonal aggregation and no map.

Two paths, per plan.md §6 Phase 2:

  PRIMARY   AI-1, `p2_ftw_delineate.py` — pretrained Fields of The World U-Net over
            bi-temporal Sentinel-2. Needs imagery; run once GEE credentials exist.

  FALLBACK  this script — a village-constrained Voronoi tessellation of the survey
            points, clipped to a maximum parcel radius.

Why Voronoi rather than buffered circles: buffers overlap, so summing their areas
double-counts land and corrupts the crop-area statistic that the whole product
reports. A Voronoi tessellation partitions the village exactly once, which is the
property crop-area accounting actually needs. Cells are clipped to
FALLBACK_PARCEL_RADIUS_M so an isolated point cannot claim half a village.

Both paths write the same schema, distinguished by `geometry_source`, which feeds
the Record Trust Score (audit-signals).

Run:  .venv/bin/python KAVAL/scripts/p2_parcel_layer.py
Out:  data/interim/parcels.gpkg
"""

import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import voronoi_polygons
from shapely.geometry import MultiPoint
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kaval import provenance  # noqa: E402
from kaval.config import (CRS, EVIDENCE, FALLBACK_PARCEL_RADIUS_M, INTERIM,  # noqa: E402
                          KEY_PARCEL, KEY_VILLAGE, METRIC_CRS, VILLAGES)

OUT = INTERIM / "parcels.gpkg"
RECORDS = INTERIM / "records.parquet"


def village_voronoi(points: gpd.GeoDataFrame, boundary, radius_m: float):
    """
    Voronoi cells for `points`, clipped to `boundary` and to `radius_m` around
    each generating point. Returns geometries aligned to points.index.
    """
    if len(points) == 1:
        return [points.geometry.iloc[0].buffer(radius_m).intersection(boundary)]

    mp = MultiPoint(list(points.geometry))
    cells = list(voronoi_polygons(mp, extend_to=boundary.envelope).geoms)

    # voronoi_polygons does not guarantee input order; match each cell to the
    # point it contains rather than assuming alignment.
    out = [None] * len(points)
    pts = list(points.geometry)
    for cell in cells:
        for i, p in enumerate(pts):
            if out[i] is None and cell.contains(p):
                out[i] = cell
                break

    geoms = []
    for i, p in enumerate(pts):
        cell = out[i] if out[i] is not None else p.buffer(radius_m)
        g = cell.intersection(boundary).intersection(p.buffer(radius_m))
        geoms.append(g if not g.is_empty else p.buffer(radius_m / 2))
    return geoms


def main():
    provenance.require(RECORDS)
    rec = pd.read_parquet(RECORDS)
    vil = gpd.read_file(VILLAGES).to_crs(CRS)
    vil["village_code_int"] = pd.to_numeric(vil["village_co"], errors="coerce").astype("Int64")

    pts = gpd.GeoDataFrame(
        rec, geometry=gpd.points_from_xy(rec.lon, rec.lat), crs=CRS)

    # --- which village is this parcel ACTUALLY in? -------------------------
    # 1,930 records (13%) carry a village code that disagrees with the polygon the
    # point falls inside — almost all of it the Viswanathaperi Part-1/Part-2 pair
    # (911 <-> 912). That is a survey-record vs administrative-boundary
    # discrepancy and an audit finding in its own right, so we record it rather
    # than reconciling it silently.
    #
    # Geometry is built from the polygon the point is really in (otherwise cells
    # land outside their generating point and the tessellation breaks). The
    # recorded code is retained for registry joins.
    sj = gpd.sjoin(pts, vil[["village_code_int", "vill_name", "geometry"]],
                   how="left", predicate="within").drop_duplicates(subset=[KEY_PARCEL])
    pts["village_spatial"] = sj["village_code_int"].values
    pts["village_name"] = sj["vill_name"].values
    pts["village_code_mismatch"] = (
        pts["village_spatial"].notna()
        & (pts["village_spatial"].astype("Int64") != pts[KEY_VILLAGE]))
    # A point outside every polygon falls back to its recorded code.
    pts["village_spatial"] = pts["village_spatial"].fillna(pts[KEY_VILLAGE]).astype(int)

    pts = pts.to_crs(METRIC_CRS)
    vil_m = vil.to_crs(METRIC_CRS)

    report = {
        "records": len(rec),
        "village_polygons_supplied": len(vil),
        "villages_with_ground_truth": int(rec[KEY_VILLAGE].nunique()),
        "method": "village-constrained Voronoi, clipped to "
                  f"{FALLBACK_PARCEL_RADIUS_M} m radius",
    }
    report["village_code_mismatch_records"] = int(pts["village_code_mismatch"].sum())
    report["village_code_mismatch_pairs"] = (
        pts[pts.village_code_mismatch].groupby([KEY_VILLAGE, "village_spatial"])
        .size().sort_values(ascending=False).head(10)
        .rename_axis(["recorded", "actual"]).reset_index(name="n")
        .to_dict(orient="records"))

    # 25 polygons, 21 revenue villages with ground truth. The remaining 4 are
    # Reserve Forest (village_co 'YYY', lgdvcode 0) - protected land, not
    # unsurveyed farmland. They serve as a NEGATIVE CONTROL: a model that
    # confidently calls reserve forest a crop is miscalibrated.
    non_village = vil[vil["village_code_int"].isna()]["vill_name"].tolist()
    report["reserve_forest_polygons"] = non_village
    report["villages_with_ground_truth"] = int(pts["village_spatial"].nunique())

    frames, unmatched = [], 0
    for code, grp in pts.groupby("village_spatial"):
        match = vil_m[vil_m["village_code_int"] == code]
        if match.empty:
            # No boundary for this village code — fall back to plain buffers and count it.
            unmatched += len(grp)
            g = grp.copy()
            g["geometry"] = g.geometry.buffer(FALLBACK_PARCEL_RADIUS_M)
            g["geometry_source"] = "buffer_no_boundary"
            frames.append(g)
            continue
        boundary = unary_union(match.geometry.values)
        g = grp.copy()
        g["geometry"] = village_voronoi(grp, boundary, FALLBACK_PARCEL_RADIUS_M)
        g["geometry_source"] = "voronoi"
        frames.append(g)

    parcels = gpd.GeoDataFrame(pd.concat(frames), crs=METRIC_CRS)
    parcels["area_m2"] = parcels.geometry.area
    report["records_without_village_boundary"] = unmatched

    # --- quality checks ----------------------------------------------------
    report["area_m2"] = {
        "median": round(float(parcels.area_m2.median())),
        "p10": round(float(parcels.area_m2.quantile(0.10))),
        "p90": round(float(parcels.area_m2.quantile(0.90))),
        "total_ha": round(float(parcels.area_m2.sum()) / 1e4, 1),
    }
    empty = int((parcels.area_m2 <= 0).sum())
    report["empty_geometries"] = empty
    assert empty == 0, "Voronoi produced empty parcels"

    # Overlap check — the reason we chose Voronoi over buffers. Measured as AREA,
    # not as a predicate: shapely's `overlaps` returns true for adjacent cells
    # that merely share a boundary, so a pair count would be meaningless here.
    # Double-counted area is what would actually corrupt the crop-area statistic.
    sample = parcels.sample(min(3000, len(parcels)), random_state=0)
    pairs = gpd.sjoin(sample, parcels[[KEY_PARCEL, "geometry"]],
                      how="inner", predicate="overlaps")
    pairs = pairs[pairs[f"{KEY_PARCEL}_left"] != pairs[f"{KEY_PARCEL}_right"]]
    lut = parcels.set_index(KEY_PARCEL).geometry
    dbl = sum(lut[a].intersection(lut[b]).area
              for a, b in zip(pairs[f"{KEY_PARCEL}_left"], pairs[f"{KEY_PARCEL}_right"]))
    report["overlap_check"] = {
        "sampled_parcels": len(sample),
        "adjacent_pairs": int(len(pairs)),
        "double_counted_area_m2": round(float(dbl), 3),
        "as_pct_of_sampled_area": round(100 * dbl / float(sample.area_m2.sum()), 6),
        "note": "adjacent Voronoi cells share boundaries but enclose no common area, "
                "so crop-area totals do not double-count",
    }
    assert dbl / float(sample.area_m2.sum()) < 1e-6, "parcels double-count area"

    parcels = parcels.to_crs(CRS)
    keep = [KEY_PARCEL, "bag_id", KEY_VILLAGE, "village_spatial", "village_name",
            "village_code_mismatch", "crop", "crop_stage", "lat", "lon",
            "geometry_source", "area_m2", "geometry"]
    parcels[keep].to_file(OUT, driver="GPKG", layer="parcels")

    (EVIDENCE / "p2_parcel_layer.json").write_text(json.dumps(report, indent=2))
    provenance.record(
        OUT, classification="DERIVED",
        source="Voronoi tessellation of supplied ground-truth points, constrained by "
               "supplied village boundaries",
        licence="Derived from FarmwiseAI-supplied data — not for redistribution",
        produced_by="KAVAL/scripts/p2_parcel_layer.py",
        crs=CRS, transform=f"village-constrained Voronoi, clipped to "
                           f"{FALLBACK_PARCEL_RADIUS_M} m radius",
        inputs=["KAVAL/data/interim/records.parquet",
                "Dataset/Administrative_Boundary/Sivagiri_Villages.geojson"],
        notes="FALLBACK geometry. Superseded by p2_ftw_delineate.py once Sentinel-2 "
              "imagery is available. geometry_source distinguishes the two. "
              "Tessellation is grouped by the village polygon the point actually "
              "falls in, not the recorded village code; the disagreement is "
              "retained as village_code_mismatch.",
        agent="parcel-delineation")

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
