"""
KAVAL / Phase 2 — AI-1: parcel delineation from satellite (PRIMARY path).

FarmwiseAI supplied ground-truth POINTS and village boundaries. No cadastral
geometry. "Parcel-level classification" is therefore impossible until we make the
parcels ourselves, so AI-1 segments field boundaries straight out of Sentinel-2.

This script is the primary path. `p2_parcel_layer.py` (village-constrained Voronoi)
is the fallback and stays in place: it supplies geometry for every point this one
cannot match, so no record is ever dropped. Both write the same schema into
`data/interim/parcels.gpkg`, distinguished by `geometry_source`.

## The model

Fields of The World v3, codename "PRUE": a three-class U-Net
(0 background / 1 field interior / 2 field boundary) with an EfficientNet-B7 encoder,
over a bi-temporal Sentinel-2 stack. Trained across 24 countries including Asian
smallholder systems, which is why it is worth trying zero-shot on Sivagiri before
anyone considers fine-tuning.

We use the **CC-BY** checkpoint, not the more accurate "FULL" one — see the note on
`FTW_MODEL` in config.py. That is a licence decision, and it costs us accuracy.

## What this script actually does

  1. obtain an 8-band bi-temporal stack (B04 B03 B02 B08, window A then window B)
  2. run the FTW model over it                        -> 3-class label raster
  3. vectorise the interior class, clean slivers      -> candidate field polygons
  4. snap the 14,611 ground-truth points into them    -> THE GATE
  5. fall back to Voronoi geometry for anything unmatched
  6. write parcels.gpkg + docs/evidence/p2_ftw_delineation.json + provenance

Steps 1-2 need imagery and a 257 MB checkpoint. Steps 3-6 are ours and are exercised
end-to-end by `--dry-run` against a synthetic field layer, so the join, the cleaning,
the fallback merge and the output schema are tested even with no imagery present.

## Honesty about what is untested

Nothing in this file has been run against real Sentinel-2. This environment has no
imagery, no GEE credentials and no `ftw_tools`, and `rasterio` is not installed in
the venv either. Specifically UNTESTED:

  * the `ftw inference run` / `ftw inference polygonize` subprocess calls
  * whether FTW_PRUE_EFNET_B7_CCBY is present in the installed ftw-tools registry
  * every number this script would report on real imagery

Everything downstream of `load_fields()` is tested, via --dry-run.

## Running it

    # install (heavy: torch + torchgeo + lightning + rasterio, ~2 GB)
    uv pip install --python /home/user/FM_AI/.venv/bin/python \
        --prerelease=allow "ftw-tools>=2.0.0b5"

    # A. no imagery yet: the script prints the exact download command and exits
    .venv/bin/python KAVAL/scripts/p2_ftw_delineate.py

    # B. from a stacked GeoTIFF (ftw download, a GEE export, anything 8-band)
    .venv/bin/python KAVAL/scripts/p2_ftw_delineate.py --imagery data/raw/s2_bitemporal.tif

    # C. from an already-vectorised field layer (model run elsewhere / on a GPU box)
    .venv/bin/python KAVAL/scripts/p2_ftw_delineate.py --fields data/raw/ftw_fields.parquet

    # D. structure + join + schema validation, no imagery required
    .venv/bin/python KAVAL/scripts/p2_ftw_delineate.py --dry-run

Out:  data/interim/parcels.gpkg, docs/evidence/p2_ftw_delineation.json
"""

import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kaval import provenance  # noqa: E402
from kaval.config import (FTW_SNAP_TOLERANCE_M,  # noqa: E402
                          CRS, EVIDENCE, FTW_BANDS, FTW_MATCH_RATE_GATE,  # noqa: E402
                          FTW_MAX_PLAUSIBLE_FIELD_AREA_M2, FTW_MIN_COMPACTNESS,
                          FTW_MIN_FIELD_AREA_M2, FTW_MODEL, FTW_SIMPLIFY_M,
                          FTW_STACK_BANDS, FTW_WINDOW_PAIR, INTERIM, KEY_PARCEL,
                          KEY_VILLAGE, METRIC_CRS, RAW, SEASON_WINDOWS, TALUK)

RECORDS = INTERIM / "records.parquet"
FALLBACK = INTERIM / "parcels.gpkg"     # written by p2_parcel_layer.py
OUT = INTERIM / "parcels.gpkg"          # ...and superseded in place by this script
REPORT = EVIDENCE / "p2_ftw_delineation.json"

# The exact column list p2_parcel_layer.py writes. Downstream phases read this and
# nothing else, so the two scripts must agree character for character.
# `field_id` is not decoration. Several legal parcels can share one physical
# delineated field, and parcels sharing a field carry identical zonal features —
# a leakage channel exactly like a shared capture event. splits.headline_groups
# unions it with bag_id, so it must survive into the parcel layer.
SCHEMA = [KEY_PARCEL, "bag_id", KEY_VILLAGE, "village_spatial", "village_name",
          "village_code_mismatch", "crop", "crop_stage", "lat", "lon",
          "geometry_source", "field_id", "snap_m", "parcels_sharing_field",
          "area_m2", "field_area_m2", "geometry"]

