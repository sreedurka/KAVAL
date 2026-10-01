---
name: parcel-join
description: Rules for linking ground-truth points, parcel polygons, survey numbers, capture-event bags and administrative boundaries in KAVAL. Load before any spatial join, point-in-polygon operation, parcel aggregation, or building the feature store. Triggers: "spatial join", "point in polygon", "geopandas", "sjoin", "parcel_id", "link", "aggregate", "zonal", "buffer".
---

# Parcel Linkage

## The identifiers

| Key | Form | Meaning |
|---|---|---|
| `parcel_id` | `{village__1}_{survey_n_1}_{sub_divi_1}` | The land unit. 283 records have a blank subdivision — normalise to empty string, do not drop. |
| `bag_id` | `image_path` | The survey capture event. **The leakage group key.** Up to 43 parcels per bag. |
| `village__1` | integer code | Spatial group key; joins to `village_co` in `Sivagiri_Villages.geojson` |
| `observation_id` | `{dist}_{taluk}_{village}_{survey}_{subdiv}_{lat}_{lon}` | Row-level id used by the earlier feature export |

## Join order (do not reorder)

1. Repair coordinates first — 645 records hold two values in one cell (`;`-joined) and
   13 geocode outside the study area. Fix or quarantine before joining.
2. Point → delineated parcel polygon (Phase 2 output), predicate `within`.
3. Unmatched points → buffered-point fallback parcel (30 m), flagged
   `geometry_source='buffer'`. Never silently drop an unmatched point.
4. Parcel → village polygon, to validate `village__1` against `village_co`. Mismatches
   are a finding — log them, don't overwrite.
5. Attach `bag_id` last and assert it survived.

## Aggregation

When several embedding pixels/observations fall in one parcel, aggregate to one vector.
Default: **mean + standard deviation**, both retained. The std carries within-parcel
heterogeneity, which is an audit signal (a mixed or misdelineated parcel has high std).

State the aggregation choice in writing and test at least one alternative
(median, or area-weighted) in Phase 3. Do not assume mean is correct.

## Invariants — assert these, every time

```python
assert df.parcel_id.notna().all()
assert df.bag_id.notna().all()                 # leakage key must survive
assert df.groupby('bag_id').final_crop_name.nunique().max() == 1   # bags are single-label
assert df.crs.to_epsg() == 4326
```

## Never

- Join on rounded latitude/longitude. Use the composite keys.
- Drop unmatched rows silently. Flag and count them.
- Let `bag_id` be lost in a groupby. Carry it as a grouping column, not an aggregate.
- Reproject without recording it (`data-provenance`).
