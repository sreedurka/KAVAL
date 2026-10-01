"""
KAVAL — single source of truth for paths, keys, thresholds and season windows.

Rule from plan.md §11: thresholds live here and nowhere else. If a number appears
in two files, one of them is wrong.
"""

from pathlib import Path

# ---------------------------------------------------------------- paths -----
ROOT = Path(__file__).resolve().parents[2]          # /home/user/FM_AI
KAVAL = ROOT / "KAVAL"
DATA = KAVAL / "data"
RAW = DATA / "raw"
INTERIM = DATA / "interim"
DERIVED = DATA / "derived"
EVIDENCE = KAVAL / "docs" / "evidence"
MODELS = KAVAL / "models"

# Supplied by FarmwiseAI (SUPPLIED — never redistribute)
GT_POINTS = ROOT / "Dataset" / "Ground Truth Points" / "Ground_truth_Points.csv"
VILLAGES = ROOT / "Dataset" / "Administrative_Boundary" / "Sivagiri_Villages.geojson"
TALUK = ROOT / "Dataset" / "Administrative_Boundary" / "Taluk_boundary.geojson"
DISTRICT = ROOT / "Dataset" / "Administrative_Boundary" / "Tenkasi_Boundary.geojson"

# Prior-work feature export (see plan.md §12) — GSE + seasonal Sentinel for 14,611 parcels
PRIOR_FEATURES = (ROOT / "CropSight" / "CropSight_Task3_UPGRADED" /
                  "06_FEATURE_ACQUISITION" / "gse_plus_seasonal_features_2024.csv")

for _d in (RAW, INTERIM, DERIVED, EVIDENCE, MODELS):
    _d.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------------------- keys -----
CRS = "EPSG:4326"

KEY_PARCEL = "parcel_id"      # {village}_{survey_no}_{subdivision}
KEY_BAG = "bag_id"            # image_path — THE leakage group key
KEY_VILLAGE = "village_code"
LABEL = "crop"
STAGE = "crop_stage"

# Keys that must survive every join, aggregation and export (parcel-join skill)
INVARIANT_KEYS = [KEY_PARCEL, KEY_BAG, KEY_VILLAGE]

# ------------------------------------------------------------- features -----
GSE_BANDS = [f"A{i:02d}" for i in range(64)]
SEASONS = (1, 2, 3, 4)
SEASONAL_BANDS = [f"S{s}_{b}" for s in SEASONS for b in ("NDVI", "VH", "VV")]

# Rabi 2024-25, Tamil Nadu. The ground-truth survey ran November 2024; these four
# windows span the crop cycle around it. gee-export skill: one definition, used everywhere.
SEASON_WINDOWS = {
    1: ("2024-06-01", "2024-08-31"),   # Kharif / pre-season
    2: ("2024-09-01", "2024-11-30"),   # sowing — contains the survey window
    3: ("2024-12-01", "2025-02-28"),   # peak vegetative
    4: ("2025-03-01", "2025-05-31"),   # maturity / harvest
}
SURVEY_WINDOW = ("2024-11-06", "2024-11-13")

# ------------------------------------------------------------ modelling -----
SEED = 0
N_FOLDS = 5

# leakage-protocol: the four regimes, by group key. None == stratified row split.
SPLIT_REGIMES = {
    "1-random": None,
    "2-parcel": KEY_PARCEL,
    "3-event": KEY_BAG,          # <- THE HEADLINE REGIME
    # The village the parcel ACTUALLY falls in, not the recorded code. 1,930
    # records (13%) disagree between the two, and grouping by the recorded code
    # leaves parcels from the same physical village on both sides of a fold.
    "4-village": "village_spatial",
}
HEADLINE_REGIME = "3-event"

# A class with fewer than this many INDEPENDENT capture events is not evaluable
# and is collapsed to OTHER_CLASS (leakage-protocol rule 5).
MIN_EVENTS_PER_CLASS = 5
OTHER_CLASS = "Other"

LGBM_PARAMS = dict(n_estimators=300, learning_rate=0.05, num_leaves=31,
                   verbose=-1, n_jobs=8)

# ----------------------------------------------------------- audit ----------
# audit-signals skill. Exposed through the API and movable in the UI — never
# duplicated anywhere else in the codebase.
THRESHOLDS = {
    "confidence_high": 0.80,      # the brief's own 80% confidence line
    "confidence_low": 0.50,
    "trust_floor": 0.35,          # below this the RECORD is unverifiable
    "trust_high": 0.65,
}

# Record Trust Score component weights (audit-signals: publish the weights)
TRUST_WEIGHTS = {
    "bag_size": 0.25,                    # more parcels sharing one photo -> less trust
    "photo_distance": 0.20,              # photo farther from parcel -> less trust
    "bag_support": 0.25,                 # MIL attention weight -> low means passenger
    "stage_plausibility": 0.10,
    "mixed_crop": 0.10,
    "geometry_source": 0.05,
    "heterogeneity": 0.05,
}

# Saturation points for trust normalisation, from Phase 0 forensics.
TRUST_SCALES = {
    "bag_size_saturate": 20,       # bags of 20+ carry no per-parcel evidence
    "photo_distance_saturate_m": 3000,   # p90 of the measured distribution
}

