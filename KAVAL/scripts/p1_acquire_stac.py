"""
KAVAL / Phase 1 - credential-free imagery acquisition over STAC.

WHY THIS EXISTS. p1_acquire_gee.py needs an authenticated Earth Engine account.
Sentinel-2 L2A, Sentinel-1 and the Copernicus DEM are also published as open
cloud-optimised GeoTIFFs behind public STAC APIs that need no account, so Phase 3
(features) is not blocked on GEE. Only the Google Satellite Embedding remains GEE-only.

Products (all keyed by parcel_id, carrying bag_id and village_code):

  (B) data/raw/seasonal_s1_s2_stac.csv
      Per-parcel zonal means of S{1..4}_{NDVI,VH,VV} over the four
      config.SEASON_WINDOWS. A KEYLESS, SEASONAL-ONLY alternative to the prior GEE
      export, deliberately NOT wired into the feature store: it has the same 12
      seasonal column names but no Google Satellite Embedding bands, so pointing
      p3_feature_store.py --features at it would drop all 64 GSE features. It also
      measures something different (config windows and parcel-polygon zonal means,
      against the GEE export's calendar quarters and 30 m point buffers), and it
      correlates only moderately with those columns. Kept so the seasonal arm can
      be rebuilt without Earth Engine; swapping it in is a Phase 3/4 re-run.

  (P) data/raw/presto_monthly_series.parquet
      Long format, parcel_id x month, 12 calendar months Jun 2024 - May 2025 (Presto's
      pretraining cadence is 30-day steps). RAW units, NOT normalised:
      S2 B2 B3 B4 B5 B6 B7 B8 B8A B11 B12 as reflectance x 10000 (baseline-harmonised),
      S1 VV/VH in dB, static elevation/slope. Missing is NaN plus an explicit
      *_observed flag; nothing is interpolated or gap-filled. Temperature is NOT
      included (ERA5-Land needs a CDS key we do not hold); precipitation comes from the
      CHIRPS file and is not duplicated here.

  (A) optional, --ftw-stack: data/raw/ftw_stack_2024_25.tif, the 8-band uint16 FTW
      bi-temporal stack. Off by default: Phase 2 ran the ftw-tools CLI, which fetches its
      own imagery.

Sources (all anonymous):
  Sentinel-2  Element84 Earth Search  sentinel-2-c1-l2a  (AWS Open Data COGs)
  Sentinel-1  Microsoft Planetary Computer  sentinel-1-rtc  (gamma0 terrain-corrected,
              linear power; a free anonymous SAS token is fetched by planetary-computer)
  DEM         Element84 Earth Search  cop-dem-glo-30

Deliberate choices, all echoed into the evidence JSON:
  * S2 cloud mask from SCL: drop 0 nodata, 1 saturated, 3 shadow, 8/9 cloud, 10 cirrus.
  * Composite = per-pixel median of unmasked observations. A pixel with none stays NaN.
  * Processing-baseline offset: baseline >= 04.00 carries a +1000 DN offset. Every scene is
    harmonised to the baseline-3.0 scale (DN - 1000, clipped at 0) BEFORE compositing, per
    scene, decided from that scene's own s2:processing_baseline. The per-scene baselines
    are recorded so a mixed-baseline series cannot pass unnoticed.
  * S1: ONE orbit direction, ONE relative orbit (verified). Per-window/month mean in
    LINEAR power, converted to dB after. Seasonal zonal means are taken over the dB image
    (as p1_acquire_gee.py does); monthly parcel values likewise.
  * Parcel value = mean over the parcel's pixels. A parcel-month counts as OBSERVED only if
    at least MIN_VALID_FRAC of its pixels hold a valid composite value; else all values
    are NaN.
  * Grid: native Sentinel-2 grid in EPSG:32643 (the AOI lies wholly inside UTM zone 43N,
    72-78E; NOT zone 44 as config.METRIC_CRS says). 10 m bands are not resampled; 20 m
    bands and SCL use nearest-neighbour onto the 10 m grid.

Scene downloads are cached (default .cache/kaval_stac under the
repo root, outside data/) so a dropped connection resumes instead of restarting.

Run:  .venv/bin/python KAVAL/scripts/p1_acquire_stac.py [--dry-run] [--s1-orbit DESCENDING]
"""

import argparse
import hashlib
import json
import os
import sys

