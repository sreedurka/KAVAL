"""
KAVAL / Phase 1 - CHIRPS v2.0 monthly rainfall for the Sivagiri taluk (no GEE, no key).

Reads the monthly global COGs at data.chc.ucsb.edu with a windowed /vsicurl read (a few kB
per month, not the 30 MB global file), for the four SEASON_WINDOWS spanning Rabi 2024-25
(Jun 2024 - May 2025). The window is derived from the supplied taluk polygon, padded by one
0.05 degree cell so every cell touching the polygon is included.

Output: KAVAL/data/raw/chirps_monthly_sivagiri.csv, one row per (cell, month).
Resolution caveat: 0.05 deg is ~5.5 km, about 6 x 5 cells over the whole taluk. Village-level
rainfall would be near-duplicate; use taluk mean or per-cell, not per-parcel.
Parcel keys (parcel_id, image_path, village__1) do not apply to a raster grid; the
downstream zonal join attaches them by cell_id.

Licence: public domain (CC0 waiver by Pete Peterson; GEE catalog page for CHIRPS Daily).
The CHG README carries no licence text; the waiver statement is from the GEE catalog.
Run:  .venv/bin/python KAVAL/scripts/p1_acquire_chirps.py
"""

import json
import sys
from datetime import date
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kaval import provenance  # noqa: E402
from kaval.config import EVIDENCE, RAW, SEASON_WINDOWS, TALUK  # noqa: E402

BASE = "https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_monthly/cogs"
OUT = RAW / "chirps_monthly_sivagiri.csv"
LICENCE = ("Public domain: 'To the extent possible under law, Pete Peterson has waived all "
           "copyright and related or neighboring rights to CHIRPS' (CC0; as stated on the Google "
           "Earth Engine catalog page for UCSB-CHG/CHIRPS/DAILY). Cite Funk et al. 2015, "
           "Scientific Data 2:150066, doi:10.1038/sdata.2015.66.")


def months():
    lo = min(pd.Timestamp(w[0]) for w in SEASON_WINDOWS.values())
    hi = max(pd.Timestamp(w[1]) for w in SEASON_WINDOWS.values())
    return list(pd.period_range(lo, hi, freq="M"))


def main():
    taluk = gpd.read_file(TALUK).to_crs(4326)
    poly = taluk.union_all() if hasattr(taluk, "union_all") else taluk.unary_union
    minx, miny, maxx, maxy = poly.bounds
    pad = 0.05
    rows, failures = [], []
    for p in months():
        url = f"{BASE}/chirps-v2.0.{p.year}.{p.month:02d}.cog"
        try:
            with rasterio.open(f"/vsicurl/{url}") as ds:
                win = from_bounds(minx - pad, miny - pad, maxx + pad, maxy + pad,
                                  transform=ds.transform).round_offsets().round_lengths()
                a = ds.read(1, window=win, masked=True)
                m = np.ma.getmaskarray(a)
                tr = ds.window_transform(win)
            for r in range(a.shape[0]):
                for c in range(a.shape[1]):
                    x, y = tr * (c + 0.5, r + 0.5)
                    cell = box(x - 0.025, y - 0.025, x + 0.025, y + 0.025)
                    rows.append(dict(cell_id=f"{x:.3f}_{y:.3f}", lon=round(x, 4), lat=round(y, 4),
                                     month=str(p), precip_mm=None if m[r, c] else float(a[r, c]),
                                     intersects_taluk=bool(cell.intersects(poly)),
                                     source_url=url))
        except Exception as exc:                                   # noqa: BLE001
            failures.append({"url": url, "error": str(exc)})
            print("FAIL", url, exc)
    if not rows:
        sys.exit("no CHIRPS data obtained")
    df = pd.DataFrame(rows)
    df.to_csv(OUT, index=False)
    print(f"{len(df)} rows, {df.cell_id.nunique()} cells, {df.month.nunique()} months")

    provenance.record(
        OUT, classification="ACQUIRED", agent="data-acquisition",
        source=f"{BASE}/chirps-v2.0.YYYY.MM.cog (UCSB Climate Hazards Center), windowed read",
        licence=LICENCE, produced_by="KAVAL/scripts/p1_acquire_chirps.py",
        spatial_extent="Sivagiri taluk polygon bbox + one 0.05 deg cell pad (from supplied Taluk_boundary.geojson)",
        temporal_extent=f"{months()[0]} .. {months()[-1]} (monthly totals, mm)",
        transform="windowed read of monthly COGs; cell centres tabulated; no resampling",
        notes="0.05 deg (~5.5 km) resolution; ~6x5 cells across the taluk. precip_mm is the monthly total.")

    sub = df[df.intersects_taluk]
    ev = {"date": date.today().isoformat(), "rows": len(df), "cells": int(df.cell_id.nunique()),
          "cells_intersecting_taluk": int(sub.cell_id.nunique()), "failures": failures,
          "months": sorted(df.month.unique()),
          "taluk_mean_mm_by_month": {m: round(float(v), 1)
                                     for m, v in sub.groupby("month").precip_mm.mean().items()},
          "null_cells": int(df.precip_mm.isna().sum())}
    (EVIDENCE / "p1_chirps_acquisition.json").write_text(json.dumps(ev, indent=2))
    print(json.dumps(ev["taluk_mean_mm_by_month"], indent=1))


if __name__ == "__main__":
    main()