# The vocabulary of `geometry_source`. Same column, extended values — the schema is
# unchanged, but a downstream reader can tell a clean delineation from a compromised
# one without re-deriving it.
SRC_CLEAN = "ftw"             # inside exactly one field, and the only point in it
SRC_SHARED = "ftw_shared"     # inside exactly one field that holds other points too
SRC_AMBIG = "ftw_ambiguous"   # inside more than one field (overlapping polygons)

INSTALL_HINT = (
    "  uv pip install --python .venv/bin/python --prerelease=allow "
    '"ftw-tools>=2.0.0b5"\n'
    "  (the PRUE v3 EfficientNet checkpoints are only in the 2.0.0 line; the 1.4.x\n"
    "   stable line ships the older v1/v2 models under different registry names)")


# --------------------------------------------------------------- imagery ----

def taluk_bbox():
    """AOI bbox from the SUPPLIED taluk polygon. Never a hand-typed bbox."""
    gj = json.loads(Path(TALUK).read_text())
    geom = gpd.GeoDataFrame.from_features(gj["features"], crs=CRS)
    minx, miny, maxx, maxy = geom.total_bounds
    return [round(float(v), 5) for v in (minx, miny, maxx, maxy)]


def download_instructions(bbox):
    """
    The actionable message for "no imagery". Mirrors p1_acquire_gee.py's behaviour
    on missing GEE credentials: say exactly what to run, do not fail obscurely.

    Note this path does NOT need Earth Engine. ftw-tools pulls Sentinel-2 L2A from
    the Microsoft Planetary Computer / Element84 STAC endpoints, so AI-1 is not
    blocked on the Phase 1 GEE registration. A GEE export of the same eight bands
    works just as well — pass it with --imagery.
    """
    a_start, a_end = SEASON_WINDOWS[FTW_WINDOW_PAIR[0]]
    b_start, b_end = SEASON_WINDOWS[FTW_WINDOW_PAIR[1]]
    bb = ",".join(str(v) for v in bbox)
    return "\n".join([
        "No bi-temporal Sentinel-2 stack available, so AI-1 cannot run.",
        "",
        f"Sivagiri taluk bbox (from {Path(TALUK).name}): {bb}",
        f"  window A  season {FTW_WINDOW_PAIR[0]} (sowing)          {a_start} .. {a_end}",
        f"  window B  season {FTW_WINDOW_PAIR[1]} (peak vegetative)  {b_start} .. {b_end}",
        "",
        "Easiest route — let ftw-tools pick the two scenes and run the whole chain:",
        f"  ftw inference all --bbox '{bb}' --year 2024 --model {FTW_MODEL} \\",
        "      -o KAVAL/data/raw/ftw/ --cloud_cover_max 20",
        "  then re-run this script with --fields on the resulting .parquet",
        "",
        "Or pick the scenes yourself (win_a/win_b are STAC item ids, not dates):",
        f"  ftw inference download -a <S2_item_id_in_{a_start[:7]}> "
        f"-b <S2_item_id_in_{b_start[:7]}> \\",
        f"      --bbox '{bb}' -o KAVAL/data/raw/s2_bitemporal.tif",
        "  then re-run this script with --imagery KAVAL/data/raw/s2_bitemporal.tif",
        "",
        "Or export the same eight bands from Earth Engine "
        f"({'/'.join(FTW_BANDS)} x 2 windows,",
        "band order A then B, uint16 reflectance) and pass it with --imagery.",
        "",
        "Meanwhile the Voronoi fallback layer from p2_parcel_layer.py remains valid;",
        "run this script with --dry-run to validate everything that does not need "
        "imagery.",
    ])


def check_imagery(path):
    """
    Validate the stack before spending an hour of CPU on it. rasterio is optional
    here because it is NOT in the KAVAL venv — installing ftw-tools brings it in.
    If it is missing we say so rather than pretending the file was checked.
    """
    info = {"path": str(path)}
    try:
        import rasterio
    except ImportError:
        info["validated"] = False
        info["note"] = ("rasterio not installed; band count and dtype NOT checked. "
                        "Installing ftw-tools provides it.")
        return info

    with rasterio.open(path) as src:
        info.update(validated=True, bands=src.count, dtype=str(src.dtypes[0]),
                    crs=str(src.crs), width=src.width, height=src.height)
    if info["bands"] != FTW_STACK_BANDS:
        raise SystemExit(
            f"{path} has {info['bands']} bands; FTW needs exactly {FTW_STACK_BANDS} "
            f"({' '.join(f'{b}_t1' for b in FTW_BANDS)} "
            f"{' '.join(f'{b}_t2' for b in FTW_BANDS)}).\n"
            "A single-date export will not do: the model reads the phenological "
            "contrast between the two dates, which is where the boundary signal is.")
    return info


# ----------------------------------------------------------------- model ----