# The Copernicus DEM is a public s3:// bucket. GDAL signs S3 requests unless told
# not to, so without this the DEM read fails on any machine that has no AWS
# credentials, which is the whole point of this script. setdefault leaves a
# deliberate AWS configuration alone. Found when the script first ran on a second
# machine; the first must have had anonymous S3 configured outside the repo.
os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kaval.config import (EVIDENCE, FTW_BANDS, FTW_STACK_BANDS, FTW_WINDOW_PAIR,  # noqa: E402
                          INTERIM, KEY_BAG, KEY_PARCEL, KEY_VILLAGE, RAW, ROOT,
                          SEASON_WINDOWS, SEASONAL_BANDS, TALUK)

warnings.filterwarnings("ignore")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "5")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "3")

E84 = "https://earth-search.aws.element84.com/v1"
MSPC = "https://planetarycomputer.microsoft.com/api/stac/v1"
S2_COLLECTION = "sentinel-2-c1-l2a"
S1_COLLECTION = "sentinel-1-rtc"
DEM_COLLECTION = "cop-dem-glo-30"
S1_ORBIT_DEFAULT = "DESCENDING"   # brief asked ASCENDING; none exists over this AOI (see main)
GRID_CRS = "EPSG:32643"
RES = 10
MIN_VALID_FRAC = 0.5              # parcel-month observed iff >= this share of pixels valid
SCL_BAD = (0, 1, 3, 8, 9, 10)

# Presto band order (S2 part) -> Earth Search asset names
PRESTO_S2 = ["B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B11", "B12"]
S2_ASSET = {"B2": "blue", "B3": "green", "B4": "red", "B5": "rededge1", "B6": "rededge2",
            "B7": "rededge3", "B8": "nir", "B8A": "nir08", "B11": "swir16", "B12": "swir22"}
MONTHS = [(2024, m) for m in range(6, 13)] + [(2025, m) for m in range(1, 6)]

OUT_CSV = RAW / "seasonal_s1_s2_stac.csv"
OUT_PARQ = RAW / "presto_monthly_series.parquet"
OUT_FTW = RAW / "ftw_stack_2024_25.tif"
OUT_EVID = EVIDENCE / "p1_stac_acquisition.json"
PARCELS = INTERIM / "parcels.gpkg"
CACHE = ROOT / ".cache" / "kaval_stac"
ME = "KAVAL/scripts/p1_acquire_stac.py"


# ------------------------------------------------------------------ AOI / grid --
def aoi_from_taluk():
    """AOI comes from the supplied taluk polygon. Never a hand-typed bbox."""
    from shapely.geometry import shape
    gj = json.loads(Path(TALUK).read_text())
    return shape(gj["features"][0]["geometry"])


def make_geobox(aoi):
    """10 m GeoBox in EPSG:32643, edges snapped to the S2 tile grid (multiples of 10 m)."""
    from odc.geo.geobox import GeoBox
    from pyproj import Transformer
    from shapely.ops import transform
    tf = Transformer.from_crs("EPSG:4326", GRID_CRS, always_xy=True).transform
    x0, y0, x1, y1 = transform(tf, aoi).bounds
    x0, y0 = np.floor(x0 / RES) * RES, np.floor(y0 / RES) * RES
    x1, y1 = np.ceil(x1 / RES) * RES, np.ceil(y1 / RES) * RES
    return GeoBox.from_bbox((x0, y0, x1, y1), GRID_CRS, resolution=RES)


def _month_range(y, m):
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    return f"{y}-{m:02d}-01T00:00:00Z/{ny}-{nm:02d}-01T00:00:00Z"


def _dt(w):
    a, b = SEASON_WINDOWS[w]
    return f"{a}T00:00:00Z/{b}T23:59:59Z"


def _full_range():
    return f"{SEASON_WINDOWS[1][0]}T00:00:00Z/{SEASON_WINDOWS[4][1]}T23:59:59Z"


# ------------------------------------------------------------------- STAC ------
def search(url, coll, aoi, dt, sign=False):
    from pystac_client import Client
    kw = {}
    if sign:
        import planetary_computer
        kw["modifier"] = planetary_computer.sign_inplace
    for attempt in range(4):
        try:
            return sorted(Client.open(url, **kw).search(
                collections=[coll], intersects=aoi.__geo_interface__, datetime=dt,
                max_items=1000).items(), key=lambda i: i.datetime)
        except Exception:                                            # noqa: BLE001
            if attempt == 3:
                raise
            time.sleep(3 * (attempt + 1))


def retry(fn, tries=3):
    for k in range(tries):
        try:
            return fn()
        except Exception:                                            # noqa: BLE001
            if k == tries - 1:
                raise
            time.sleep(4 * (k + 1))


def _atomic_save(path, arr):
    tmp = path.with_suffix(".tmp.npy")
    np.save(tmp, arr)
    os.replace(tmp, path)


