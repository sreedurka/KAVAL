"""
KAVAL / Phase 2a — AI-1: run the Fields of The World pipeline that produces
`data/interim/ftw_run/{inference_data.tif, inference_output.tif, polygons.parquet}`.

Why this script exists
----------------------
The FTW layer was first produced by a hand-typed `ftw inference all …` command. A
reproducibility audit failed Phase 3 on that manual step. This script is that step,
scripted: same model, same AOI, same scene-selection parameters, and it records what
it actually did (STAC item ids, command, versions, output hashes) so the run can be
checked rather than trusted.

Parameters, and where each was recovered from
---------------------------------------------
  * model  FTW_PRUE_EFNET_B7_CCBY          config.FTW_MODEL; p2_ftw_delineation.json
  * bbox   taluk bbox rounded to 4 dp      README command "77.2704,9.1744,77.5500,9.4198";
                                           it is the only rounding that reproduces the
                                           existing 3093 x 2737 px grid (5 dp gives 2738
                                           rows)
  * year   2024                            README command
  * STAC   Microsoft Planetary Computer    ftw default (-h mspc)
  * cloud  <= 20 %                          ftw default
  * buffer_days 15                          RECOVERED, not recorded. The existing stack's
                                           TIFFTAG_DATETIME is 2024-12-08T05:11:19, i.e.
                                           S2B_MSIL2A_20241208T051119. FTW's crop calendar
                                           puts the late date at 2024-11-23; the ftw
                                           default of +-14 d ends 2024-12-07 and finds NO
                                           scene under 20 % cloud (the command fails).
                                           Any buffer in 15..24 d selects 20241208 (13.9 %);
                                           25 d or more would pick 20241218 (11.9 %).
                                           15 is the smallest value consistent with the
                                           artefact. Early scene for every value in that
                                           range: S2A_MSIL2A_20240507T050651 (7.8 %).
  * inference / polygonize parameters      ftw defaults (resize_factor 2, patch 1024,
                                           padding 64, batch 2; polygonize simplify=True,
                                           min_size 500 m2, no close_interiors) — what
                                           `ftw inference all` passes, no overrides.
  * --gpu -1                                README command (CPU)

NOTE the scene dates. FTW picks its two windows from its own crop calendar, NOT from
config.SEASON_WINDOWS / FTW_WINDOW_PAIR. The real pair is 2024-05-07 and 2024-12-08.
p2_ftw_delineation.json's `window_pair` block echoes the config, not the imagery.

Run
---
    # real run (refuses to overwrite an existing ftw_run without --overwrite)
    .venv/bin/python KAVAL/scripts/p2a_ftw_inference.py --overwrite

    # reproduction check into a scratch dir, compared against the existing layer
    .venv/bin/python KAVAL/scripts/p2a_ftw_inference.py --out-dir /tmp/…/ftw_repro \
        --compare-to KAVAL/data/interim/ftw_run

Out: <out-dir>/{inference_data.tif, inference_output.tif, polygons.parquet,
     ftw_inference_all.log}; metadata JSON to docs/evidence/p2a_ftw_inference.json when
     --out-dir is the real ftw_run path, otherwise to <out-dir>/p2a_ftw_inference.json.
     Provenance is recorded ONLY for the real path.
"""

import argparse
import hashlib
import importlib.metadata as md
import json
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kaval import provenance  # noqa: E402
from kaval.config import (CRS, EVIDENCE, FTW_MODEL, INTERIM, METRIC_CRS,  # noqa: E402
                          ROOT, TALUK)

REAL_OUT = INTERIM / "ftw_run"
OUTPUTS = ("inference_data.tif", "inference_output.tif", "polygons.parquet")

YEAR = 2024
STAC_HOST = "mspc"
CLOUD_COVER_MAX = 20
BUFFER_DAYS = 15
BBOX_DECIMALS = 4

# What the original (manual) run used, recovered from the artefact. The script checks
# the scenes FTW selects against these and says so loudly if upstream has moved.
EXPECTED_ITEMS = {
    "window_a": "S2A_MSIL2A_20240507T050651_R019_T43PGL_20240507T100654",
    "window_b": "S2B_MSIL2A_20241208T051119_R019_T43PGL_20241208T075639",
}


