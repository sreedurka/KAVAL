"""
KAVAL / Phase 1 — Register every input KAVAL reads.

PROVENANCE.md exists so that FarmwiseAI-supplied resources are distinguishable from
data we sourced ourselves, which the challenge brief requires. It cannot do that
while it holds only DERIVED entries. This registers the SUPPLIED inputs and the
prior-work feature export that every model feature ultimately comes from.

Run:  .venv/bin/python KAVAL/scripts/p1_register_inputs.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kaval import provenance  # noqa: E402
from kaval.config import (DISTRICT, GT_POINTS, PRIOR_FEATURES, TALUK,  # noqa: E402
                          VILLAGES)

SUPPLIED = [
    (GT_POINTS, "Digital Crop Survey ground-truth points for Sivagiri taluk",
     "survey window 6-13 November 2024 (Rabi 2024-25)",
     "14,643 records; crop, stage and geotagged photograph reference per parcel."),
    (VILLAGES, "Village administrative boundaries, Sivagiri taluk", "n/a",
     "25 polygons: 21 revenue villages carrying ground truth, plus 4 Reserve "
     "Forest polygons (village_co='YYY') used as a negative control."),
    (TALUK, "Sivagiri taluk boundary", "n/a", "Defines the AOI for all acquisition."),
    (DISTRICT, "Tenkasi district boundary", "n/a", "Context layer."),
]


def main():
    for path, source, temporal, notes in SUPPLIED:
        provenance.record(
            path, classification="SUPPLIED",
            source=f"FarmwiseAI Campus Product Challenge data package — {source}",
            licence="Provided by FarmwiseAI for this challenge. Not redistributed; "
                    "not published in any repository or demo artefact.",
            produced_by="FarmwiseAI (received as supplied)",
            temporal_extent=temporal, transform="none (as received)",
            notes=notes, agent="data-acquisition")

    # Every GSE band and seasonal index in the project comes from this file, so it
    # cannot sit unregistered while plan.md rule 5 says an unprovenanced file does
    # not exist.
    if PRIOR_FEATURES.exists():
        # Facts below were checked against the CropSight folder itself
        # (06_FEATURE_ACQUISITION/: README.md, gee_seasonal_sentinel_features.js,
        # merge_and_validate_features.py, cropsight_seasonal_s2_s1_2024_buffer30m.csv).
        acq = "CropSight/CropSight_Task3_UPGRADED/06_FEATURE_ACQUISITION/"
        provenance.record(
            PRIOR_FEATURES, classification="ACQUIRED",
            source="Google Earth Engine exports produced by this team's earlier "
                   "CropSight work: GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL (64-d, 10 m, "
                   "2024) from a GSE point export, plus seasonal Sentinel-2 "
                   "(COPERNICUS/S2_SR_HARMONIZED) NDVI and Sentinel-1 "
                   "(COPERNICUS/S1_GRD) VV/VH medians from "
                   "cropsight_seasonal_s2_s1_2024_buffer30m.csv",
            licence="Google Earth Engine terms; Satellite Embedding CC-BY-4.0 "
                    "(Google DeepMind); Copernicus Sentinel data free and open",
            produced_by=(
                "MANUAL Earth Engine Code Editor export (" + acq
                + "gee_seasonal_sentinel_features.js for the seasonal table, plus a "
                "GSE point export whose script and CSV were not retained), merged "
                "one-to-one on observation_id by " + acq
                + "merge_and_validate_features.py"),
            temporal_extent="GSE annual 2024; seasonal S1..S4 = calendar-2024 "
                            "quarters (Jan-Mar, Apr-Jun, Jul-Sep, Oct-Dec) per the "
                            "retained .js, NOT config.SEASON_WINDOWS",
            transform="seasonal bands: reduceRegions mean over a 30 m buffer around "
                      "each survey point (BUFFER_M=30, scale 10 m). GSE: from "
                      "a separate GSE point export (method not recorded, see Notes); "
                      "neither is a zonal "
                      "aggregate over the parcel polygon. Merged on observation_id; "
                      "the 12 seasonal columns match the retained seasonal CSV to "
                      "float round-trip (max abs diff 4e-15)",
            inputs=[acq + "cropsight_seasonal_s2_s1_2024_buffer30m.csv",
                    "GSE point export CSV (not retained)"],
            notes="Accepted exception per plan.md §12 — GEE credentials not held; "
                  "not regenerable in this environment. The GSE sampling geometry "
                  "is not recorded in the folder: its .geo column is an empty "
                  "MultiPoint and embedding L2 norms are 0.993-1.009 (median "
                  "1.000), consistent with per-pixel point samples of unit-length "
                  "embeddings rather than a buffer mean. The 30 m buffer is "
                  "documented only for the seasonal bands. Superseded once "
                  "p1_acquire_gee.py runs against the AI-1 parcel layer; the "
                  "schema is identical so Phase 3 accepts either.",
            agent="data-acquisition")

    print(provenance.PROVENANCE.read_text().count("### "), "entries in PROVENANCE.md")


if __name__ == "__main__":
    main()