def fetch_s2(item, gb):
    """Download one scene (10 bands + SCL) on the AOI grid; cache as .npy. Idempotent."""
    import odc.stac
    d = CACHE / "s2"
    d.mkdir(parents=True, exist_ok=True)
    f_b, f_s = d / f"{item.id}_bands.npy", d / f"{item.id}_scl.npy"
    if f_b.exists() and f_s.exists():
        return item.id

    def go():
        ds = odc.stac.load([item], bands=[S2_ASSET[b] for b in PRESTO_S2] + ["scl"],
                           geobox=gb, resampling="nearest", chunks={}).compute()
        return ds
    ds = retry(go)
    bands = np.stack([ds[S2_ASSET[b]].values[0] for b in PRESTO_S2]).astype("uint16")
    _atomic_save(f_s, ds["scl"].values[0].astype("uint8"))
    _atomic_save(f_b, bands)
    return item.id


def fetch_s1(item, gb):
    import odc.stac
    d = CACHE / "s1"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{item.id}.npy"
    if f.exists():
        return item.id

    def go():
        # Planetary Computer asset URLs carry a SAS token that EXPIRES. Items are signed
        # once, at search time, but fetched much later: Sentinel-2 alone took 65 minutes
        # here, so by the time Sentinel-1 started every token had lapsed and all 31
        # scenes failed with HTTP 403 across eight retry rounds. Re-signing immediately
        # before each read makes the token's age independent of how long the run has
        # been going. `sign` is idempotent and cheap (it caches per collection).
        import planetary_computer
        fresh = planetary_computer.sign(item)
        return odc.stac.load([fresh], bands=["vv", "vh"], geobox=gb, resampling="nearest",
                             chunks={}).compute()
    ds = retry(go)
    a = np.stack([ds["vv"].values[0], ds["vh"].values[0]]).astype("float32")
    a[(a <= 0) | (a == -32768) | ~np.isfinite(a)] = np.nan   # RTC nodata / non-physical
    _atomic_save(f, a)
    return item.id


def get_scenes(fn, items, gb, label, workers=4, rounds=8):
    """Fetch every scene, tolerating flaky object-store reads: failures are collected and
    retried in later rounds (with a pause) instead of aborting hours of completed work.
    Cached scenes are skipped, so re-running the script also resumes."""
    t0 = time.time()
    todo = list(items)
    for rnd in range(rounds):
        failed = []

        def one(i):
            try:
                fn(i, gb)
                return None
            except Exception as exc:                                  # noqa: BLE001
                return (i, str(exc)[:160])
        with ThreadPoolExecutor(workers) as ex:
            for k, r in enumerate(ex.map(one, todo), 1):
                if r:
                    failed.append(r)
        done = len(items) - len(failed)
        print(f"  {label}: round {rnd+1}: {done}/{len(items)} cached, {len(failed)} failed "
              f"({time.time()-t0:.0f}s)", flush=True)
        if not failed:
            return
        todo = [i for i, _ in failed]
        time.sleep(20 * (rnd + 1))
    sys.exit(f"{label}: {len(todo)} scenes still failing after {rounds} rounds, e.g. {failed[0]}. "
             "Re-run to resume from the cache; check connectivity to the STAC asset hosts.")


# ------------------------------------------------------------- compositing ------
def s2_composite(items, want):
    """Median over cloud-masked, baseline-harmonised scenes. want = list of band names.
    Returns {band: float32 HxW (NaN none)}, valid-obs count HxW, per-scene stats."""
    idx = [PRESTO_S2.index(b) for b in want]
    H, W = np.load(CACHE / "s2" / f"{items[0].id}_scl.npy", mmap_mode="r").shape
    stack = np.full((len(want), len(items), H, W), np.nan, dtype="float32")
    nvalid = np.zeros((H, W), dtype="int16")
    scene = []
    for k, it in enumerate(items):
        scl = np.load(CACHE / "s2" / f"{it.id}_scl.npy")
        bands = np.load(CACHE / "s2" / f"{it.id}_bands.npy", mmap_mode="r")
        bad = np.isin(scl, SCL_BAD)
        base = float(it.properties["s2:processing_baseline"])
        off = 1000.0 if base >= 4.0 else 0.0
        for j, bi in enumerate(idx):
            a = np.clip(np.asarray(bands[bi], dtype="float32") - off, 0, None)
            a[bad] = np.nan
            stack[j, k] = a
        nvalid += (~bad).astype("int16")
        scene.append({"date": it.datetime.strftime("%Y-%m-%d"), "id": it.id,
                      "processing_baseline": base, "offset_removed": off,
                      "tile_eo_cloud_cover_pct": round(float(it.properties["eo:cloud_cover"]), 1),
                      "aoi_masked_pct": round(float(bad.mean() * 100), 2),
                      "aoi_nodata_pct": round(float((scl == 0).mean() * 100), 2),
                      "aoi_cloud_pct": round(float(np.isin(scl, (8, 9, 10)).mean() * 100), 2),
                      "aoi_shadow_pct": round(float((scl == 3).mean() * 100), 2)})
    out = {}
    for j, b in enumerate(want):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            out[b] = np.nanmedian(stack[j], axis=0).astype("float32")
    return out, nvalid, scene