def sha256_full(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def taluk_bbox_str():
    """AOI bbox from the SUPPLIED taluk polygon, rounded as the original run was."""
    g = gpd.read_file(TALUK).to_crs(CRS)
    return ",".join(f"{v:.{BBOX_DECIMALS}f}" for v in g.total_bounds)


def versions():
    out = {"python": platform.python_version()}
    for p in ("ftw-tools", "torch", "odc-stac", "pystac-client", "planetary-computer",
              "rasterio", "segmentation-models-pytorch", "timm", "geopandas"):
        try:
            out[p] = md.version(p)
        except md.PackageNotFoundError:
            out[p] = None
    return out


def ftw_cli():
    exe = Path(sys.executable).with_name("ftw")
    if exe.exists():
        return str(exe)
    found = shutil.which("ftw")
    if not found:
        raise SystemExit("`ftw` CLI not found; install ftw-tools>=2.0.0b5 into the venv.")
    return found


def run_ftw(out_dir, model, bbox, buffer_days, log_path):
    cmd = [ftw_cli(), "inference", "all",
           "-o", str(out_dir), "-m", model, "--year", str(YEAR), "--bbox", bbox,
           "--cloud_cover_max", str(CLOUD_COVER_MAX), "--buffer_days", str(buffer_days),
           "--stac_host", STAC_HOST, "--gpu", "-1", "--overwrite", "--verbose"]
    print("running:", " ".join(cmd), flush=True)
    t0 = time.time()
    with open(log_path, "w") as log:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1)
        for line in proc.stdout:
            log.write(line)
            # progress bars are noisy; echo only the informative lines
            if not line.lstrip().startswith("[") and "%|" not in line:
                sys.stdout.write(line)
        rc = proc.wait()
    if rc != 0:
        raise SystemExit(f"ftw inference all exited {rc}; see {log_path}")
    return cmd, round(time.time() - t0, 1)


def parse_log(log_path):
    text = Path(log_path).read_text(errors="replace")
    sel = re.findall(r"SELECTED:\s+(\S+)\s+from\s+(\S+)", text)
    cal = re.search(r"Crop calendar dates: Start=(\S+) \(day (\d+)\), "
                    r"End=(\S+) \(day (\d+)\)", text)
    cc = re.findall(r"Cloud cover:\s+([\d.]+)% \(lowest among (\d+)", text)
    out = {"selected": [{"id": i, "date": d} for i, d in sel],
           "cloud_cover_pct": [float(c) for c, _ in cc],
           "candidates": [int(n) for _, n in cc],
           "warnings": sorted({ln.strip() for ln in text.splitlines()
                               if "Warning" in ln or "untested" in ln or
                               "Rescaling" in ln})}
    if cal:
        out["crop_calendar"] = {"start": cal.group(1), "start_doy": int(cal.group(2)),
                                "end": cal.group(3), "end_doy": int(cal.group(4))}
    return out


def raster_meta(path):
    import rasterio
    with rasterio.open(path) as s:
        return {"width": s.width, "height": s.height, "count": s.count,
                "dtype": s.dtypes[0], "crs": str(s.crs),
                "transform": list(s.transform)[:6], "tags": s.tags()}


# ------------------------------------------------------------- comparison ----

