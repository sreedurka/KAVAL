"""
KAVAL / Phase 3b — AI-2 second arm: Presto embeddings.

The challenge brief asks us to "compare the performance obtained from Google
Satellite Embeddings and Presto embeddings where both are supplied". FarmwiseAI
supplied neither, so we acquired both: Google Satellite Embedding from Earth
Engine, and Presto (NASA Harvest, MIT) run here over Sentinel time series we
pulled from public STAC endpoints.

The two encode very different things, which is what makes the comparison worth
making rather than ceremonial:

  * **Google Satellite Embedding** is an annual, spatial summary — one 64-d vector
    per pixel per year, distilled from Landsat, Sentinel-1 and Sentinel-2.
  * **Presto** is a time-series transformer — it reads a per-pixel sequence of
    monthly observations and returns a 128-d vector. It sees phenology; GSE sees
    a year.

Two honesty notes carried into the evidence artefact:

  1. **Domain shift.** Presto was pretrained on Sentinel-2 L1C top-of-atmosphere.
     We feed it L2A surface reflectance, because that is what the STAC endpoints
     serve and what the rest of the pipeline uses. That is a small systematic
     shift, reported rather than silently corrected.
  2. **Coarse meteorology.** Presto expects temperature and precipitation per
     pixel. Ours are reanalysis products at 0.05 deg (CHIRPS) and ~0.5 deg
     (MERRA-2 via NASA POWER, substituting for the ERA5-Land we have no key for),
     so both are taluk-scale: every parcel in a given month gets the same value.
     They carry seasonality, which is what Presto reads them for, but no
     within-taluk spatial signal. Fed as real values rather than masked, with the
     limitation recorded.

Run:  .venv/bin/python KAVAL/scripts/p3b_presto_embeddings.py
Out:  data/derived/presto_embeddings.parquet, docs/evidence/p3b_presto.json
"""

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")
from kaval import provenance  # noqa: E402
from kaval.config import DERIVED, EVIDENCE, KEY_PARCEL, RAW  # noqa: E402

STORE = DERIVED / "feature_store.parquet"
from kaval.presto_io import build_inputs, embed, load_presto  # noqa: E402

SERIES = RAW / "presto_monthly_series.parquet"
CHIRPS = RAW / "chirps_monthly_sivagiri.csv"
TEMPERATURE = RAW / "temperature_monthly_sivagiri.csv"
OUT = DERIVED / "presto_embeddings.parquet"

S2_BANDS = ["B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B11", "B12"]
S1_BANDS = ["VV", "VH"]
# 12 monthly steps at Presto's pretraining cadence, starting June 2024.
MONTHS = pd.period_range("2024-06", "2025-05", freq="M")
START_MONTH = 5          # June, 0-indexed from January


def pivot(df, cols, parcels):
    """Long (parcel x month) -> dense [N, T, len(cols)] with NaN where unobserved."""
    out = np.full((len(parcels), len(MONTHS), len(cols)), np.nan, dtype=np.float32)
    pidx = {p: i for i, p in enumerate(parcels)}
    midx = {str(m): i for i, m in enumerate(MONTHS)}
    present = [c for c in cols if c in df.columns]
    if not present:
        return out, present
    sub = df[[KEY_PARCEL, "month"] + present].copy()
    sub["month"] = sub["month"].astype(str)
    for c_i, c in enumerate(cols):
        if c not in present:
            continue
        v = sub[[KEY_PARCEL, "month", c]].dropna(subset=[c])
        rows = v[KEY_PARCEL].map(pidx).to_numpy()
        colsi = v["month"].map(midx).to_numpy()
        ok = ~(pd.isna(rows) | pd.isna(colsi))
        out[rows[ok].astype(int), colsi[ok].astype(int), c_i] = v[c].to_numpy()[ok]
    return out, present


