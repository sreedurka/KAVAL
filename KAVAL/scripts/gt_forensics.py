"""
KAVAL / Phase 1 — Ground-truth forensics.

Regenerates every factual claim made in proposal_updated.md about the supplied
Digital Crop Survey reference sample. Writes docs/evidence/gt_forensics.json
and docs/evidence/gt_forensics.md.

Run:  .venv/bin/python KAVAL/scripts/gt_forensics.py
"""

import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
GT = ROOT / "Dataset" / "Ground Truth Points" / "Ground_truth_Points.csv"
OUT = ROOT / "KAVAL" / "docs" / "evidence"


def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p = math.radians
    dlat, dlon = p(lat2 - lat1), p(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p(lat1)) * math.cos(p(lat2)) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def first_num(s):
    """Some image coordinate cells contain two values joined by ';'."""
    s = str(s).strip()
    if ";" in s:
        s = s.split(";")[0]
    try:
        return float(s)
    except ValueError:
        return float("nan")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(GT)
    ev = {}

    ev["n_records"] = len(df)
    ev["n_villages"] = int(df["village__1"].nunique())
    ev["n_capture_events"] = int(df["image_path"].nunique())
    ev["label_inflation_factor"] = round(len(df) / df["image_path"].nunique(), 2)

    # --- Claim 1: one capture event supplies many parcel labels -------------
    g = df.groupby("image_path")
    sizes = g.size()
    ev["max_parcels_per_capture_event"] = int(sizes.max())
    ev["pct_records_in_multi_parcel_events"] = round(
        100 * sizes[sizes > 1].sum() / len(df), 1
    )
    # Within a capture event, are the survey attributes constant?
    const = {}
    for col in ["final_crop_name", "final_crop_stage", "village__1",
                "image_timestamp", "image_latitude", "image_longitude"]:
        const[col] = int((g[col].nunique() == 1).sum())
    ev["capture_events_with_constant_field"] = const
    ev["capture_events_with_mixed_crop_label"] = int((g["final_crop_name"].nunique() > 1).sum())

    # --- Claim 2: effective sample size per crop ----------------------------
    per_crop = (
        df.groupby("final_crop_name")
        .agg(records=("image_path", "size"), capture_events=("image_path", "nunique"))
        .sort_values("records", ascending=False)
    )
    per_crop["inflation"] = (per_crop.records / per_crop.capture_events).round(1)
    ev["per_crop_effective_n"] = per_crop.to_dict(orient="index")

    # --- Claim 3: the photograph is not co-located with the parcel ----------
    df["ilat"] = df["image_latitude"].map(first_num)
    df["ilon"] = df["image_longitude"].map(first_num)
    # Some cells hold two values joined by ';' and a few decode to coordinates
    # outside the study area entirely. Both are data-quality findings in their
    # own right, so count them rather than silently coercing.
    # Either coordinate may be multi-valued; checking latitude alone undercounts by
    # 2 and disagrees with p1_repair_ground_truth.py, which checks both.
    ev["records_with_multivalued_image_coord"] = int(
        (df["image_latitude"].astype(str).str.contains(";")
         | df["image_longitude"].astype(str).str.contains(";")).sum()
    )
    plausible = df.ilat.between(8.0, 14.0) & df.ilon.between(76.0, 81.0)
    ev["records_with_out_of_area_image_coord"] = int((~plausible).sum())
    ok = df[plausible].dropna(subset=["ilat", "ilon"])
    d = [
        haversine_m(r.ilat, r.ilon, r.final_lat, r.final_long)
        for r in ok.itertuples()
    ]
    s = pd.Series(d)
    ev["photo_to_parcel_distance_m"] = {
        "median": round(s.median()),
        "p75": round(s.quantile(0.75)),
        "p90": round(s.quantile(0.90)),
        "p99": round(s.quantile(0.99)),
        "max": round(s.max()),
        "pct_over_1km": round(100 * (s > 1000).mean(), 1),
        "pct_over_3km": round(100 * (s > 3000).mean(), 1),
    }

    # Spatial tightness of the parcels sharing one label
    diam = []
    for _, sub in df.groupby("image_path"):
        if len(sub) < 2:
            continue
        pts = list(zip(sub.final_lat, sub.final_long))
        diam.append(max(
            haversine_m(*pts[i], *pts[j])
            for i in range(len(pts)) for j in range(i + 1, len(pts))
        ))
    ds = pd.Series(diam)
    ev["capture_event_parcel_spread_m"] = {
        "median": round(ds.median()), "p90": round(ds.quantile(0.90)), "max": round(ds.max()),
    }

    # --- Claim 4: class imbalance and mixed-crop declarations ---------------
    vc = df["final_crop_name"].value_counts()
    ev["n_crop_classes"] = int(vc.size)
    ev["top5_share_pct"] = round(100 * vc.head(5).sum() / len(df), 1)
    ev["n_mixed_crop_declarations"] = int(df["rabi_crop_classification"].str.contains(";").sum())
    ev["crop_stage_distribution"] = df["final_crop_stage"].value_counts().to_dict()

    # Stage is confounded with crop: report the worst offenders
    conf = {}
    for crop, sub in df.groupby("final_crop_name"):
        top = sub["final_crop_stage"].value_counts(normalize=True).iloc[0]
        conf[crop] = round(100 * top, 1)
    ev["pct_records_in_modal_stage_per_crop"] = conf

    # --- Claim 5: geometry we were NOT given --------------------------------
    ev["parcel_polygons_supplied"] = False
    ev["note"] = (
        "Supplied reference sample only. Records are points; no cadastral parcel "
        "geometry was supplied, so parcel boundaries must be acquired or derived."
    )

    (OUT / "gt_forensics.json").write_text(json.dumps(ev, indent=2, default=str))

    # --- Human-readable summary --------------------------------------------
    L = []
    L.append("# Ground-Truth Forensics — Supplied Reference Sample\n")
    L.append(f"Source: `{GT.relative_to(ROOT)}`  ·  regenerate with `KAVAL/scripts/gt_forensics.py`\n")
    L.append("## Headline\n")
    L.append(f"- **{ev['n_records']:,} survey records** across {ev['n_villages']} villages")
    L.append(f"- ...but only **{ev['n_capture_events']:,} distinct capture events** "
             f"(**{ev['label_inflation_factor']}x label inflation**)")
    L.append(f"- A single capture event supplies up to **{ev['max_parcels_per_capture_event']} parcel labels**")
    L.append(f"- **{ev['pct_records_in_multi_parcel_events']}%** of records sit in a multi-parcel capture event")
    L.append(f"- Capture events containing more than one crop label: "
             f"**{ev['capture_events_with_mixed_crop_label']}** (out of {ev['n_capture_events']:,})\n")
    L.append("## Effective sample size per crop\n")
    L.append("| Crop | Records | Capture events | Inflation |")
    L.append("|---|---:|---:|---:|")
    for crop, row in ev["per_crop_effective_n"].items():
        L.append(f"| {crop} | {row['records']:,} | {row['capture_events']} | {row['inflation']}x |")
    L.append("\n> Per-class metrics for the minority crops rest on a handful of independent")
    L.append("> observations. Reporting an F1 score for them without stating this is misleading.\n")
    p = ev["photo_to_parcel_distance_m"]
    L.append("## Photograph geolocation vs. the parcel it documents\n")
    L.append(f"- median **{p['median']:,} m**, p90 **{p['p90']:,} m**, max **{p['max']:,} m**")
    L.append(f"- **{p['pct_over_1km']}%** of records are documented by a photograph taken over 1 km away")
    L.append(f"- separately, **{ev['records_with_multivalued_image_coord']}** records store two "
             f"coordinates in one cell and **{ev['records_with_out_of_area_image_coord']}** decode "
             "to a location outside the study area — both must be repaired before use")
    sp = ev["capture_event_parcel_spread_m"]
    L.append(f"- the parcels sharing one label are themselves tight (median spread {sp['median']} m), "
             "so the label behaves as a spatially smoothed block, not a per-parcel observation\n")
    L.append("## Class structure\n")
    L.append(f"- {ev['n_crop_classes']} crop classes; top 5 account for **{ev['top5_share_pct']}%** of records")
    L.append(f"- **{ev['n_mixed_crop_declarations']}** records declare more than one crop category "
             "(single-label classification cannot express these)")
    (OUT / "gt_forensics.md").write_text("\n".join(L) + "\n")

    print("\n".join(L))


if __name__ == "__main__":
    main()