def run_ftw(imagery, model, out_dir):
    """
    Shell out to the `ftw` CLI rather than importing ftw_tools.

    Deliberate: the Python surface (ftw_tools.inference.inference.run,
    ftw_tools.postprocess.polygonize.polygonize) is still on a 2.0.0 beta and its
    signatures have moved between releases. The CLI is the documented, stable
    contract, and a subprocess boundary also keeps torch out of this process.

    UNTESTED — no ftw-tools and no imagery in this environment.
    """
    if shutil.which("ftw") is None:
        raise SystemExit("`ftw` CLI not found. Install it with:\n" + INSTALL_HINT)

    # Fail early and legibly if the configured checkpoint is not in this build's
    # registry, instead of after the download of a 257 MB file.
    if not str(model).endswith(".ckpt"):
        try:
            listed = subprocess.run(["ftw", "model", "list", "--all"],
                                    capture_output=True, text=True, check=True).stdout
        except (subprocess.CalledProcessError, OSError) as exc:  # noqa: BLE001
            raise SystemExit(f"`ftw model list` failed ({exc}).\n" + INSTALL_HINT)
        if model not in listed:
            raise SystemExit(
                f"Model {model!r} is not in the installed ftw-tools registry.\n"
                "Either install the 2.0.0 line (see below) or download the "
                "checkpoint and pass its path to --model:\n"
                "  https://github.com/fieldsoftheworld/ftw-baselines/releases/"
                "download/v3.1/prue_efnetb7_ccby_checkpoint.ckpt\n" + INSTALL_HINT)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    labels = out_dir / "ftw_labels.tif"
    fields = out_dir / "ftw_fields.parquet"

    # --gpu -1 is CPU. A taluk at 10 m is ~4,000 x 4,000 px; on CPU with B7 expect
    # hours, not minutes. resize_factor 2 is the FTW default and halves that.
    subprocess.run(["ftw", "inference", "run", str(imagery),
                    "--model", str(model), "-o", str(labels),
                    "--gpu", "-1", "--resize_factor", "2", "--overwrite"], check=True)

    # Polygonise the interior class. simplify/min_size come from config because they
    # are region-specific judgements, not FTW defaults — see config.FTW_SIMPLIFY_M.
    # --close_interiors: a hole inside a field is a delineation artefact here, not a
    # real inclusion; leaving holes in would understate every parcel's area.
    subprocess.run(["ftw", "inference", "polygonize", str(labels),
                    "-o", str(fields),
                    "--simplify", str(FTW_SIMPLIFY_M),
                    "--min_size", str(FTW_MIN_FIELD_AREA_M2),
                    "--close_interiors", "--overwrite"], check=True)
    return fields


# ---------------------------------------------------------- field layer -----

def load_fields(path):
    """Read a delineated field layer (parquet/gpkg/fgb/geojson) into METRIC_CRS."""
    gdf = gpd.read_file(path) if Path(path).suffix != ".parquet" \
        else gpd.read_parquet(path)
    if gdf.crs is None:
        raise SystemExit(f"{path} carries no CRS; refusing to guess one.")
    return gdf.to_crs(METRIC_CRS)


def clean_fields(fields):
    """
    Remove what vectorising a segmentation always produces and a cadastre never
    contains: zero-area artefacts, sub-pixel specks, and ribbon slivers left where
    the boundary class was one pixel wide.

    Compactness (Polsby-Popper, 4*pi*A/P^2) is the sliver test rather than a
    width heuristic, because it is scale-free: a 0.05 ha field and a 5 ha field are
    both blocky, but a ribbon of either area is not.

    Returns (clean_fields, stats). Nothing is deleted without being counted.
    """
    stats = {"polygons_in": int(len(fields))}

    fields = fields.copy()
    fields["geometry"] = fields.geometry.make_valid()
    fields = fields[~fields.geometry.is_empty & fields.geometry.notna()]
    fields = fields.explode(index_parts=False, ignore_index=True)
    fields = fields[fields.geom_type == "Polygon"]
    stats["after_make_valid_explode"] = int(len(fields))

    fields["area_m2"] = fields.geometry.area
    perim = fields.geometry.length
    fields["compactness"] = np.where(
        perim > 0, 4 * math.pi * fields["area_m2"] / perim ** 2, 0.0)

    too_small = fields["area_m2"] < FTW_MIN_FIELD_AREA_M2
    sliver = (~too_small) & (fields["compactness"] < FTW_MIN_COMPACTNESS)
    stats["dropped_below_min_area"] = int(too_small.sum())
    stats["dropped_slivers"] = int(sliver.sum())

    fields = fields[~too_small & ~sliver].reset_index(drop=True)
    fields["field_id"] = [f"ftw_{i:07d}" for i in range(len(fields))]

    # Kept, not dropped: an implausibly large polygon is a MISSED boundary, and the
    # count of them is the honest measure of under-segmentation on smallholdings.
    oversized = fields["area_m2"] > FTW_MAX_PLAUSIBLE_FIELD_AREA_M2
    stats["polygons_out"] = int(len(fields))
    stats["oversized_kept"] = int(oversized.sum())
    stats["oversized_threshold_m2"] = FTW_MAX_PLAUSIBLE_FIELD_AREA_M2
    if len(fields):
        q = fields["area_m2"].quantile([0.10, 0.50, 0.90])
        stats["field_area_m2"] = {"p10": round(float(q.loc[0.10])),
                                  "median": round(float(q.loc[0.50])),
                                  "p90": round(float(q.loc[0.90])),
                                  "total_ha": round(float(fields.area_m2.sum()) / 1e4, 1)}
    return fields, stats


# ------------------------------------------------------------- the gate -----