def s1_composite(items):
    """Linear-power mean per pixel, then dB. Returns VV, VH float32 dB and obs count."""
    arrs = np.stack([np.load(CACHE / "s1" / f"{i.id}.npy") for i in items])   # N,2,H,W
    n = np.isfinite(arrs[:, 0]).sum(axis=0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        lin = np.nanmean(arrs, axis=0)
        db = (10 * np.log10(lin)).astype("float32")
    return {"VV": db[0], "VH": db[1]}, n


# ------------------------------------------------------------------ zonal ------
class Zonal:
    """Per-parcel mean over pixels. Parcels sharing an identical polygon (ftw_shared)
    are computed once. Pixel-centre rule; polygons too small to contain a pixel centre
    take the pixel under their representative point (counted, not hidden)."""

    def __init__(self, parcels, transform, shape, crs):
        from rasterio import features
        g = parcels.to_crs(crs)
        wkb = g.geometry.to_wkb()
        codes, uniq = wkb.factorize()
        self.code = codes                                   # parcel -> unique-geom index
        ug = g.assign(_k=codes).drop_duplicates("_k").sort_values("_k").geometry.reset_index(drop=True)
        n = len(ug)
        lab = features.rasterize(zip(ug, np.arange(1, n + 1, dtype="int32")), out_shape=shape,
                                 transform=transform, fill=0, dtype="int32")
        cnt = np.bincount(lab.ravel(), minlength=n + 1)[1:]
        self.rescued = 0
        inv = ~transform
        for u in np.where(cnt == 0)[0]:
            p = ug[u].representative_point()
            c, r = inv * (p.x, p.y)
            r, c = int(r), int(c)
            if 0 <= r < shape[0] and 0 <= c < shape[1] and lab[r, c] == 0:
                lab[r, c] = u + 1
                self.rescued += 1
        self.lab = lab.ravel()
        self.n = n
        self.cnt = np.bincount(self.lab, minlength=n + 1)[1:]
        self.n_parcels = len(parcels)
        self.unique_geoms = n
        self.no_pixels = int((self.cnt == 0).sum())

    def mean(self, arr):
        """Return (mean per parcel, valid fraction per parcel)."""
        v = arr.ravel()
        ok = (self.lab > 0) & np.isfinite(v)
        s = np.bincount(self.lab[ok], weights=v[ok].astype("float64"), minlength=self.n + 1)[1:]
        c = np.bincount(self.lab[ok], minlength=self.n + 1)[1:]
        with np.errstate(invalid="ignore", divide="ignore"):
            m = np.where(c > 0, s / c, np.nan)
            f = np.where(self.cnt > 0, c / np.maximum(self.cnt, 1), 0.0)
        return m[self.code], f[self.code]


# ------------------------------------------------------------------- DEM -------
def dem_static(aoi, gb, zonal, coarse=3):
    """Copernicus DEM 30 m -> elevation and slope per parcel (Presto static inputs)."""
    import odc.stac
    items = search(E84, DEM_COLLECTION, aoi, None)
    gb30 = gb.zoom_out(coarse)     # 30 m grid on the same origin
    ds = retry(lambda: odc.stac.load(items, bands=["data"], geobox=gb30, resampling="bilinear",
                                     chunks={}).compute())
    z = ds["data"].max("time").values.astype("float32") if "time" in ds["data"].dims \
        else ds["data"].values.astype("float32")
    gy, gx = np.gradient(z, 30.0)
    slope = np.degrees(np.arctan(np.hypot(gx, gy))).astype("float32")
    up = lambda a: np.kron(a, np.ones((coarse, coarse), "float32"))[:gb.shape[0], :gb.shape[1]]  # noqa: E731
    z10, s10 = up(z), up(slope)
    if z10.shape != gb.shape:
        pad = ((0, gb.shape[0] - z10.shape[0]), (0, gb.shape[1] - z10.shape[1]))
        z10, s10 = np.pad(z10, pad, mode="edge"), np.pad(s10, pad, mode="edge")
    return zonal.mean(z10)[0], zonal.mean(s10)[0], [i.id for i in items]


# ------------------------------------------------------------------- main ------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="derive the AOI and count STAC items; download nothing")
    ap.add_argument("--s1-orbit", default=S1_ORBIT_DEFAULT, choices=["ASCENDING", "DESCENDING"])
    ap.add_argument("--ftw-stack", action="store_true",
                    help="also write the 8-band FTW bi-temporal uint16 stack")
    args = ap.parse_args()

    aoi = aoi_from_taluk()
    gb = make_geobox(aoi)
    bbox = tuple(round(v, 6) for v in aoi.bounds)
    print(f"AOI from {Path(TALUK).name}: bounds {bbox}; grid {GRID_CRS} @ {RES} m, "
          f"{gb.shape[1]}x{gb.shape[0]} px")

    try:
        s2_all = search(E84, S2_COLLECTION, aoi, _full_range())
        s1_all = search(MSPC, S1_COLLECTION, aoi, _full_range(), sign=True)
    except Exception as exc:                                        # noqa: BLE001
        sys.exit(f"STAC search failed ({exc}).\nCheck network access to {E84} and {MSPC}. "
                 "No credentials are needed for either.")
    want = args.s1_orbit.lower()
    orbits_seen = {}
    for i in s1_all:
        k = f"{i.properties.get('sat:orbit_state')}/rel{i.properties.get('sat:relative_orbit')}"
        orbits_seen[k] = orbits_seen.get(k, 0) + 1
    s1_sel = [i for i in s1_all if i.properties.get("sat:orbit_state") == want]
    rel = {i.properties.get("sat:relative_orbit") for i in s1_sel}
    print(f"S2 scenes {len(s2_all)}; S1 all orbits {orbits_seen}; selected {want}: {len(s1_sel)}")
    if not s1_sel:
        sys.exit(f"No Sentinel-1 {args.s1_orbit} scenes over the AOI. Available: {orbits_seen}. "
                 "Mixing directions is forbidden; re-run with the direction that exists and "
                 "state the substitution in provenance.")
    if len(rel) > 1:
        sys.exit(f"Selected S1 scenes span relative orbits {rel}; refusing to mix geometries.")

    def between(items, dt):
        a, b = dt.split("/")
        a, b = datetime.fromisoformat(a.replace("Z", "+00:00")), datetime.fromisoformat(b.replace("Z", "+00:00"))
        return [i for i in items if a <= i.datetime < b]

    win_dt = {w: _dt(w) for w in SEASON_WINDOWS}
    mon_dt = {(y, m): _month_range(y, m) for y, m in MONTHS}
    for w, dt in win_dt.items():
        print(f"  window {w}: S2 {len(between(s2_all, dt))}  S1 {len(between(s1_sel, dt))}")
    for ym, dt in mon_dt.items():
        print(f"  {ym[0]}-{ym[1]:02d}: S2 {len(between(s2_all, dt))}  S1 {len(between(s1_sel, dt))}")
    if args.dry_run:
        print("dry run: nothing downloaded.")
        return
    if any(not between(s2_all, dt) for dt in win_dt.values()):
        sys.exit("A season window has zero Sentinel-2 scenes; refusing to write a degraded product.")

    import geopandas as gpd
    import pandas as pd
    parcels = gpd.read_file(PARCELS)
    assert parcels[KEY_PARCEL].is_unique
    keys = parcels[[KEY_PARCEL, KEY_BAG, KEY_VILLAGE]].copy()
    tf = gb.transform
    zonal = Zonal(parcels, tf, gb.shape, GRID_CRS)
    print(f"parcels {zonal.n_parcels}, unique polygons {zonal.unique_geoms}, "
          f"rescued-by-representative-point {zonal.rescued}, without pixels {zonal.no_pixels}")

    get_scenes(fetch_s2, s2_all, gb, "S2")
    get_scenes(fetch_s1, s1_sel, gb, "S1")

    ev = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "script": ME,
          "aoi_source": Path(TALUK).name, "aoi_bounds_wgs84": bbox, "grid_crs": GRID_CRS,
          "resolution_m": RES, "grid_shape_hw": list(gb.shape),
          "s2_collection": S2_COLLECTION, "s1_collection": S1_COLLECTION,
          "s1_orbit_requested_by_brief": "ASCENDING", "s1_orbit_used": args.s1_orbit,
          "s1_relative_orbit_used": sorted(rel),
          "s1_orbits_available_over_aoi_2024_06_to_2025_05": orbits_seen,
          "parcels_sha256_used": hashlib.sha256(PARCELS.read_bytes()).hexdigest(),
          "zonal": {"parcels": zonal.n_parcels, "unique_polygons": zonal.unique_geoms,
                    "polygons_rescued_by_representative_point": zonal.rescued,
                    "polygons_without_any_pixel": zonal.no_pixels,
                    "median_px_per_unique_polygon": float(np.median(zonal.cnt)),
                    "pct_polygons_lt_10px": round(float((zonal.cnt < 10).mean() * 100), 1),
                    "s1_mean_taken_over": "dB image (per-window linear-power average -> dB)"},
          "min_valid_frac_for_observed": MIN_VALID_FRAC,
          "s2_baselines_seen": sorted({float(i.properties["s2:processing_baseline"]) for i in s2_all}),
          "windows": {}, "months": {}}
    ev["s2_baseline_step_present"] = len(ev["s2_baselines_seen"]) > 1 and \
        min(ev["s2_baselines_seen"]) < 4.0 <= max(ev["s2_baselines_seen"])

    # ---------------- (B) seasonal windows ----------------
    seas = keys.copy()
    ftw_comp = {}
    for w in SEASON_WINDOWS:
        it2, it1 = between(s2_all, win_dt[w]), between(s1_sel, win_dt[w])
        need = ["B4", "B8"] + (["B3", "B2"] if w in FTW_WINDOW_PAIR else [])
        comp, nv, scene = s2_composite(it2, need)
        if args.ftw_stack and w in FTW_WINDOW_PAIR:
            ftw_comp[w] = comp
        r, d = comp["B8"] / 10000.0, comp["B4"] / 10000.0
        with np.errstate(invalid="ignore", divide="ignore"):
            ndvi = ((r - d) / (r + d)).astype("float32")
        s1c, n1 = s1_composite(it1)
        for nm, arr in (("NDVI", ndvi), ("VH", s1c["VH"]), ("VV", s1c["VV"])):
            seas[f"S{w}_{nm}"] = zonal.mean(arr)[0]
        cc = [s["tile_eo_cloud_cover_pct"] for s in scene]
        ev["windows"][str(w)] = {
            "dates": list(SEASON_WINDOWS[w]), "s2_items_found": len(it2),
            "s2_tile_cloud_cover_pct": {"min": min(cc), "median": float(np.median(cc)), "max": max(cc),
                                        "n_gt_50": int(sum(c > 50 for c in cc))},
            "s2_aoi_masked_pct_per_scene": {"median": float(np.median([s["aoi_masked_pct"] for s in scene])),
                                            "max": max(s["aoi_masked_pct"] for s in scene),
                                            "n_scenes_gt_50": int(sum(s["aoi_masked_pct"] > 50 for s in scene))},
            "s2_scenes": scene,
            "s2_pixels_no_valid_obs_pct": round(float((nv == 0).mean() * 100), 3),
            "s2_pixels_lt3_valid_obs_pct": round(float((nv < 3).mean() * 100), 2),
            "s2_valid_obs_per_pixel": {"p5": float(np.percentile(nv, 5)), "median": float(np.median(nv)),
                                       "max": int(nv.max())},
            "s2_observations_masked_pct": round(float(np.mean([s["aoi_masked_pct"] for s in scene])), 2),
            "s1_items_selected_orbit": len(it1), "s1_pixels_no_obs_pct": round(float((n1 == 0).mean() * 100), 3),
        }
        print(f"window {w}: S2 {len(it2)} scenes, no-valid px {ev['windows'][str(w)]['s2_pixels_no_valid_obs_pct']}%",
              flush=True)
    assert [c for c in seas.columns if c.startswith("S")] == \
        [c for c in SEASONAL_BANDS], "column schema drifted from config.SEASONAL_BANDS"
    seas["px_count"] = zonal.cnt[zonal.code]
    seas.to_csv(OUT_CSV, index=False)
    ev["seasonal_csv"] = {"nan_counts": {c: int(seas[c].isna().sum()) for c in SEASONAL_BANDS},
                          "column_means": {c: round(float(seas[c].mean()), 4) for c in SEASONAL_BANDS},
                          "keys_preserved": [KEY_PARCEL, KEY_BAG, KEY_VILLAGE]}

    # ---------------- (A) optional FTW stack ----------------
    if args.ftw_stack:
        import rasterio
        t1, t2 = FTW_WINDOW_PAIR
        bmap = {"B04": "B4", "B03": "B3", "B02": "B2", "B08": "B8"}
        names = [f"{b}_t1" for b in FTW_BANDS] + [f"{b}_t2" for b in FTW_BANDS]
        assert len(names) == FTW_STACK_BANDS
        H, W = gb.shape
        ftw = np.zeros((FTW_STACK_BANDS, H, W), "uint16")
        for k, (win, b) in enumerate([(t1, b) for b in FTW_BANDS] + [(t2, b) for b in FTW_BANDS]):
            a = ftw_comp[win][bmap[b]]
            ftw[k] = np.where(np.isfinite(a), np.clip(np.rint(a), 0, 65535), 0).astype("uint16")
        with rasterio.open(OUT_FTW, "w", driver="GTiff", dtype="uint16", count=8, height=H, width=W,
                           crs=GRID_CRS, transform=tf, nodata=0, compress="deflate", predictor=2,
                           tiled=True, blockxsize=256, blockysize=256) as dst:
            dst.write(ftw)
            dst.descriptions = tuple(names)
        ev["ftw_stack"] = {"band_order": names, "dtype": "uint16", "crs": GRID_CRS,
                           "pct_pixels_any_band_zero": round(float((ftw == 0).any(axis=0).mean() * 100), 3)}

    # ---------------- (P) monthly Presto series ----------------
    elev, slope, dem_ids = dem_static(aoi, gb, zonal)
    frames = []
    for mi, (y, m) in enumerate(MONTHS):
        it2, it1 = between(s2_all, mon_dt[(y, m)]), between(s1_sel, mon_dt[(y, m)])
        df = keys.copy()
        df["month"] = f"{y}-{m:02d}"
        df["month_idx"] = mi
        df["calendar_month0"] = m - 1                    # Presto convention: 0 = January
        df["s2_n_scenes"], df["s1_n_scenes"] = len(it2), len(it1)
        if it2:
            comp, nv, scene = s2_composite(it2, PRESTO_S2)
            fr = None
            for b in PRESTO_S2:
                mean, frac = zonal.mean(comp[b])
                fr = frac if fr is None else fr
                df[b] = mean
            df["s2_valid_frac"] = fr
        else:
            scene, nv = [], None
            for b in PRESTO_S2:
                df[b] = np.nan
            df["s2_valid_frac"] = 0.0
        obs2 = (df["s2_valid_frac"] >= MIN_VALID_FRAC).to_numpy()
        for b in PRESTO_S2:
            df.loc[~obs2, b] = np.nan
        df["s2_observed"] = obs2
        if it1:
            s1c, n1 = s1_composite(it1)
            vv, f1 = zonal.mean(s1c["VV"])
            vh, _ = zonal.mean(s1c["VH"])
            df["VV"], df["VH"], df["s1_valid_frac"] = vv, vh, f1
        else:
            df["VV"], df["VH"], df["s1_valid_frac"] = np.nan, np.nan, 0.0
        obs1 = (df["s1_valid_frac"] >= MIN_VALID_FRAC).to_numpy()
        df.loc[~obs1, ["VV", "VH"]] = np.nan
        df["s1_observed"] = obs1
        df["elevation_m"], df["slope_deg"] = elev, slope
        frames.append(df)
        ev["months"][f"{y}-{m:02d}"] = {
            "s2_items": len(it2), "s1_items": len(it1),
            "s2_scene_dates": [s["date"] for s in scene],
            "s2_scene_baselines": sorted({s["processing_baseline"] for s in scene}),
            "s2_scene_aoi_masked_pct": [s["aoi_masked_pct"] for s in scene],
            "s2_pixels_no_valid_obs_pct": None if nv is None else round(float((nv == 0).mean() * 100), 2),
            "parcels_s2_observed": int(obs2.sum()), "parcels_s2_observed_pct": round(float(obs2.mean() * 100), 2),
            "parcels_s1_observed": int(obs1.sum()), "parcels_s1_observed_pct": round(float(obs1.mean() * 100), 2),
            "parcels_s2_median_valid_frac": round(float(np.median(df["s2_valid_frac"])), 3)}
        print(f"month {y}-{m:02d}: S2 {len(it2)} scenes -> {obs2.mean()*100:.1f}% parcels observed; "
              f"S1 {len(it1)} scenes -> {obs1.mean()*100:.1f}%", flush=True)
    out = pd.concat(frames, ignore_index=True)
    out.to_parquet(OUT_PARQ, index=False)
    ev["monthly_parquet"] = {"rows": len(out), "parcels": int(out[KEY_PARCEL].nunique()), "months": 12,
                             "columns": list(out.columns), "units": {
                                 "B2..B12": "reflectance x 10000, baseline-3.0 scale, NOT normalised",
                                 "VV/VH": "dB", "elevation_m": "m (Copernicus DEM GLO-30)",
                                 "slope_deg": "degrees from 30 m DEM"},
                             "temperature_2m": "NOT INCLUDED (ERA5-Land requires a CDS key)",
                             "precipitation": "NOT INCLUDED (see data/raw/chirps_monthly_sivagiri.csv)",
                             "dem_items": dem_ids,
                             "elevation_range_m": [round(float(np.nanmin(elev)), 1), round(float(np.nanmax(elev)), 1)],
                             "slope_median_deg": round(float(np.nanmedian(slope)), 2)}
    OUT_EVID.write_text(json.dumps(ev, indent=2))
    print("wrote", OUT_CSV, OUT_PARQ, OUT_EVID, sep="\n  ")
    record_provenance(args, ev, dem_ids)


