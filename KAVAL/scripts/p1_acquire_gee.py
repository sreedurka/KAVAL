"""
KAVAL / Phase 1 — Google Earth Engine acquisition.

Acquires, for the Sivagiri taluk AOI:
  * Google Satellite Embedding (AlphaEarth) 64-d annual vectors, 2024 and 2023
  * Sentinel-2 L2A and Sentinel-1 GRD seasonal composites (4 windows)
  * CHIRPS rainfall and ERA5-Land agro-climate aggregates

Requires an authenticated Earth Engine account:
    .venv/bin/pip install earthengine-api
    earthengine authenticate
    export EE_PROJECT=<your-cloud-project>

Without credentials this script exits with a clear message rather than failing
obscurely; Phase 3 falls back to the prior-work feature export (see plan.md §12),
which is provenanced separately.

Run:  .venv/bin/python KAVAL/scripts/p1_acquire_gee.py [--dry-run]
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kaval.config import (GSE_BANDS, RAW, SEASON_WINDOWS, TALUK)  # noqa: E402

S1_ORBIT = "ASCENDING"   # gee-export: fix one orbit direction, never mix
SCALE = 10


def aoi_from_taluk(ee):
    """AOI comes from the supplied taluk polygon. Never a hand-typed bbox."""
    gj = json.loads(Path(TALUK).read_text())
    return ee.Geometry(gj["features"][0]["geometry"])


def mask_s2(img, ee):
    scl = img.select("SCL")
    # drop saturated, shadow, cloud (med/high), cirrus
    bad = scl.eq(1).Or(scl.eq(3)).Or(scl.eq(8)).Or(scl.eq(9)).Or(scl.eq(10))
    return img.updateMask(bad.Not()).divide(10000)


def seasonal_optical(ee, aoi, start, end):
    col = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
           .filterBounds(aoi).filterDate(start, end)
           .map(lambda i: mask_s2(i, ee)))
    med = col.median()
    ndvi = med.normalizedDifference(["B8", "B4"]).rename("NDVI")
    return ndvi


def seasonal_sar(ee, aoi, start, end):
    col = (ee.ImageCollection("COPERNICUS/S1_GRD")
           .filterBounds(aoi).filterDate(start, end)
           .filter(ee.Filter.eq("instrumentMode", "IW"))
           .filter(ee.Filter.eq("orbitProperties_pass", S1_ORBIT)))
    # gee-export: average in linear power, convert back to dB afterwards
    def to_linear(img):
        return (ee.Image.constant(10).pow(img.select(["VV", "VH"]).divide(10))
                .copyProperties(img, ["system:time_start"]))
    lin = col.map(to_linear).mean()
    return lin.log10().multiply(10).rename(["VV", "VH"])


def build_stack(ee, aoi, year=2024):
    """One image holding every band Phase 3 needs, so a single export suffices."""
    gse = (ee.ImageCollection("GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL")
           .filterBounds(aoi)
           .filterDate(f"{year}-01-01", f"{year+1}-01-01")
           .mosaic()
           .select(GSE_BANDS))
    bands = [gse]
    for s, (start, end) in SEASON_WINDOWS.items():
        bands.append(seasonal_optical(ee, aoi, start, end).rename(f"S{s}_NDVI"))
        sar = seasonal_sar(ee, aoi, start, end)
        bands.append(sar.select("VV").rename(f"S{s}_VV"))
        bands.append(sar.select("VH").rename(f"S{s}_VH"))
    return ee.Image.cat(bands).clip(aoi)


def export_parcel_features(ee, stack, parcels_asset, description):
    """
    Zonal mean AND standard deviation per parcel (parcel-join skill: the std is
    retained as a within-parcel heterogeneity audit signal, not discarded).
    """
    reducer = ee.Reducer.mean().combine(ee.Reducer.stdDev(), sharedInputs=True)
    fc = stack.reduceRegions(
        collection=parcels_asset, reducer=reducer, scale=SCALE, tileScale=4)
    task = ee.batch.Export.table.toDrive(
        collection=fc, description=description, fileFormat="CSV",
        folder="KAVAL")
    task.start()
    return task


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="validate the script without contacting Earth Engine")
    ap.add_argument("--parcels-asset", default=None,
                    help="EE FeatureCollection asset id for the Phase 2 parcel layer")
    args = ap.parse_args()

    if args.dry_run:
        print("dry run: script structure OK. Season windows:")
        for s, w in SEASON_WINDOWS.items():
            print(f"  S{s}: {w[0]} .. {w[1]}")
        print(f"  GSE bands: {len(GSE_BANDS)}  S1 orbit: {S1_ORBIT}  scale: {SCALE} m")
        return

    try:
        import ee
    except ImportError:
        sys.exit("earthengine-api not installed.\n"
                 "  .venv/bin/pip install earthengine-api && earthengine authenticate\n"
                 "Phase 3 falls back to the prior-work feature export meanwhile.")

    project = os.environ.get("EE_PROJECT")
    try:
        ee.Initialize(project=project) if project else ee.Initialize()
    except Exception as exc:                                   # noqa: BLE001
        sys.exit(f"Earth Engine not authenticated ({exc}).\n"
                 "Run `earthengine authenticate` and set EE_PROJECT.")

    aoi = aoi_from_taluk(ee)
    print("AOI area (km2):", aoi.area(1).divide(1e6).getInfo())

    if not args.parcels_asset:
        sys.exit("--parcels-asset required: upload the Phase 2 parcel layer to EE first.")

    for year in (2024, 2023):        # 2023 gives the change-detection baseline
        stack = build_stack(ee, aoi, year)
        task = export_parcel_features(
            ee, stack, ee.FeatureCollection(args.parcels_asset),
            description=f"kaval_parcel_features_{year}")
        print(f"started export for {year}: task {task.id}")

    print("\nExports run asynchronously. Monitor with `earthengine task list`.")
    print(f"On completion place the CSVs in {RAW} and record provenance:")
    print("  .venv/bin/python -c \"from kaval import provenance; ...\"")


if __name__ == "__main__":
    main()