def compare(new_dir, ref_dir):
    """Repro vs reference: raster equality and polygon agreement."""
    import numpy as np
    import rasterio

    rep = {"reference_dir": str(ref_dir)}
    for name in OUTPUTS:
        rep.setdefault("sha256_identical", {})[name] = (
            sha256_full(Path(new_dir) / name) == sha256_full(Path(ref_dir) / name))

    # inference_data: compare pixel values band by band
    with rasterio.open(Path(new_dir) / "inference_data.tif") as a, \
            rasterio.open(Path(ref_dir) / "inference_data.tif") as b:
        same_grid = (a.shape == b.shape and a.transform == b.transform
                     and a.crs == b.crs and a.count == b.count)
        rep["inference_data"] = {"same_grid": bool(same_grid)}
        if same_grid:
            bands = []
            for i in range(1, a.count + 1):
                x, y = a.read(i).astype("int32"), b.read(i).astype("int32")
                d = np.abs(x - y)
                bands.append({"band": i, "identical_frac": round(float((d == 0).mean()), 6),
                              "max_abs_diff": int(d.max()),
                              "mean_abs_diff": round(float(d.mean()), 4)})
            rep["inference_data"]["bands"] = bands
            rep["inference_data"]["identical"] = all(
                bd["max_abs_diff"] == 0 for bd in bands)

    # inference_output: class agreement
    with rasterio.open(Path(new_dir) / "inference_output.tif") as a, \
            rasterio.open(Path(ref_dir) / "inference_output.tif") as b:
        same_grid = a.shape == b.shape and a.transform == b.transform
        rep["inference_output"] = {"same_grid": bool(same_grid)}
        if same_grid:
            x, y = a.read(1), b.read(1)
            agree = x == y
            classes = sorted(set(np.unique(x)) | set(np.unique(y)))
            confusion = {f"ref{int(c1)}_new{int(c2)}": int(((y == c1) & (x == c2)).sum())
                         for c1 in classes for c2 in classes}
            rep["inference_output"].update(
                identical=bool(agree.all()),
                pixel_agreement=round(float(agree.mean()), 6),
                pixels_differing=int((~agree).sum()),
                pixels_total=int(agree.size),
                confusion_ref_by_new=confusion)

    # polygons
    new = gpd.read_parquet(Path(new_dir) / "polygons.parquet").to_crs(METRIC_CRS)
    ref = gpd.read_parquet(Path(ref_dir) / "polygons.parquet").to_crs(METRIC_CRS)
    new_u, ref_u = new.union_all(), ref.union_all()
    inter = new_u.intersection(ref_u).area
    union = new_u.union(ref_u).area
    rep["polygons"] = {
        "count_new": int(len(new)), "count_ref": int(len(ref)),
        "area_ha_new": round(float(new.area.sum()) / 1e4, 2),
        "area_ha_ref": round(float(ref.area.sum()) / 1e4, 2),
        "union_iou": round(float(inter / union), 6) if union else None,
    }
    # matched-polygon IoU: each reference polygon against its best-overlapping new one
    ref = ref.reset_index(drop=True).assign(rid=lambda d: d.index, ra=lambda d: d.area)
    new = new.reset_index(drop=True).assign(nid=lambda d: d.index, na=lambda d: d.area)
    pairs = gpd.overlay(ref[["rid", "ra", "geometry"]], new[["nid", "na", "geometry"]],
                        how="intersection", keep_geom_type=True)
    if len(pairs):
        pairs["inter"] = pairs.area
        pairs["iou"] = pairs["inter"] / (pairs["ra"] + pairs["na"] - pairs["inter"])
        best = pairs.sort_values("iou", ascending=False).drop_duplicates("rid")
        iou = best.set_index("rid")["iou"].reindex(ref["rid"]).fillna(0.0)
        rep["polygons"]["matched_iou"] = {
            "median": round(float(iou.median()), 6),
            "mean": round(float(iou.mean()), 6),
            "frac_iou_1": round(float((iou > 0.999999).mean()), 6),
            "frac_iou_over_0.9": round(float((iou > 0.9).mean()), 6),
            "frac_iou_over_0.5": round(float((iou > 0.5).mean()), 6),
            "ref_polygons_with_no_overlap": int((iou == 0).sum())}
    return rep


def verdict(cmp, items_match):
    """'reproduces' only if the stack is the same imagery and outputs agree tightly."""
    po = cmp.get("polygons", {})
    io = cmp.get("inference_output", {})
    tol = {"inference_output_pixel_agreement_min": 0.999,
           "polygon_count_rel_diff_max": 0.001,
           "area_rel_diff_max": 0.001, "union_iou_min": 0.999}
    ok = (items_match and io.get("pixel_agreement", 0) >= tol[
        "inference_output_pixel_agreement_min"]
          and abs(po["count_new"] - po["count_ref"]) <= tol[
              "polygon_count_rel_diff_max"] * po["count_ref"]
          and abs(po["area_ha_new"] - po["area_ha_ref"]) <= tol[
              "area_rel_diff_max"] * po["area_ha_ref"]
          and (po.get("union_iou") or 0) >= tol["union_iou_min"])
    identical = all(cmp.get("sha256_identical", {}).values())
    return {"tolerance": tol,
            "result": "reproduces (byte-identical)" if identical else
                      "reproduces (within tolerance)" if ok else "does not reproduce"}