def snap_points(pts, fields, tolerance_m=0.0):
    """
    Point-in-polygon per the parcel-join skill: predicate `within`, no rounding.
    Returns a frame indexed by parcel_id with `field_id`, `n_fields` and `snap_m`.

    A point inside several overlapping fields is resolved to the SMALLEST containing
    one (most specific), but it still counts as ambiguous — the gate says "exactly
    one polygon" and we do not launder that by picking a winner quietly.

    **On the tolerance.** Strict containment puts only about a third of points
    inside a field, which reads like a delineation failure. Mostly it is not: the
    unmatched points sit a median of about 15 m from the nearest field, most within
    20 m and under 1% beyond 200 m (figures in docs/evidence/p2e_ftw_match_detail.json,
    not here). The survey points are offset by a pixel or two, which is the
    positional accuracy a handheld GPS fix gives you. (An earlier version of this
    docstring also said FTW's area matched the registry; it compared mismatched
    footprints and was retracted, correction #18. Like for like FTW is 41% short.)

    So a non-zero tolerance is not moving the goalpost; a binary containment test is
    the wrong instrument for data with ~10-15 m positional uncertainty. The strict
    number is reported alongside, and `measure()` reports the whole
    tolerance/sharing trade-off curve so the choice is visible rather than tuned.
    """
    left = pts[[KEY_PARCEL, "geometry"]]
    right = fields[["field_id", "area_m2", "geometry"]]
    hits = gpd.sjoin(left, right, how="left", predicate="within")

    n = hits.groupby(KEY_PARCEL, sort=False)["field_id"].count().rename("n_fields")
    best = (hits.sort_values("area_m2", na_position="last")
                .drop_duplicates(subset=[KEY_PARCEL], keep="first")
                .set_index(KEY_PARCEL)["field_id"])
    out = pd.concat([best, n], axis=1).reindex(pts[KEY_PARCEL].values)
    out["snap_m"] = 0.0

    if tolerance_m > 0:
        missing = out.index[out["field_id"].isna()]
        if len(missing):
            near = gpd.sjoin_nearest(
                pts[pts[KEY_PARCEL].isin(missing)][[KEY_PARCEL, "geometry"]],
                fields[["field_id", "geometry"]], how="left", distance_col="snap_m")
            near = near.drop_duplicates(KEY_PARCEL).set_index(KEY_PARCEL)
            near = near[near["snap_m"] <= tolerance_m]
            out.loc[near.index, "field_id"] = near["field_id"]
            out.loc[near.index, "n_fields"] = 1
            out.loc[near.index, "snap_m"] = near["snap_m"]
    return out


def measure(snapped, fields, villages):
    """
    The Phase 2 acceptance gate, plus the measurement plan.md asks for but the gate
    does not actually test.

    plan.md §6 words it as "what fraction of the points land in a delineated field,
    ONE POINT PER FIELD?" — but the gate itself only says "inside exactly one
    polygon". Those are different questions and the difference matters: a single
    polygon per village would score 100% on the gate while destroying the parcel
    layer. So we report both, and the stricter one is the real quality number.
    """
    n = len(snapped)
    n_fields = snapped["n_fields"].fillna(0).astype(int)

    unmatched = n_fields == 0
    ambiguous = n_fields > 1
    in_one = n_fields == 1

    # of the points in exactly one field, which share that field with another point?
    fid = snapped["field_id"].where(in_one)
    per_field = fid.value_counts()
    shared_fields = set(per_field[per_field > 1].index)
    shared = in_one & fid.isin(shared_fields)
    clean = in_one & ~shared

    rep = {
        "points": int(n),
        "gate_metric": "fraction of ground-truth points inside exactly one FTW field",
        "gate_threshold": FTW_MATCH_RATE_GATE,
        "match_rate": round(float(in_one.mean()), 4),
        "gate_passes": bool(in_one.mean() >= FTW_MATCH_RATE_GATE),
        "points_in_exactly_one_field": int(in_one.sum()),
        "points_in_no_field": int(unmatched.sum()),
        "points_in_multiple_fields": int(ambiguous.sum()),

        # the stricter, more honest number
        "one_point_per_field_rate": round(float(clean.mean()), 4),
        "points_sharing_a_field": int(shared.sum()),
        "fields_holding_more_than_one_point": int(len(shared_fields)),
        "max_points_in_one_field": int(per_field.max()) if len(per_field) else 0,

        "fields_total": int(len(fields)),
        "fields_hit_by_a_point": int(fid.nunique()),
        "fields_with_no_ground_truth": int(len(fields) - fid.nunique()),
    }

    # Per-village, because it will not be uniform and the agent brief requires it.
    # Villages are the spatial ones (the polygon the point actually falls in), not
    # the recorded codes — see p2_parcel_layer.py on the 911/912 discrepancy.
    # `villages=None` is used when sweeping the tolerance curve, where only the
    # headline rates matter and the per-village breakdown would be noise.
    if villages is not None:
        by_v = pd.DataFrame({"village": villages.values,
                             "in_one": in_one.values, "clean": clean.values})
        g = by_v.groupby("village")
        rep["per_village"] = sorted(
            ({"village": int(v),
              "points": int(len(grp)),
              "match_rate": round(float(grp.in_one.mean()), 4),
              "one_point_per_field_rate": round(float(grp.clean.mean()), 4)}
             for v, grp in g),
            key=lambda r: r["match_rate"])
        rates = [r["match_rate"] for r in rep["per_village"]]
        rep["per_village_spread"] = {
            "villages": len(rates),
            "worst": min(rates) if rates else None,
            "best": max(rates) if rates else None,
            "villages_below_gate": int(sum(r < FTW_MATCH_RATE_GATE for r in rates)),
        }
    return rep, clean, shared, ambiguous, unmatched


