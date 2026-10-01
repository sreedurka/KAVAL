"""
KAVAL / Phase 2c — FTW cropland area versus the registry, like for like.

Earlier documents said FTW's 13,062 ha was "within 8% of the registry's 12,097 ha".
That compared two different footprints: FTW covers the whole taluk (including 18,385 ha
of Reserve Forest) while the Agrisnet registry covers only the 21 revenue villages.
This script restricts FTW to the same footprint and splits the registry into annual and
perennial crops, so the comparison says what it actually says.

Run:  .venv/bin/python KAVAL/scripts/p2c_ftw_registry_area.py
Out:  docs/evidence/p2c_ftw_registry_area.json
"""
import json, sys, warnings
from pathlib import Path
import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")
from kaval import provenance  # noqa: E402
from kaval.config import EVIDENCE, INTERIM, METRIC_CRS, RAW, VILLAGES  # noqa: E402

FIELDS = INTERIM / "ftw_run" / "polygons.parquet"   # absolute, via config: runs from any cwd
REGISTRY = RAW / "tn_crop_registry.csv"
PERENNIAL = ("Coconut|Banana|Mango|Tamarind|Palmyra|Acid Lime|Lemon|Guava|Sapota|"
             "Cashew|Teak|Neem|Drumstick|Jack|Papaya|Pomegranate")


def main():
    provenance.require(REGISTRY)
    f = gpd.read_parquet(FIELDS).to_crs(METRIC_CRS)
    v = gpd.read_file(VILLAGES).to_crs(METRIC_CRS)
    is_rev = v["village_co"].astype(str).str.isdigit()
    rev, rf = v[is_rev], v[~is_rev]

    ha = lambda g: float(g.area.sum() / 1e4)
    in_rev = gpd.overlay(f[["geometry"]], rev[["geometry"]], how="intersection", keep_geom_type=True)
    in_rf = gpd.overlay(f[["geometry"]], rf[["geometry"]], how="intersection", keep_geom_type=True)

    d = pd.read_csv(REGISTRY)
    r = d[(d.level == "village") & (d.season == "Rabi 2024") & (d.taluk == "Sivagiri")]
    per = r.crop.str.contains(PERENNIAL, case=False, na=False)
    total, annual, perennial = r.area_ha.sum(), r[~per].area_ha.sum(), r[per].area_ha.sum()

    ftw_all, ftw_rev, ftw_rf = ha(f), ha(in_rev), ha(in_rf)
    pct = lambda a, b: round(100 * (a - b) / b, 1)
    ev = {
        "footprints_ha": {"taluk": round(ha(v), 0), "revenue_villages": round(ha(rev), 0),
                          "reserve_forest": round(ha(rf), 0)},
        "ftw_ha": {"whole_layer": round(ftw_all, 0), "inside_21_villages": round(ftw_rev, 0),
                   "inside_reserve_forest": round(ftw_rf, 0)},
        "registry_ha": {"all_crops": round(total, 0), "annual_arable": round(annual, 0),
                        "perennial_tree": round(perennial, 0)},
        "comparison_pct": {
            "whole_layer_vs_registry_MISMATCHED_FOOTPRINT": pct(ftw_all, total),
            "in_villages_vs_all_crops": pct(ftw_rev, total),
            "in_villages_vs_annual_crops": pct(ftw_rev, annual)},
        "correction": (
            "Earlier documents claimed FTW was 'within 8% of the registry'. That "
            "compared FTW's whole-taluk area (13,062 ha, including 736 ha inside Reserve "
            "Forest and all non-village land) against a registry covering only the 21 "
            "revenue villages. Like for like, FTW finds materially LESS than the registry."),
        "reading": (
            "FTW recovers ~59% of registry cropped area inside the villages, and ~75% of "
            "the annual-crop area. It under-delineates even annual arable, so the "
            "'strong on annual, weak on tree crops' story is only part of the shortfall. "
            "Other candidates, none isolable with this data: Rabi-only imagery windows "
            "missing fallow or late-sown fields, cloud-affected scenes, the Sentinel-2 "
            "5.11 processing-baseline mismatch, and small fields below the 500 m2 floor."),
    }
    (EVIDENCE / "p2c_ftw_registry_area.json").write_text(json.dumps(ev, indent=2))
    print(json.dumps(ev, indent=2))


if __name__ == "__main__":
    main()