# ------------------------------------------------------------------- main ----

def main():
    ap = argparse.ArgumentParser(description="Run FTW inference for the Sivagiri taluk.")
    ap.add_argument("--out-dir", default=str(REAL_OUT))
    ap.add_argument("--model", default=FTW_MODEL)
    ap.add_argument("--buffer-days", type=int, default=BUFFER_DAYS)
    ap.add_argument("--overwrite", action="store_true",
                    help="required to replace an existing real ftw_run")
    ap.add_argument("--compare-to", default=None,
                    help="reference ftw_run directory to compare the outputs against")
    ap.add_argument("--skip-run", action="store_true",
                    help="do not run ftw; only (re)build metadata/comparison from "
                         "outputs already in --out-dir")
    ap.add_argument("--reproduction", default=None,
                    help="with --skip-run on the real path: the p2a JSON of a scratch "
                         "re-run compared against these outputs. Registers the ORIGINAL "
                         "files (not overwritten by an identical re-run) and carries "
                         "the re-run's scene ids and verdict into evidence/provenance.")
    args = ap.parse_args()
    repro = json.loads(Path(args.reproduction).read_text()) if args.reproduction else None
    if repro and not repro.get("comparison", {}).get("verdict", {}).get(
            "result", "").startswith("reproduces"):
        raise SystemExit("--reproduction JSON does not say the outputs reproduce; "
                         "refusing to register them as script-produced.")

    out_dir = Path(args.out_dir).resolve()
    is_real = out_dir == REAL_OUT.resolve()
    if is_real and not args.skip_run and not args.overwrite and any(
            (out_dir / n).exists() for n in OUTPUTS):
        raise SystemExit(f"{out_dir} already holds FTW outputs; pass --overwrite to "
                         "replace them (downstream parcels.gpkg must then be rebuilt).")
    out_dir.mkdir(parents=True, exist_ok=True)
    evidence = EVIDENCE / "p2a_ftw_inference.json" if is_real \
        else out_dir / "p2a_ftw_inference.json"
    log_path = out_dir / "ftw_inference_all.log"

    bbox = taluk_bbox_str()
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if args.skip_run:
        cmd, secs = None, None
    else:
        cmd, secs = run_ftw(out_dir, args.model, bbox, args.buffer_days, log_path)

    parsed = parse_log(log_path) if log_path.exists() else {}
    sel = [s["id"] for s in parsed.get("selected", [])]
    items = {"window_a": sel[0] if len(sel) > 0 else None,
             "window_b": sel[1] if len(sel) > 1 else None}
    if repro and not sel:
        # The original hand-run left no log; the verified re-run names the scenes.
        items, parsed = repro["s2_items"], repro.get("scene_selection", {})
    items_match = items == EXPECTED_ITEMS

    missing = [n for n in OUTPUTS if not (out_dir / n).exists()]
    if missing:
        raise SystemExit(f"ftw finished but did not write {missing} in {out_dir}")

    polys = gpd.read_parquet(out_dir / "polygons.parquet")
    rep = {
        "script": "KAVAL/scripts/p2a_ftw_inference.py",
        "started_utc": started,
        "runtime_s": secs,
        "out_dir": str(out_dir),
        "is_real_path": is_real,
        "model": args.model,
        "command": cmd,
        "parameters": {"year": YEAR, "bbox": bbox, "bbox_source": f"{Path(TALUK).name} "
                       f"total_bounds rounded to {BBOX_DECIMALS} dp",
                       "stac_host": STAC_HOST, "cloud_cover_max": CLOUD_COVER_MAX,
                       "buffer_days": args.buffer_days, "gpu": -1,
                       "inference_and_polygonize": "ftw defaults (no overrides)"},
        "s2_items": items,
        "s2_items_expected": EXPECTED_ITEMS,
        "s2_items_match_expected": items_match,
        "scene_selection": parsed,
        "versions": versions(),
        "outputs": {n: {"sha256": sha256_full(out_dir / n),
                        "bytes": (out_dir / n).stat().st_size} for n in OUTPUTS},
        "inference_data": raster_meta(out_dir / "inference_data.tif"),
        "inference_output": raster_meta(out_dir / "inference_output.tif"),
        "polygons": {"count": int(len(polys)), "crs": str(polys.crs.to_epsg()),
                     "area_ha": round(float(polys.to_crs(METRIC_CRS).area.sum()) / 1e4,
                                      2)},
    }
    if not items_match:
        rep["WARNING"] = ("FTW selected different Sentinel-2 items than the original "
                          "run; upstream STAC contents or cloud metadata have changed.")

    if repro:
        rep["reproduction"] = {
            "method": "scratch re-run of this script, compared file by file",
            "command": repro.get("command"), "started_utc": repro.get("started_utc"),
            "runtime_s": repro.get("runtime_s"), "s2_items": repro.get("s2_items"),
            "comparison": repro.get("comparison")}
    if args.compare_to:
        cmp = compare(out_dir, Path(args.compare_to).resolve())
        cmp["verdict"] = verdict(cmp, items_match)
        rep["comparison"] = cmp

    evidence.write_text(json.dumps(rep, indent=2, default=str))
    print(json.dumps({k: rep[k] for k in ("s2_items", "s2_items_match_expected",
                                          "polygons")}, indent=2))
    if "comparison" in rep:
        print(json.dumps(rep["comparison"], indent=2, default=str))
    print(f"wrote {evidence}")

    if is_real:
        run_cmd = list(cmd or (repro or {}).get("command") or [])
        if "-o" in run_cmd:   # record the real output path, not a scratch dir
            run_cmd[run_cmd.index("-o") + 1] = str(out_dir.relative_to(ROOT))
        rel_cmd = " ".join(["ftw"] + (run_cmd[1:] if run_cmd else []))
        if repro:
            v = repro["comparison"]["verdict"]["result"]
            rel_cmd += (f" — originally hand-run; this script's re-run {v} "
                        "(docs/evidence/p2a_ftw_inference.json 'reproduction')")
        common = dict(
            licence="Sentinel-2 L2A: Copernicus open licence (free, full, open; "
                    "attribution 'contains modified Copernicus Sentinel data 2024'). "
                    "Model FTW_PRUE_EFNET_B7_CCBY weights CC-BY-4.0.",
            produced_by="KAVAL/scripts/p2a_ftw_inference.py",
            crs=METRIC_CRS, agent="p2a_ftw_inference",
            temporal_extent=f"{items['window_a']} + {items['window_b']}")
        provenance.record(
            out_dir / "inference_data.tif", classification="ACQUIRED",
            source=f"Microsoft Planetary Computer sentinel-2-l2a, items "
                   f"{items['window_a']} and {items['window_b']}, via `{rel_cmd}`",
            transform="odc-stac load of B04,B03,B02,B08 per scene, bilinear, clipped to "
                      "bbox; stacked A then B; baseline>=4 offset removed (-1000, clip 0)",
            inputs=[f"STAC {items['window_a']}", f"STAC {items['window_b']}",
                    str(Path(TALUK).relative_to(ROOT))],
            notes="8-band uint16 bi-temporal stack written by ftw inference all.",
            **common)
        provenance.record(
            out_dir / "inference_output.tif", classification="DERIVED",
            source=f"FTW {args.model} inference on inference_data.tif",
            transform="3-class U-Net argmax (0 bg / 1 field / 2 boundary), resize_factor "
                      "2, patch 1024, padding 64, CPU",
            inputs=["KAVAL/data/interim/ftw_run/inference_data.tif",
                    f"{args.model} checkpoint (ftw-tools registry)"],
            notes="See docs/evidence/p2a_ftw_inference.json.", **common)
        provenance.record(
            out_dir / "polygons.parquet", classification="DERIVED",
            source="ftw polygonize (defaults) of inference_output.tif",
            transform="polygonize field class, simplify=True, min_size=500 m2",
            inputs=["KAVAL/data/interim/ftw_run/inference_output.tif"],
            notes="Raw FTW layer; cleaned by p2_ftw_delineate.py.", **common)


if __name__ == "__main__":
    main()
