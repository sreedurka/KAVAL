"""
KAVAL / Phase 7 — Village-level registry comparison.

The challenge brief asks us to "show villages where predicted crop area differs
significantly from the supplied registry". Until now `/summary/registry-delta`
compared our own data to itself, which we had to caveat in the payload. This
builds the real comparison against the Tamil Nadu Agrisnet village-wise Digital
Crop Survey report for Rabi 2024.

Two things make a naive hectare-vs-hectare comparison wrong, and both are handled
here:

  1. **Our parcels do not cover the village.** The supplied ground truth is a
     sample of survey points whose parcels cover a fraction of the registry's
     area for the same villages (figures in the evidence file). Comparing absolute area would measure sampling coverage,
     not agreement. So we compare **crop composition** — each crop's share of the
     village's cropped area — which is scale-free.

  2. **Attribute by the RECORDED village code, not the polygon the point falls in.**
     Some records disagree between the two (counts in the evidence file). The
     registry is keyed on village names carried by the same code system the survey
     uses, so its agreement with the recorded code is expected BY CONSTRUCTION and
     cannot show which attribution is correct. The only independent evidence is
     geometric: the crosstab of recorded code by containing polygon for the
     Viswanathaperi 911/912 pair, written to `docs/evidence/p7_registry.json`. It
     points at a boundary or labelling error in the supplied layer but does not
     prove it; it needs cadastral or field confirmation from FarmwiseAI.

     Note this does not change the leakage protocol: regime 4 still groups by
     polygon membership, because spatial blocking depends on where a parcel
     physically is, not on which administrative label is attached to it.

  3. **The registry is not independent of the survey.** Agrisnet publishes the
     aggregate of the same Digital Crop Survey whose parcel-level sample
     FarmwiseAI supplied. So this audits the DCS's own published numbers against
     satellite. That is a real and useful audit, but it is NOT validation against
     a second, independent survey, and every consumer of this output says so.

Run:  .venv/bin/python KAVAL/scripts/p7_registry_comparison.py
Out:  data/derived/village_registry.parquet, docs/evidence/p7_registry.json
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kaval import provenance  # noqa: E402
from kaval.area import crop_area  # noqa: E402
from kaval.config import AREA_RULE, DERIVED, EVIDENCE, HEADLINE_REGIME, KEY_PARCEL, RAW  # noqa: E402

REGISTRY = RAW / "tn_crop_registry.csv"
AUDIT = DERIVED / "audit.parquet"
OUT = DERIVED / "village_registry.parquet"

SEASON = "Rabi 2024"          # matches the November 2024 survey window
TALUK = "Sivagiri"
PAIR = (911, 912)             # Viswanathaperi Part-1 / Part-2 village codes

INDEPENDENCE_NOTE = (
    "The Agrisnet village figures are the published aggregate of the SAME Digital "
    "Crop Survey whose parcel-level sample was supplied as ground truth. This "
    "comparison therefore audits the DCS's own published numbers against satellite. "
    "It is not validation against an independent second survey.")

SCALE_NOTE = (
    "Compared as crop SHARE of village cropped area, not absolute hectares: our "
    "parcel sample covers a fraction of each village, so an absolute comparison "
    "would measure sampling coverage rather than agreement.")


def main():
    provenance.require(REGISTRY)
    provenance.require(AUDIT)

    reg = pd.read_csv(REGISTRY)
    reg = reg[(reg.level == "village") & (reg.season == SEASON)
              & (reg.taluk == TALUK)].copy()

    audit = pd.read_parquet(AUDIT)
    # Attribute to the village the SURVEY recorded, because that is the key the
    # registry is published against. `village_name` on audit.parquet comes from
    # polygon membership, which is the disputed attribution.
    fs = pd.read_parquet(DERIVED / "feature_store.parquet")[
        [KEY_PARCEL, "village_code", "village_spatial", "village_name"]]
    code_to_name = (fs.drop_duplicates("village_spatial")
                    .set_index("village_spatial")["village_name"].to_dict())
    audit = audit.drop(columns=["village_name"]).merge(fs, on=KEY_PARCEL, how="left")
    audit["village_recorded"] = audit["village_code"].map(code_to_name)
    audit["village_polygon"] = audit["village_name"]
    audit["village_name"] = audit["village_recorded"].fillna(audit["village_polygon"])
    ev = {"area_rule": AREA_RULE, "season": SEASON, "split_regime": HEADLINE_REGIME,
          "independence_note": INDEPENDENCE_NOTE, "scale_note": SCALE_NOTE}

    # --- restrict both sides to the classes we can actually predict -----------
    # The model has five evaluable classes; the registry lists every crop grown.
    # Comparing our five against their everything would manufacture a deficit, so
    # both sides are renormalised over the same five crops and the share of
    # registry area that falls outside them is reported separately.
    classes = sorted(c for c in audit.y_pred.unique() if c != "Other")
    reg["in_scope"] = reg.crop.isin(classes)
    ev["registry_area_ha_total"] = round(float(reg.area_ha.sum()), 1)
    ev["registry_area_ha_in_scope"] = round(float(reg.loc[reg.in_scope, "area_ha"].sum()), 1)
    ev["registry_out_of_scope_pct"] = round(
        100 * (1 - ev["registry_area_ha_in_scope"] / ev["registry_area_ha_total"]), 1)
    ev["registry_crops_out_of_scope"] = sorted(
        reg.loc[~reg.in_scope].groupby("crop").area_ha.sum()
        .sort_values(ascending=False).head(8).index.tolist())

    r = (reg[reg.in_scope].groupby(["village", "crop"]).area_ha.sum()
         .rename("registry_ha").reset_index())
    r["registry_share"] = r.registry_ha / r.groupby("village").registry_ha.transform("sum")

    # --- our side ------------------------------------------------------------
    a = audit[audit.y_pred.isin(classes)]
    # Area is aggregated at field level (kaval/area.py) so a shared field is one crop.
    cnt = (a.groupby(["village_name", "y_pred"])
           .agg(parcels=(KEY_PARCEL, "size"),
                mean_confidence=("confidence_calibrated", "mean")).reset_index())
    ar = crop_area(a, "y_pred", ["village_name"]).rename(columns={"area_ha": "sat_ha"})
    s = (cnt.merge(ar, on=["village_name", "y_pred"], how="outer")
         .rename(columns={"village_name": "village", "y_pred": "crop"}))
    s["parcels"] = s["parcels"].fillna(0)
    s["sat_ha"] = s["sat_ha"].fillna(0.0)
    s["conflicted_area_ha"] = s["conflicted_area_ha"].fillna(0.0)
    s["satellite_share"] = s.sat_ha / s.groupby("village").sat_ha.transform("sum")

    m = r.merge(s, on=["village", "crop"], how="outer")
    for col in ["registry_ha", "registry_share", "sat_ha", "satellite_share", "parcels",
                "conflicted_area_ha"]:
        m[col] = m[col].fillna(0.0)
    m["delta_share"] = m.satellite_share - m.registry_share
    m["abs_delta_share"] = m.delta_share.abs()
    # Attribute the village's registry hectares in proportion to how much the
    # satellite over- or under-calls that crop — the operationally meaningful figure.
    village_reg_ha = m.groupby("village").registry_ha.transform("sum")
    m["implied_ha_delta"] = (m.delta_share * village_reg_ha).round(1)
    m = m.sort_values("abs_delta_share", ascending=False).round(4)

    # --- village-name integrity ---------------------------------------------
    reg_v, our_v = set(r.village), set(s.village)
    ev["villages_registry_only"] = sorted(reg_v - our_v)
    ev["villages_ours_only"] = sorted(our_v - reg_v)
    ev["villages_matched"] = len(reg_v & our_v)
    if ev["villages_registry_only"] or ev["villages_ours_only"]:
        print("WARNING village name mismatch:",
              ev["villages_registry_only"], ev["villages_ours_only"])

    m.to_parquet(OUT, index=False)

    top = m[m.registry_ha + m.sat_ha > 0].head(12)
    ev["largest_divergences"] = top[
        ["village", "crop", "registry_share", "satellite_share", "delta_share",
         "registry_ha", "implied_ha_delta", "mean_confidence"]].to_dict("records")
    ev["mean_abs_delta_share"] = round(float(m.abs_delta_share.mean()), 4)
    ev["crops_compared"] = classes
    ev["n_rows"] = len(m)

    # Which crop does satellite systematically over- or under-call, taluk-wide?
    bias = (m.groupby("crop")[["registry_share", "satellite_share"]].mean()
            .assign(bias=lambda d: d.satellite_share - d.registry_share)
            .sort_values("bias").round(4))
    ev["systematic_bias_by_crop"] = bias.reset_index().to_dict("records")

    # Which attribution does the registry actually support? This is the evidence
    # behind the claim that the boundary file, not the survey, is in error.
    def mean_abs_delta(name_col):
        t = audit[audit.y_pred.isin(classes)].assign(v=audit[name_col])
        ss = (crop_area(t, "y_pred", ["v"]).set_index(["v", "y_pred"])["area_ha"]
              .unstack(fill_value=0))
        ss = ss.div(ss.sum(axis=1), axis=0)
        rr = (reg[reg.in_scope].groupby(["village", "crop"]).area_ha.sum()
              .unstack(fill_value=0))
        rr = rr.div(rr.sum(axis=1), axis=0)
        idx, cols = rr.index.intersection(ss.index), rr.columns.intersection(ss.columns)
        diff = (ss.loc[idx, cols] - rr.loc[idx, cols]).abs()
        vis = [i for i in idx if "Viswanathaperi" in str(i)]
        return (round(float(diff.values.mean()), 4),
                round(float(diff.loc[vis].values.mean()), 4) if vis else None)

    all_rec, vis_rec = mean_abs_delta("village_recorded")
    all_poly, vis_poly = mean_abs_delta("village_polygon")
    # Independent geometric evidence: recorded code x containing polygon, pair only.
    pair_df = fs[fs.village_code.isin(PAIR) | fs.village_spatial.isin(PAIR)]
    xt = pd.crosstab(pair_df.village_code, pair_df.village_spatial)
    pair_geometry = {
        "polygon_names": {str(c): code_to_name.get(c) for c in PAIR},
        "records_by_recorded_code_x_containing_polygon": {
            str(rc): {str(pc): int(xt.loc[rc, pc]) if rc in xt.index and pc in xt.columns
                      else 0 for pc in PAIR} for rc in PAIR},
        "n_records_all_villages_code_ne_polygon": int(
            (fs.village_code != fs.village_spatial).sum()),
        "n_records_all_villages": int(len(fs)),
    }
    ev["attribution_test"] = {
        "by_recorded_code": {"mean_abs_delta_share_all": all_rec,
                             "viswanathaperi_pair": vis_rec},
        "by_polygon_membership": {"mean_abs_delta_share_all": all_poly,
                                  "viswanathaperi_pair": vis_poly},
        "pair_geometry": pair_geometry,
        "scope_note": ("The Viswanathaperi pair figures are a two-village subset; the "
                       "all-village figures are the taluk-wide comparison. Do not quote "
                       "the pair gap as if it were taluk-wide."),
        "conclusion": (
            "The registry is compiled from the recorded village codes, so its "
            "agreement with them is expected by construction and cannot show which "
            "attribution is correct. The only independent evidence is geometric: "
            "every record coded " + str(PAIR[1]) + " falls inside polygon Part-1 of "
            + "/".join(map(str, PAIR)) + " (counts per recorded code by containing "
            "polygon are in pair_geometry). That points to a boundary or labelling "
            "error in the supplied layer but does not prove it; it needs cadastral "
            "or field confirmation from FarmwiseAI."),
    }

    (EVIDENCE / "p7_registry.json").write_text(json.dumps(ev, indent=2, default=str))
    provenance.record(
        OUT, classification="DERIVED",
        source="TN Agrisnet village-wise Digital Crop Survey report joined to KAVAL "
               "satellite predictions",
        licence="Derived; registry source carries no stated licence (public "
                "government statistics, attributed to TN Agrisnet)",
        produced_by="KAVAL/scripts/p7_registry_comparison.py",
        temporal_extent=SEASON,
        transform="crop-share comparison per village, renormalised over the five "
                  "evaluable classes",
        inputs=["KAVAL/data/raw/tn_crop_registry.csv",
                "KAVAL/data/derived/audit.parquet"],
        notes=INDEPENDENCE_NOTE, agent="verification-economics")

    print(json.dumps({k: v for k, v in ev.items()
                      if k not in ("largest_divergences",)}, indent=2, default=str))
    print("\nLargest divergences:")
    print(top[["village", "crop", "registry_share", "satellite_share",
               "delta_share", "implied_ha_delta"]].to_string(index=False))


if __name__ == "__main__":
    main()