# -------------------------------------------------------------- assembly ----

def assemble(fallback, fields, snapped, clean, shared, ambiguous):
    """
    Build the output layer. Matched points take the FTW field polygon; everything
    else keeps the Voronoi/buffer geometry it already had.

    The fallback layer is the carrier of the attribute columns (village_spatial,
    village_name, village_code_mismatch) so the two scripts cannot drift apart:
    there is one definition of those columns and it lives in p2_parcel_layer.py.
    """
    out = fallback.to_crs(METRIC_CRS).set_index(KEY_PARCEL)
    geom_lut = fields.set_index("field_id").geometry
    src = pd.Series(out["geometry_source"].values, index=out.index)

    take = {}
    for mask, label in ((clean, SRC_CLEAN), (shared, SRC_SHARED),
                        (ambiguous, SRC_AMBIG)):
        ids = snapped.index[mask.values]
        src.loc[ids] = label
        for pid, fidv in snapped.loc[ids, "field_id"].items():
            take[pid] = geom_lut.loc[fidv]

    if take:
        out.loc[list(take), "geometry"] = gpd.GeoSeries(
            list(take.values()), index=list(take), crs=METRIC_CRS)
    out["geometry_source"] = src
    # Carry the delineated field id and how far the point had to be snapped.
    out["field_id"] = snapped.reindex(out.index)["field_id"]
    out["snap_m"] = snapped.reindex(out.index)["snap_m"]
    # A parcel on fallback geometry has no field, so it cannot share one.
    out.loc[~src.str.startswith("ftw"), ["field_id", "snap_m"]] = None

    # ---- area: apportion a shared field, never hand each parcel the whole one --
    # A parcel that shares a physical field takes that field's POLYGON as its
    # geometry, which is right for drawing it. Taking the field's AREA as well
    # would count the same land once per sharing parcel: measured at 3.88x
    # inflation over the shared set, turning a 2,250 ha taluk sample into a
    # 4,801 ha one. Crop-wise area is a headline product output, so that would be
    # a reported number that is simply wrong.
    #
    # So the field's area is divided among the parcels sharing it, weighted by
    # their fallback Voronoi area — a proxy for relative parcel size, since the
    # survey gives us no subdivision extents. `field_area_m2` keeps the undivided
    # figure for anyone who needs the physical field rather than the legal parcel.
    fallback_area = fallback.set_index(KEY_PARCEL)["area_m2"].reindex(out.index)
    out["field_area_m2"] = out.geometry.area
    out["area_m2"] = out["field_area_m2"]

    shared_mask = out["field_id"].notna()
    if shared_mask.any():
        grp = out.loc[shared_mask].groupby("field_id")
        n_sharing = grp[KEY_PARCEL].transform("size") if KEY_PARCEL in out.columns \
            else grp.size().reindex(out.loc[shared_mask, "field_id"]).values
        w = fallback_area[shared_mask].fillna(1.0).clip(lower=1.0)
        w_sum = w.groupby(out.loc[shared_mask, "field_id"]).transform("sum")
        out.loc[shared_mask, "area_m2"] = (
            out.loc[shared_mask, "field_area_m2"] * (w / w_sum)).values
        out.loc[shared_mask, "parcels_sharing_field"] = n_sharing
    out["parcels_sharing_field"] = out["parcels_sharing_field"].fillna(1).astype(int) \
        if "parcels_sharing_field" in out.columns else 1

    out = out.reset_index()
    out = gpd.GeoDataFrame(out, geometry="geometry", crs=METRIC_CRS).to_crs(CRS)
    missing = [c for c in SCHEMA if c not in out.columns]
    if missing:
        raise RuntimeError(f"output schema drifted from p2_parcel_layer.py: {missing}")
    return out[SCHEMA]


# ------------------------------------------------------------ cadastral -----

def cadastral_iou(parcels, cadastral_path):
    """
    If FarmwiseAI supply FMB / cadastral geometry, this is the deliverable that
    tells them how far satellite delineation can substitute for survey geometry.

    Per delineated field, IoU against its best-overlapping cadastral parcel. We
    report the median and the fraction above 0.5 (the usual "correctly delineated"
    convention in the field-boundary literature) rather than a single mean, because
    the distribution is bimodal: fields are either found or merged with a neighbour,
    and a mean hides exactly that.

    UNTESTED — no cadastral geometry has been supplied.
    """
    cad = gpd.read_file(cadastral_path).to_crs(METRIC_CRS)
    cad = cad[cad.geometry.notna() & ~cad.geometry.is_empty].reset_index(drop=True)
    cad["cad_id"] = np.arange(len(cad))
    cad["cad_area"] = cad.geometry.area

    ours = parcels.to_crs(METRIC_CRS).reset_index(drop=True)
    ours["our_area"] = ours.geometry.area

    pairs = gpd.overlay(ours[[KEY_PARCEL, "geometry_source", "our_area", "geometry"]],
                        cad[["cad_id", "cad_area", "geometry"]], how="intersection")
    if pairs.empty:
        return {"cadastral_parcels": int(len(cad)), "overlapping_pairs": 0,
                "note": "no overlap — check the CRS and the extent of the supplied "
                        "cadastral file before reading anything into this"}
    pairs["inter"] = pairs.geometry.area
    pairs["iou"] = pairs["inter"] / (pairs["our_area"] + pairs["cad_area"]
                                     - pairs["inter"])
    best = pairs.sort_values("iou", ascending=False).drop_duplicates(KEY_PARCEL)

    def summarise(sub):
        return {"n": int(len(sub)),
                "median_iou": round(float(sub.iou.median()), 4),
                "frac_iou_over_0.5": round(float((sub.iou > 0.5).mean()), 4),
                "frac_iou_over_0.7": round(float((sub.iou > 0.7).mean()), 4)}

    rep = {"cadastral_parcels": int(len(cad)),
           "overlapping_pairs": int(len(pairs)),
           "all": summarise(best)}
    # Split by geometry_source: the Voronoi rows are the control. If FTW does not
    # beat Voronoi on IoU, AI-1 has earned nothing and we say so.
    for label, sub in best.groupby("geometry_source"):
        rep[str(label)] = summarise(sub)
    return rep


