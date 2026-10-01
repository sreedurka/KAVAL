---
name: gee-export
description: Google Earth Engine patterns for KAVAL - acquiring Satellite Embedding (AlphaEarth) vectors, Sentinel-1/2 composites and agro-climate data for the Sivagiri AOI, and exporting them without hitting quota. Load before writing any Earth Engine code or export. Triggers: "Earth Engine", "GEE", "ee.", "Satellite Embedding", "AlphaEarth", "Sentinel-1", "Sentinel-2", "export", "zonal statistics", "reduceRegions".
---

# Google Earth Engine for KAVAL

## Datasets

| Purpose | Collection | Notes |
|---|---|---|
| Satellite embeddings (AI-2) | `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL` | 64 bands `A00`–`A63`, 10 m, annual 2017–2025, unit-length vectors |
| Optical | `COPERNICUS/S2_SR_HARMONIZED` | mask with `MSK_CLDPRB` / SCL before compositing |
| SAR | `COPERNICUS/S1_GRD` | VV+VH, IW mode, ASCENDING — fix one orbit direction, do not mix |
| Rainfall | `UCSB-CHG/CHIRPS/DAILY` | |
| Reanalysis | `ECMWF/ERA5_LAND/DAILY_AGGR` | |
| Surface temp | `MODIS/061/MOD11A2` | |

## AOI

Derive from the supplied `Dataset/Administrative_Boundary/Taluk_boundary.geojson`
(Sivagiri). Never hand-type a bounding box — the AOI must match the supplied polygon so
results are comparable to the ground truth.

## Season windows (Rabi 2024-25, Tamil Nadu)

The ground-truth survey ran November 2024. Build four seasonal composites spanning the
crop cycle, labelled `S1`–`S4`, and keep the window definitions in one config file so
every downstream script uses the same ones.

## Export rules

1. **Export to Google Drive as CSV for tabular, GeoTIFF for raster.** Record the task id.
2. **Scale must be explicit.** `scale=10` for GSE and S2. Never rely on the default.
3. **`crs='EPSG:4326'`** everywhere. Mixed CRS is a silent corruption source.
4. **Tile large AOIs.** A taluk at 10 m with 64 bands will exceed memory in one request.
   Split by village polygon and concatenate.
5. **Carry the keys through.** Every exported row must retain `parcel_id`, `image_path`
   (bag id) and `village__1`, or the leakage protocol cannot be applied downstream.
6. **`reduceRegions` with `ee.Reducer.mean().combine(ee.Reducer.stdDev(), sharedInputs=True)`**
   for parcel aggregation — record both, justify the choice in writing.
7. **Set `tileScale`** (4 or 8) when a reduce fails on memory before reducing the AOI.

## Gotchas

- GSE embeddings are unit-length; do **not** re-normalise them, and do not standardise
  them per-feature without saying so — it destroys the geometry the embedding encodes.
- `reduceRegions` silently drops features with no valid pixels. Count input vs output
  features every time and log the difference.
- S1 values are dB. Compositing in dB vs linear gives different answers — pick linear
  for averaging, convert after, and state which.
- Annual GSE for 2024 covers the calendar year, not the crop season. Say so when
  interpreting; pair it with the seasonal S1/S2 features rather than treating it as
  season-specific.

## Every export ends with a `data-provenance` entry. No exceptions.
