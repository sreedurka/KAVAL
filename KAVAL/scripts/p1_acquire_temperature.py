"""
KAVAL / Phase 1 — monthly air temperature, without a CDS key.

`plan.md` §4 lists ERA5-Land for temperature. ERA5-Land needs a Copernicus CDS API
key we do not hold, so the channel was going to be masked in the Presto input.

NASA POWER serves MERRA-2 reanalysis over an open, keyless HTTP API, which closes
the gap. It is a substitution, so it is recorded as one rather than quietly filling
the ERA5-Land row.

**Resolution caveat, the same one CHIRPS carries.** MERRA-2 is roughly 0.5 deg x
0.625 deg — about 55 x 70 km, so the whole 437 km2 taluk sits inside one or two
cells. This is a taluk-scale series, not a per-parcel one. Joining it to parcels
would imply a spatial precision the data does not have; every parcel in a month
gets the same value and the evidence artefact says so.

Run:  .venv/bin/python KAVAL/scripts/p1_acquire_temperature.py
Out:  data/raw/temperature_monthly_sivagiri.csv, docs/evidence/p1_temperature.json
"""

import json
import sys
import urllib.request
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kaval import provenance  # noqa: E402
from kaval.config import EVIDENCE, RAW, TALUK  # noqa: E402

OUT = RAW / "temperature_monthly_sivagiri.csv"
API = ("https://power.larc.nasa.gov/api/temporal/monthly/point"
       "?parameters=T2M,T2M_MIN,T2M_MAX&community=AG"
       "&longitude={lon:.4f}&latitude={lat:.4f}&start={y0}&end={y1}&format=JSON")
MONTHS = pd.period_range("2024-06", "2025-05", freq="M")


def main():
    # Centroid of the supplied taluk polygon, never a hand-typed coordinate.
    taluk = gpd.read_file(TALUK).to_crs("EPSG:4326")
    c = taluk.geometry.union_all().centroid
    url = API.format(lon=c.x, lat=c.y, y0=2024, y1=2025)

    with urllib.request.urlopen(url, timeout=120) as r:
        payload = json.load(r)

    params = payload["properties"]["parameter"]
    rows = []
    for key in sorted(params["T2M"]):
        # POWER appends a month "13" per year holding the ANNUAL mean. Including
        # it would silently corrupt a monthly series.
        if key.endswith("13"):
            continue
        period = pd.Period(f"{key[:4]}-{key[4:]}", freq="M")
        if period not in MONTHS:
            continue
        rec = {"month": str(period)}
        for p in ("T2M", "T2M_MIN", "T2M_MAX"):
            v = params.get(p, {}).get(key)
            # POWER uses -999 as its fill value; it must not reach the model.
            rec[p.lower()] = None if v is None or v <= -998 else float(v)
        rec["t2m_kelvin"] = None if rec["t2m"] is None else round(rec["t2m"] + 273.15, 3)
        rows.append(rec)

    df = pd.DataFrame(rows).sort_values("month")
    df.to_csv(OUT, index=False)

    ev = {
        "source": "NASA POWER (MERRA-2 reanalysis), keyless HTTP API",
        "substitutes_for": "ERA5-Land, which requires a Copernicus CDS API key we do "
                           "not hold",
        "point": {"lon": round(c.x, 4), "lat": round(c.y, 4),
                  "derived_from": "centroid of the supplied taluk polygon"},
        "months": len(df),
        "months_expected": len(MONTHS),
        "missing_months": [str(m) for m in MONTHS if str(m) not in set(df.month)],
        "t2m_celsius": {"min": float(df.t2m.min()), "max": float(df.t2m.max()),
                        "mean": round(float(df.t2m.mean()), 2)},
        "resolution_caveat": (
            "MERRA-2 is ~0.5 deg x 0.625 deg (~55 x 70 km). The entire 437 km2 taluk "
            "falls in one or two cells, so this is a TALUK-scale series. Every parcel "
            "in a given month receives the same value; it carries no within-taluk "
            "spatial information."),
        "units_note": "t2m is degrees Celsius as POWER serves it; t2m_kelvin is the "
                      "converted column Presto expects.",
    }
    (EVIDENCE / "p1_temperature.json").write_text(json.dumps(ev, indent=2))
    provenance.record(
        OUT, classification="ACQUIRED",
        source=f"NASA POWER monthly point API (MERRA-2), {url}",
        licence="NASA POWER data are freely available and unrestricted; cite NASA "
                "Langley Research Center POWER Project",
        produced_by="KAVAL/scripts/p1_acquire_temperature.py",
        spatial_extent="Single MERRA-2 cell at the Sivagiri taluk centroid",
        temporal_extent="monthly, June 2024 - May 2025",
        transform="annual (month 13) records dropped; -999 fill converted to null; "
                  "Kelvin column added",
        notes=ev["resolution_caveat"], agent="data-acquisition")

    print(json.dumps(ev, indent=2))
    print()
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