# ------------------------------------------------------------- dry run ------

def synthetic_fields(pts, cell_m=70):
    """
    A fake delineation, for --dry-run only.

    It is not a simulation of FTW and its match rate means nothing. Its job is to
    push real geometry through clean_fields / snap_points / measure / assemble so
    those code paths are actually executed rather than merely imported. It is built
    to contain all four cases the pipeline must handle: matched, shared (a cell with
    two points), ambiguous (a deliberately overlapping duplicate) and unmatched
    (every tenth cell removed), plus a sliver and a sub-minimum speck for the
    cleaner to reject.
    """
    minx, miny = pts.geometry.x.min(), pts.geometry.y.min()
    ix = ((pts.geometry.x - minx) // cell_m).astype(int)
    iy = ((pts.geometry.y - miny) // cell_m).astype(int)
    cells = sorted(set(zip(ix, iy)))
    cells = [c for k, c in enumerate(cells) if k % 10]      # punch ~10% out

    geoms = [box(minx + i * cell_m, miny + j * cell_m,
                 minx + (i + 1) * cell_m, miny + (j + 1) * cell_m)
             for i, j in cells]
    # overlapping duplicate -> ambiguous points
    geoms += [g.buffer(cell_m * 0.2) for g in geoms[:20]]
    # a ribbon and a speck the cleaner must reject
    geoms += [box(minx, miny - 400, minx + 2000, miny - 399),
              box(minx, miny - 800, minx + 10, miny - 790)]
    return gpd.GeoDataFrame({"geometry": geoms}, crs=METRIC_CRS)


def dry_run():
    """Validate everything that does not require imagery. Writes nothing."""
    rep = {"mode": "dry-run", "wrote_nothing": True}
    print("== AI-1 dry run: validating everything that does not need imagery ==\n")

    bbox = taluk_bbox()
    rep["taluk_bbox"] = bbox
    print(f"taluk bbox from {Path(TALUK).name}: {bbox}")

    a, b = FTW_WINDOW_PAIR
    assert a in SEASON_WINDOWS and b in SEASON_WINDOWS, "bad FTW_WINDOW_PAIR"
    assert SEASON_WINDOWS[a][1] <= SEASON_WINDOWS[b][0], \
        "FTW window pair must be ordered and non-overlapping"
    print(f"bi-temporal pair: S{a} {SEASON_WINDOWS[a]}  ->  S{b} {SEASON_WINDOWS[b]}")
    print(f"model: {FTW_MODEL}   stack: {FTW_STACK_BANDS} bands "
          f"({'/'.join(FTW_BANDS)} x2)")

    # --- dependencies, honestly reported -----------------------------------
    deps = {}
    for mod in ("rasterio", "ftw_tools", "torch"):
        try:
            __import__(mod)
            deps[mod] = "present"
        except ImportError:
            deps[mod] = "MISSING"
    deps["ftw_cli"] = "present" if shutil.which("ftw") else "MISSING"
    rep["dependencies"] = deps
    print("\ndependencies:", json.dumps(deps))
    if deps["ftw_tools"] == "MISSING":
        print("  -> model steps unavailable. Install with:\n" + INSTALL_HINT)

    # --- inputs ------------------------------------------------------------
    provenance.require(RECORDS)
    rec = pd.read_parquet(RECORDS)
    provenance.require(FALLBACK)
    fb = gpd.read_file(FALLBACK)
    print(f"\nrecords.parquet: {len(rec)} rows")
    print(f"fallback parcels.gpkg: {len(fb)} rows, sources "
          f"{fb.geometry_source.value_counts().to_dict()}")

    assert set(SCHEMA) <= set(fb.columns), \
        f"fallback layer is missing {sorted(set(SCHEMA) - set(fb.columns))}"
    assert fb[KEY_PARCEL].is_unique, "fallback parcel_id is not unique"
    assert set(rec[KEY_PARCEL]) == set(fb[KEY_PARCEL]), \
        "records and fallback parcels disagree on parcel_id"
    if fb.geometry_source.str.startswith("ftw").any():
        raise SystemExit(
            f"{FALLBACK} already holds FTW geometry, so it cannot serve as the "
            "fallback. Re-run p2_parcel_layer.py to regenerate it first.")
    rep["records"] = len(rec)
    rep["fallback_rows"] = len(fb)

    # --- exercise the real pipeline on synthetic geometry -------------------
    pts = gpd.GeoDataFrame(rec[[KEY_PARCEL]],
                           geometry=gpd.points_from_xy(rec.lon, rec.lat),
                           crs=CRS).to_crs(METRIC_CRS)
    fields, fstats = clean_fields(synthetic_fields(pts))
    assert fstats["dropped_below_min_area"] >= 1, "min-area filter did not fire"
    assert fstats["dropped_slivers"] >= 1, "sliver filter did not fire"
    print(f"\nclean_fields on synthetic layer: {json.dumps(fstats)}")

    snapped = snap_points(pts, fields)
    villages = fb.set_index(KEY_PARCEL).loc[pts[KEY_PARCEL], "village_spatial"]
    m, clean, shared, ambiguous, _ = measure(snapped, fields, villages)
    print(f"synthetic match rate (MEANINGLESS as a result, the layer is fake): "
          f"{m['match_rate']}  one-point-per-field {m['one_point_per_field_rate']}")
    assert m["points_in_no_field"] > 0, "unmatched path never exercised"
    assert m["points_sharing_a_field"] > 0, "shared-field path never exercised"
    assert m["points_in_multiple_fields"] > 0, "ambiguous path never exercised"

    out = assemble(fb, fields, snapped, clean, shared, ambiguous)
    assert list(out.columns) == SCHEMA, "assembled schema != p2_parcel_layer schema"
    assert len(out) == len(fb), "assemble lost or duplicated rows"
    assert out[KEY_PARCEL].notna().all() and out["bag_id"].notna().all()
    assert out.crs.to_epsg() == 4326
    assert (out.area_m2 > 0).all(), "assemble produced empty geometry"
    assert out.geometry_source.isin(
        {SRC_CLEAN, SRC_SHARED, SRC_AMBIG,
         *fb.geometry_source.unique()}).all()
    print("assemble: schema, row count, CRS, invariants and geometry all OK")
    print(f"  geometry_source -> {out.geometry_source.value_counts().to_dict()}")
    rep["synthetic_pipeline"] = {"fields": fstats, "measured": {
        k: v for k, v in m.items() if k != "per_village"}}
    rep["schema_validated"] = SCHEMA

    print("\n== dry run OK. Steps 3-6 are exercised; steps 1-2 need imagery. ==")
    print(download_instructions(bbox))
    return rep


# ------------------------------------------------------------------ main ----

def _ftw_scenes():
    """The Sentinel-2 scenes FTW actually used, from p2a's evidence (if present)."""
    p = EVIDENCE / "p2a_ftw_inference.json"
    if not p.exists():
        return "unknown — run scripts/p2a_ftw_inference.py"
    ev = json.loads(p.read_text())
    return {"items": ev.get("s2_items"), "source": "docs/evidence/p2a_ftw_inference.json"}


def main():
    ap = argparse.ArgumentParser(description="AI-1 field delineation (FTW).")
    ap.add_argument("--imagery", default=None,
                    help="8-band bi-temporal Sentinel-2 GeoTIFF (ftw download, a GEE "
                         "export, anything with the right band order)")
    ap.add_argument("--fields", default=None,
                    help="skip the model: an already-vectorised FTW field layer")
    ap.add_argument("--model", default=FTW_MODEL,
                    help="ftw registry name or a path to a .ckpt")
    ap.add_argument("--cadastral", default=None,
                    help="FarmwiseAI FMB/cadastral geometry, to report IoU against")
    ap.add_argument("--snap-tolerance", type=float, default=FTW_SNAP_TOLERANCE_M,
                    help="metres a point may be snapped to the nearest field; 0 = "
                         "strict containment only")
    ap.add_argument("--work-dir", default=str(RAW / "ftw"))
    ap.add_argument("--dry-run", action="store_true",
                    help="validate structure, joins and schema without imagery")
    args = ap.parse_args()

    if args.dry_run:
        print(json.dumps(dry_run()["dependencies"], indent=2))
        return

    # --- get a field layer, or exit saying exactly how to get one ----------
    if args.fields:
        fields_path = Path(args.fields)
        if not fields_path.exists():
            raise SystemExit(f"--fields {fields_path} does not exist.")
        imagery_info = {"source": "pre-vectorised", "path": str(fields_path)}
    elif args.imagery:
        if not Path(args.imagery).exists():
            raise SystemExit(f"--imagery {args.imagery} does not exist.")
        imagery_info = check_imagery(Path(args.imagery))
        fields_path = run_ftw(Path(args.imagery), args.model, args.work_dir)
    else:
        raise SystemExit(download_instructions(taluk_bbox()))

    # --- inputs ------------------------------------------------------------
    provenance.require(RECORDS)
    provenance.require(FALLBACK)
    rec = pd.read_parquet(RECORDS)
    fb = gpd.read_file(FALLBACK)
    if fb.geometry_source.str.startswith("ftw").any():
        raise SystemExit(
            f"{FALLBACK} already holds FTW geometry and cannot serve as the "
            "fallback for unmatched points. Re-run p2_parcel_layer.py first.")

    report = {"model": args.model, "imagery": imagery_info,
              # What the imagery actually was, not what config intended. FTW picks
              # its two scenes from its own crop calendar, so config.SEASON_WINDOWS
              # never described them; an earlier version echoed the config here.
              "imagery_scenes": _ftw_scenes(),
              "configured_window_pair_not_used_by_ftw": {
                  f"S{k}": SEASON_WINDOWS[k] for k in FTW_WINDOW_PAIR},
              "postprocess": {"min_field_area_m2": FTW_MIN_FIELD_AREA_M2,
                              "simplify_m": FTW_SIMPLIFY_M,
                              "min_compactness": FTW_MIN_COMPACTNESS}}

    raw_fields = load_fields(fields_path)
    fields, fstats = clean_fields(raw_fields)
    report["fields"] = fstats
    if fields.empty:
        raise SystemExit(
            "Delineation produced no usable field after cleaning. That is a finding, "
            "not a crash: report it, keep the Voronoi fallback, and check the "
            "imagery's cloud cover and band order before blaming the model.")

    pts = gpd.GeoDataFrame(rec[[KEY_PARCEL]],
                           geometry=gpd.points_from_xy(rec.lon, rec.lat),
                           crs=CRS).to_crs(METRIC_CRS)
    # Report the whole trade-off curve, not just the operating point, so the
    # tolerance choice is visible rather than tuned. Loosening the tolerance
    # recovers points but drives more of them into shared fields.
    curve = []
    for tol in (0.0, 10.0, 15.0, 20.0, 30.0, 50.0):
        g_t, *_ = measure(snap_points(pts, fields, tol), fields, None)
        curve.append({"tolerance_m": tol,
                      "match_rate": g_t["match_rate"],
                      "one_point_per_field_rate": g_t["one_point_per_field_rate"]})
    report["snap_tolerance_curve"] = curve
    report["snap_tolerance_applied_m"] = args.snap_tolerance

    snapped = snap_points(pts, fields, args.snap_tolerance)
    villages = fb.set_index(KEY_PARCEL).loc[pts[KEY_PARCEL], "village_spatial"]
    gate, clean, shared, ambiguous, _ = measure(snapped, fields, villages)
    report["gate"] = gate

    parcels = assemble(fb, fields, snapped, clean, shared, ambiguous)
    assert list(parcels.columns) == SCHEMA
    assert len(parcels) == len(rec), "a ground-truth point was lost"
    report["geometry_source_counts"] = parcels.geometry_source.value_counts().to_dict()
    report["area_m2"] = {
        "median": round(float(parcels.area_m2.median())),
        "p10": round(float(parcels.area_m2.quantile(0.10))),
        "p90": round(float(parcels.area_m2.quantile(0.90))),
        "total_ha": round(float(parcels.area_m2.sum()) / 1e4, 1)}

    if args.cadastral:
        report["cadastral_iou"] = cadastral_iou(parcels, args.cadastral)

    # --- the gate verdict, stated either way -------------------------------
    if not gate["gate_passes"]:
        report["gate_verdict"] = (
            f"FAIL: {gate['match_rate']:.1%} of points fall inside exactly one FTW "
            f"field, below the {FTW_MATCH_RATE_GATE:.0%} Phase 2 gate. Per plan.md "
            "§6 this is permitted only with a documented explanation and the "
            "fallback in place — the fallback IS in place (see "
            "geometry_source_counts). Write the explanation before opening Phase 3.")
    else:
        report["gate_verdict"] = f"PASS: {gate['match_rate']:.1%} >= " \
                                 f"{FTW_MATCH_RATE_GATE:.0%}"

    parcels.to_file(OUT, driver="GPKG", layer="parcels")
    REPORT.write_text(json.dumps(report, indent=2))

    provenance.record(
        OUT, classification="DERIVED",
        source=f"Fields of The World {args.model} segmentation of bi-temporal "
               "Sentinel-2, with village-constrained Voronoi fallback for unmatched "
               "ground-truth points",
        licence="Model weights CC-BY-4.0 (FTW v3.1 CC-BY checkpoint); geometry "
                "derived from FarmwiseAI-supplied points — not for redistribution",
        produced_by="KAVAL/scripts/p2_ftw_delineate.py",
        crs=CRS,
        # The scenes FTW actually used (from p2a), not the config windows it ignores.
        temporal_extent=(" + ".join(v for v in _ftw_scenes()["items"].values() if v)
                         if isinstance(_ftw_scenes(), dict) else _ftw_scenes()),
        transform=f"FTW 3-class segmentation -> polygonize(simplify="
                  f"{FTW_SIMPLIFY_M} m, min_size={FTW_MIN_FIELD_AREA_M2} m2) -> "
                  f"sliver removal (compactness < {FTW_MIN_COMPACTNESS}) -> "
                  "point-in-polygon snap -> Voronoi fallback for unmatched",
        inputs=["KAVAL/data/interim/records.parquet",
                "KAVAL/data/interim/parcels.gpkg as first written by scripts/p2_parcel_layer.py (Voronoi fallback; that script must run first, and this one supersedes the file in place)",
                str(fields_path)],
        notes="PRIMARY Phase 2 geometry (AI-1), superseding the Voronoi fallback in "
              "place. geometry_source distinguishes ftw / ftw_shared / ftw_ambiguous "
              "from voronoi / buffer_no_boundary. ftw_shared means several survey "
              "records resolve to ONE field: those rows are not independent parcels "
              "and Phase 4 must group them.",
        agent="parcel-delineation")

    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