def record_provenance(args, ev, dem_ids):
    from kaval import provenance
    span = f"{SEASON_WINDOWS[1][0]} .. {SEASON_WINDOWS[4][1]}"
    s2 = ("Element84 Earth Search STAC (anonymous), collection `sentinel-2-c1-l2a`, Sentinel-2 "
          "L2A Collection 1, tile 43PGL, AWS Open Data COGs")
    s1 = ("Microsoft Planetary Computer STAC, collection `sentinel-1-rtc` (radiometrically "
          "terrain-corrected gamma0, derived from Sentinel-1 GRD), anonymous SAS token")
    lic = ("Copernicus Sentinel data are free, full and open (Sentinel Data Legal Notice, "
           "https://sentinel.esa.int/documents/247904/690755/Sentinel_Data_Legal_Notice). "
           "Attribution: 'Contains modified Copernicus Sentinel data 2024-2025'. "
           "S1 RTC collection licence CC-BY-4.0 (Microsoft). ")
    dem_lic = ("Copernicus DEM GLO-30: 'Produced using Copernicus WorldDEM-30 (c) DLR e.V. "
               "2010-2014 and (c) Airbus Defence and Space GmbH 2014-2018 provided under "
               "COPERNICUS by the European Union and ESA; all rights reserved'. Free for use with "
               "this attribution.")
    common = dict(classification="DERIVED", produced_by=ME, agent="data-acquisition",
                  inputs=[str(PARCELS.relative_to(ROOT)), str(Path(TALUK).relative_to(ROOT))],
                  crs="EPSG:32643 grid for compositing; table is keyed by parcel_id (parcel layer EPSG:4326)")
    orbit_note = (f"S1 orbit: {args.s1_orbit}, relative orbit {ev['s1_relative_orbit_used']}. The brief "
                  "asked for ASCENDING; no ascending pass exists over the AOI in the June 2024-May 2025 "
                  f"record (seen: {ev['s1_orbits_available_over_aoi_2024_06_to_2025_05']}). One direction "
                  "only, never mixed. Backscatter is RTC gamma0, not GEE S1_GRD sigma0: expect a small "
                  "systematic offset versus the prior CropSight export.")
    provenance.record(OUT_CSV, source=f"{s2}; {s1}", licence=lic,
                      temporal_extent=f"{span} (4 seasonal windows, config.SEASON_WINDOWS)",
                      transform=("S2: SCL mask (0,1,3,8,9,10), per-scene baseline harmonisation "
                                 "(DN-1000, clip 0), per-window per-pixel median, NDVI from median B8/B4. "
                                 "S1: per-window linear-power mean then dB. Zonal mean over parcel "
                                 "polygons (pixel-centre rule)."),
                      notes=orbit_note + " Schema S{1..4}_{NDVI,VH,VV} matches the prior export; "
                            "extra column px_count. See docs/evidence/p1_stac_acquisition.json.",
                      **common)
    provenance.record(OUT_PARQ, source=f"{s2}; {s1}; DEM: Element84 `{DEM_COLLECTION}` {dem_ids}",
                      licence=lic + dem_lic,
                      temporal_extent="2024-06-01 .. 2025-05-31, 12 calendar months",
                      transform=(f"S2 per-month cloud-masked median, baseline-harmonised, RAW x10000, "
                                 f"parcel mean; observed iff >= {MIN_VALID_FRAC:.0%} pixels valid else NaN; "
                                 "S1 per-month linear mean -> dB; elevation and slope from 30 m DEM. "
                                 "No interpolation. No normalisation (presto_io.build_inputs does that)."),
                      notes=orbit_note + " No temperature (ERA5-Land needs CDS key) and no precipitation "
                            "(see chirps_monthly_sivagiri.csv). L2A surface reflectance, whereas Presto "
                            "pretraining used L1C TOA.", **common)
    if args.ftw_stack and OUT_FTW.exists():
        provenance.record(OUT_FTW, source=s2, licence=lic,
                          temporal_extent=f"windows {FTW_WINDOW_PAIR}: "
                                          f"{SEASON_WINDOWS[FTW_WINDOW_PAIR[0]]}, {SEASON_WINDOWS[FTW_WINDOW_PAIR[1]]}",
                          transform="uint16, NOT normalised; baseline-3.0 harmonised medians", **common)
    print("provenance recorded")


if __name__ == "__main__":
    main()