# Audit-layer constants that shape the trust score and the worklist ranking.
# They were inline in audit.py; anything that moves a published number belongs here.
AUDIT_CONSTANTS = {
    "ece_bins": 15,
    "bag_support_saturate": 1.5,       # attention credit saturates here
    "heterogeneity_scale_quantile": 0.95,
    "stage_rarity_cap": 0.5,           # stage share above this is "not rare"
    "area_weight_clip": (0.25, 4.0),   # how far parcel size may steer the ranking
    "random_baseline_draws": 200,
    # P(label wrong) asserted by the model is discounted by how often the model is
    # itself right. Set from the measured headline accuracy; see p6_audit.py.
    "label_error_damping_no_candidate": 0.5,
}

# Buffered-point fallback parcel radius when delineation yields no polygon
FALLBACK_PARCEL_RADIUS_M = 30

# ------------------------------------------- AI-1 field delineation (FTW) ---
# Fields of The World v3 ("PRUE"): three-class U-Net (background / field interior /
# field boundary) over a bi-temporal Sentinel-2 stack. Registry name as published in
# ftw_tools.inference.model_registry.
#
# The CC-BY checkpoint is chosen over the more accurate "FULL" one deliberately. FULL
# is trained on mixed-licence national datasets, several non-commercial; we would be
# redistributing parcel geometry derived from it. data-provenance skill: check the
# terms before acquiring, not after. Override with --model if FarmwiseAI accept the
# licence position.
FTW_MODEL = "FTW_PRUE_EFNET_B7_CCBY"

# The bi-temporal pair, as SEASON_WINDOWS keys. FTW wants one scene near sowing and
# one at peak canopy: the boundary signal is the phenological CONTRAST between
# neighbouring fields, so two dates inside the same growth stage carry almost no
# information for it.
FTW_WINDOW_PAIR = (2, 3)          # 2 = sowing, 3 = peak vegetative

# Per-window band order the pretrained model expects. Stacked window A then window B,
# giving 8 bands: B04_t1 B03_t1 B02_t1 B08_t1 B04_t2 B03_t2 B02_t2 B08_t2.
FTW_BANDS = ["B04", "B03", "B02", "B08"]
FTW_STACK_BANDS = 8

# Minimum area we will accept as a field. 500 m2 is 0.05 ha: about five Sentinel-2
# pixels across, the floor below which a 10 m sensor cannot resolve a field at all.
# It is deliberately BELOW the Tamil Nadu smallholding range (0.1-0.5 ha) so the
# filter removes speckle, not real fields. Raising it to 1 ha would delete most of
# Sivagiri's actual farmland.
FTW_MIN_FIELD_AREA_M2 = 500

# Above this, a polygon is almost certainly several fields merged by a missed
# boundary. Not deleted - counted, as an under-segmentation signal.
FTW_MAX_PLAUSIBLE_FIELD_AREA_M2 = 50_000

# Polygonisation simplification tolerance, metres. FTW's own default is 15 m, tuned
# on the large-field geographies that dominate its training set. A Tamil Nadu
# smallholding is 20-70 m across, so a 15 m tolerance is comparable to the whole
# field's width and would round real corners away.
FTW_SIMPLIFY_M = 5

# Polsby-Popper compactness, 4*pi*A/P^2. A real field is blocky (>0.3); values near
# zero are the ribbon slivers that vectorising a boundary class produces.
FTW_MIN_COMPACTNESS = 0.10

# plan.md Phase 2 acceptance gate.
# Metres a survey point may be snapped to the nearest delineated field.
# Chosen from the measured offset distribution, not tuned for the gate: unmatched
# points sit about one to two Sentinel-2 pixels from the nearest field, consistent
# with handheld-GPS positional error. Distribution: docs/evidence/p2e_ftw_match_detail.json.
FTW_SNAP_TOLERANCE_M = 20.0

FTW_MATCH_RATE_GATE = 0.80

# Projection for all metric work in south Tamil Nadu: UTM zone 43N. The AOI's mean longitude is 77.41E, and zone 43 spans 72-78E.
# An earlier version used 44N (78-84E), which inflated every area by 0.218% and
# distorted the photo-distance trust signal. FTW's own output confirmed 43N.
METRIC_CRS = "EPSG:32643"

# verification-economics: assumed cost model. Stated, not hidden.
VISIT_COST = {
    "parcels_per_surveyor_day": 25,
    "note": "Assumption. Derived from 3,204 capture events over a ~7-day survey window "
            "across 21 villages in the supplied sample; revise with FarmwiseAI's actuals.",
}

# ------------------------------------------------------------ crop area -----
# Field-level crop-area aggregation (plan.md Phase 2 consequences; kaval/area.py).
SHARED_GEOMETRY_SOURCE = "ftw_shared"   # geometry_source value for a shared FTW field
KEY_FIELD = "field_id"
AREA_CHECK_TOL_HA = 1e-6                # totals must survive aggregation to this
AREA_RULE = (
    "Crop area is aggregated at FIELD level for geometry_source == 'ftw_shared': "
    "a physical field holding several survey records is assigned ONE crop, the "
    "label with the largest apportioned area inside it (ties go to the "
    "alphabetically first label), and contributes the summed area of its records "
    "present in the audit. Totals equal the per-parcel apportioned totals. "
    "conflicted_area_ha is the area of fields whose records disagree on the label, "
    "so the majority rule does not hide the disagreement.")