def main():
    if not SERIES.exists():
        sys.exit(f"{SERIES} not found. Run KAVAL/scripts/p1_acquire_stac.py first — "
                 "Presto needs ~12 monthly Sentinel composites, not the 4 seasonal "
                 "windows Phase 4 uses.")
    provenance.require(SERIES)

    df = pd.read_parquet(SERIES)
    parcels = sorted(df[KEY_PARCEL].unique())
    ev = {"n_parcels": len(parcels), "timesteps": len(MONTHS),
          "months": [str(m) for m in MONTHS], "start_month_index": START_MONTH}

    s2, s2_present = pivot(df, S2_BANDS, parcels)
    s1, s1_present = pivot(df, S1_BANDS, parcels)
    ev["s2_bands_present"] = s2_present
    ev["s1_bands_present"] = s1_present
    ev["s2_observed_fraction"] = round(float(np.isfinite(s2).mean()), 4)
    ev["s1_observed_fraction"] = round(float(np.isfinite(s1).mean()), 4)
    # Cloud gaps are a fact about Tamil Nadu's north-east monsoon, not a bug.
    ev["s2_observed_by_month"] = {
        str(m): round(float(np.isfinite(s2[:, i, :]).mean()), 3)
        for i, m in enumerate(MONTHS)}

    # Precipitation from CHIRPS as a taluk-wide monthly mean (see below).
    precip = None
    if CHIRPS.exists():
        ch = pd.read_csv(CHIRPS)
        mcol = next((c for c in ch.columns if "month" in c.lower()), None)
        pcol = next((c for c in ch.columns if "precip" in c.lower() or "chirps" in c.lower()), None)
        if mcol and pcol:
            # Taluk-wide monthly mean: CHIRPS is 0.05 deg (~5.5 km), far coarser
            # than a parcel, so a per-parcel join would imply precision it lacks.
            monthly = ch.groupby(ch[mcol].astype(str))[pcol].mean()
            series = np.array([monthly.get(str(m), np.nan) for m in MONTHS], dtype=np.float32)
            # CHIRPS is mm/month; Presto wants metres over the step.
            precip = np.repeat((series / 1000.0)[None, :], len(parcels), axis=0)
            ev["precipitation_source"] = "CHIRPS monthly, taluk mean, mm converted to m"
    if precip is None:
        ev["precipitation_source"] = "unavailable — masked"
    # Temperature from NASA POWER (MERRA-2), substituting for ERA5-Land. Taluk-scale
    # like the precipitation, for the same reason.
    temp = None
    if TEMPERATURE.exists():
        td = pd.read_csv(TEMPERATURE).set_index("month")
        series = np.array([td["t2m_kelvin"].get(str(m), np.nan) for m in MONTHS],
                          dtype=np.float32)
        if np.isfinite(series).any():
            temp = np.repeat(series[None, :], len(parcels), axis=0)
            ev["temperature_source"] = ("NASA POWER (MERRA-2) monthly T2M at the taluk "
                                        "centroid, Kelvin; substitutes for ERA5-Land")
            ev["temperature_months_present"] = int(np.isfinite(series).sum())
    if temp is None:
        ev["temperature_source"] = "unavailable — masked, not imputed"

    # Presto's location token wants each parcel's lat/lon. The monthly series does
    # not carry coordinates; the feature store holds the canonical parcel location.
    provenance.require(STORE)
    loc = pd.read_parquet(STORE, columns=[KEY_PARCEL, "lat", "lon"]).set_index(KEY_PARCEL)
    loc = loc.reindex(parcels)
    if loc[["lat", "lon"]].isna().any().any():
        missing = int(loc["lat"].isna().sum())
        sys.exit(f"{missing} parcels in the monthly series have no location in {STORE.name}")
    latlons = loc[["lat", "lon"]].to_numpy(dtype=np.float32)

    # Static terrain for Presto's SRTM slot. We have the Copernicus GLO-30 DEM
    # (acquired alongside the series), not SRTM: same quantity, different
    # product — recorded as a substitution. Static, so one value per parcel.
    elev = slope = None
    if {"elevation_m", "slope_deg"} <= set(df.columns):
        st = df.groupby(KEY_PARCEL)[["elevation_m", "slope_deg"]].first().reindex(parcels)
        elev = st["elevation_m"].to_numpy(dtype=np.float32)
        slope = st["slope_deg"].to_numpy(dtype=np.float32)
        ev["terrain_source"] = ("Copernicus DEM GLO-30 elevation and slope, substituted "
                                "for SRTM in Presto's static slot")
        ev["terrain_observed_fraction"] = round(float(np.isfinite(elev).mean()), 4)
    else:
        ev["terrain_source"] = "unavailable — masked"

    print(f"building inputs for {len(parcels):,} parcels x {len(MONTHS)} months")
    x, mask, dw = build_inputs(s1_db=s1, s2_dn=s2, era5_temp_k=temp,
                               era5_precip_m=precip, srtm_elev_m=elev,
                               srtm_slope_deg=slope)
    ev["masked_fraction"] = round(float(mask.float().mean()), 4)

    model = load_presto()
    print("embedding…")
    emb = embed(model, x, mask, dw, latlons, START_MONTH)
    ev["embedding_dim"] = int(emb.shape[1])
    ev["embeddings_finite"] = bool(np.isfinite(emb).all())
    assert ev["embeddings_finite"], "Presto returned non-finite embeddings"

    out = pd.DataFrame(emb, columns=[f"P{i:03d}" for i in range(emb.shape[1])])
    out.insert(0, KEY_PARCEL, parcels)
    out.to_parquet(OUT, index=False)

    ev["meteorology_caveat"] = (
        "Temperature and precipitation are reanalysis products at ~0.5 deg and 0.05 deg "
        "respectively, so both are constant across the taluk within a month. They supply "
        "seasonality, not spatial signal.")
    # What the downstream comparison is actually testing. Both limit how far a
    # Presto-vs-GSE gap can be read as a verdict on Presto itself.
    ev["input_granularity"] = (
        "One series per parcel: the monthly value is the MEAN over the parcel's pixels "
        "(p1_acquire_stac.py), not a per-pixel series pooled afterwards. Presto was "
        "pretrained per pixel.")
    ev["usage"] = ("Frozen pretrained encoder, no fine-tuning; the 128-d embedding is "
                   "fed to the same MLP head and folds as GSE (p4 section C).")
    obs = ev["s2_observed_by_month"]
    worst = min(obs, key=obs.get)
    ev["s2_worst_month"] = {"month": worst, "observed_fraction": obs[worst]}
    ev["domain_shift_note"] = (
        "Presto was pretrained on Sentinel-2 L1C top-of-atmosphere; we feed L2A "
        "surface reflectance. A small systematic shift, reported rather than "
        "corrected. Any GSE-vs-Presto gap should be read with this in mind.")
    (EVIDENCE / "p3b_presto.json").write_text(json.dumps(ev, indent=2, default=str))
    provenance.record(
        OUT, classification="DERIVED",
        source="Presto (NASA Harvest, MIT) run over per-parcel monthly Sentinel-1/2 "
               "series acquired from public STAC endpoints",
        licence="Derived; Presto MIT (cite arXiv:2304.14065); Copernicus Sentinel data "
                "free and open",
        produced_by="KAVAL/scripts/p3b_presto_embeddings.py",
        temporal_extent="12 monthly steps, June 2024 - May 2025",
        transform="normalisation per presto_io.build_inputs; NaN observations masked, "
                  "never interpolated",
        inputs=[str(SERIES.relative_to(SERIES.parents[3])),
                "KAVAL/data/derived/feature_store.parquet (parcel lat/lon)",
                "KAVAL/models/presto/default_model.pt",
                # Meteorology channels read by build_inputs (precip + temperature).
                "KAVAL/data/raw/chirps_monthly_sivagiri.csv",
                "KAVAL/data/raw/temperature_monthly_sivagiri.csv"],
        notes=f"{emb.shape[1]}-d embeddings for {len(parcels):,} parcels.",
        agent="embedding-engineer")

    print(json.dumps({k: v for k, v in ev.items()
                      if k != "s2_observed_by_month"}, indent=2, default=str))
    print("\nS2 observed fraction by month:")
    for m, v in ev["s2_observed_by_month"].items():
        print(f"  {m}: {v:.1%}")


if __name__ == "__main__":
    main()
