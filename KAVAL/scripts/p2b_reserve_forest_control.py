"""
KAVAL / Phase 2b — the reserve-forest negative control.

Four of the 25 supplied polygons are Reserve Forest (`village_co = 'YYY'`), not
revenue villages. They carry no ground truth and no registry rows. An earlier
draft of the proposal wrongly described them as "unsurveyed farmland" to be used
as an inference demo; they are protected forest, which makes them something more
useful — a negative control.

The test: how much of the protected area does satellite field-delineation call
field-like? There is no ground truth inside these polygons, so this script
deliberately does NOT conclude which of the two explanations is right:

  (a) cultivation inside protected forest — encroachment, which a revenue or
      forest department would want to know about, or
  (b) delineation false positives — canopy gaps, clearings and fire lines that
      look like field boundaries to a model trained on annual cropland.

Distinguishing them requires a field visit. That is precisely KAVAL's thesis:
the system's job is to produce a defensible verification worklist, not to assert
a truth it cannot support.

Run:  .venv/bin/python KAVAL/scripts/p2b_reserve_forest_control.py
Out:  data/derived/reserve_forest_control.gpkg, docs/evidence/p2b_reserve_forest.json
"""

import json
import sys
import warnings
from pathlib import Path

import geopandas as gpd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")
from kaval import provenance  # noqa: E402
from kaval.config import CRS, DERIVED, EVIDENCE, METRIC_CRS, VILLAGES  # noqa: E402

FIELDS = Path("KAVAL/data/interim/ftw_run/polygons.parquet")
OUT = DERIVED / "reserve_forest_control.gpkg"
# Below this, an intersection is a sliver on the forest boundary rather than a
# field inside it. One Sentinel-2 pixel is 100 m2; we require five.
MIN_INTERSECTION_M2 = 500


def main():
    provenance.require(VILLAGES)
    fields = gpd.read_parquet(FIELDS).to_crs(METRIC_CRS)
    vil = gpd.read_file(VILLAGES).to_crs(METRIC_CRS)

    # Reserve forests are the polygons whose village code is not numeric.
    rf = vil[~vil["village_co"].astype(str).str.isdigit()].copy()
    rf["rf_area_ha"] = rf.area / 1e4

    inter = gpd.overlay(fields[["geometry"]], rf[["vill_name", "geometry"]],
                        how="intersection", keep_geom_type=True)
    inter["area_m2"] = inter.area
    # Drop boundary slivers before counting anything.
    slivers = int((inter.area_m2 < MIN_INTERSECTION_M2).sum())
    inter = inter[inter.area_m2 >= MIN_INTERSECTION_M2].copy()
    inter["area_ha"] = inter.area_m2 / 1e4

    ev = {
        "reserve_forest_polygons": rf["vill_name"].tolist(),
        "reserve_forest_total_ha": round(float(rf.rf_area_ha.sum()), 1),
        "min_intersection_m2": MIN_INTERSECTION_M2,
        "boundary_slivers_discarded": slivers,
        "field_like_patches": int(len(inter)),
        "field_like_area_ha": round(float(inter.area_ha.sum()), 1),
        "pct_of_protected_area": round(
            100 * float(inter.area_m2.sum()) / float(rf.area.sum()), 2),
        "patch_area_ha": {
            "median": round(float(inter.area_ha.median()), 3),
            "p90": round(float(inter.area_ha.quantile(0.90)), 3),
            "max": round(float(inter.area_ha.max()), 2),
        },
    }

    per = (inter.groupby("vill_name")
           .agg(patches=("area_ha", "size"), field_like_ha=("area_ha", "sum"))
           .join(rf.set_index("vill_name")["rf_area_ha"]))
    per["pct_of_forest"] = (100 * per.field_like_ha / per.rf_area_ha).round(2)
    ev["per_forest"] = per.round(1).reset_index().to_dict("records")

    # A polygon that is mostly field-like is more likely mislabelled in the
    # boundary file than genuinely 37% encroached. Flag it rather than assume.
    suspicious = per[per.pct_of_forest > 20]
    ev["polygons_possibly_mislabelled"] = suspicious.reset_index()["vill_name"].tolist()

    ev["interpretation"] = (
        "NOT a conclusion. There is no ground truth inside these polygons, so this "
        "measures only what the delineation model calls field-like. It is consistent "
        "with encroachment, with delineation false positives on canopy gaps and fire "
        "lines, or with errors in the supplied forest boundaries — and this data "
        "cannot separate them. The value is that it produces a bounded, ranked list "
        "of places worth a field visit.")
    ev["calibration_check"] = (
        "The useful negative-control test is whether the CROP CLASSIFIER, run over "
        "these patches, returns low confidence. That requires satellite embeddings "
        "for geometry outside the 14,611 surveyed parcels, which needs Earth Engine "
        "credentials we do not have. Recorded as not done rather than approximated.")

    inter.to_crs(CRS).to_file(OUT, driver="GPKG", layer="field_like_in_forest")
    (EVIDENCE / "p2b_reserve_forest.json").write_text(json.dumps(ev, indent=2, default=str))
    provenance.record(
        OUT, classification="DERIVED",
        source="Intersection of FTW-delineated fields with the supplied Reserve "
               "Forest polygons",
        licence="Derived from FarmwiseAI-supplied boundaries and Copernicus Sentinel-2",
        produced_by="KAVAL/scripts/p2b_reserve_forest_control.py", crs=CRS,
        transform=f"overlay intersection, slivers below {MIN_INTERSECTION_M2} m2 dropped",
        inputs=["Dataset/Administrative_Boundary/Sivagiri_Villages.geojson",
                "KAVAL/data/interim/ftw_run/polygons.parquet"],
        notes="Negative control. Hypothesis-generating, not a finding of encroachment.",
        agent="parcel-delineation")

    print(json.dumps(ev, indent=2, default=str))


if __name__ == "__main__":
    main()
