"""
KAVAL / Phase 6 — Trust, calibration and verification economics.

Turns model output into the decisions the product actually ships:

  1. calibrated confidence (cross-fitted isotonic, ECE before and after)
  2. P(the declared label is wrong)  — confident learning
  3. Record Trust Score, with published weights
  4. agreement status per parcel
  5. the budget-routed field worklist, against a random-visit counterfactual
  6. the auto-clear list and its surveyor-day saving

Run:  .venv/bin/python KAVAL/scripts/p6_audit.py
Out:  data/derived/audit.parquet, docs/evidence/p6_audit.{json,md}
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
from kaval.audit import (agreement_status, expected_calibration_error,  # noqa: E402
                         fit_calibrator, label_error_probability, route_budget,
                         trust_score)
from kaval.config import (DERIVED, EVIDENCE, HEADLINE_REGIME, INTERIM,  # noqa: E402
                          KEY_BAG, KEY_PARCEL, SEED, THRESHOLDS, VISIT_COST)

STORE = DERIVED / "feature_store.parquet"
OOF = DERIVED / "oof_predictions.parquet"
MIL = DERIVED / "mil_predictions.parquet"
P5_EV = EVIDENCE / "p5_mil.json"
OUT = DERIVED / "audit.parquet"


def cross_fitted_calibration(conf, correct, bags, seed=SEED):
    """
    Two-fold, bag-grouped isotonic calibration.

    Every parcel gets a calibrated confidence from a calibrator fitted on capture
    events it did not belong to, so the reported ECE is an out-of-fit measurement
    rather than a restatement of the fit.
    """
    rng = np.random.default_rng(seed)
    uniq = np.unique(bags)
    half = set(rng.choice(uniq, size=len(uniq) // 2, replace=False))
    side = np.array([b in half for b in bags])

    out = np.full(len(conf), np.nan)
    for mask in (side, ~side):
        cal = fit_calibrator(conf[~mask], correct[~mask])
        out[mask] = cal.predict(conf[mask])
    assert not np.isnan(out).any()
    return out


def main():
    provenance.require(STORE)
    provenance.require(OOF)

    store = pd.read_parquet(STORE)
    oof = pd.read_parquet(OOF)
    df = oof.merge(
        store[[KEY_PARCEL, "bag_size", "photo_distance_m", "mixed_crop",
               "stage_plausibility", "heterogeneity", "geometry_source",
               "area_m2", "village_name", "village_code_mismatch", "crop_stage",
               "lat", "lon",
               # Phase 2 geometry provenance: where this parcel's boundary came
               # from, and whether the satellite sees it as its own field or as
               # part of a larger farmed unit. The API surfaces these in the
               # audit trail, so they have to survive into audit.parquet.
               "field_id", "snap_m", "parcels_sharing_field", "field_area_m2"]],
        on=KEY_PARCEL, how="left", validate="one_to_one")
    # Survey number and subdivision identify the parcel to a field officer, so the
    # worklist is useless without them. They live on the canonical record table
    # rather than the feature store.
    records = pd.read_parquet(provenance.require(INTERIM / "records.parquet"))
    df = df.merge(records[[KEY_PARCEL, "survey_no", "subdivision"]],
                  on=KEY_PARCEL, how="left", validate="one_to_one")
    assert df["survey_no"].notna().all(), "worklist rows must be locatable in the field"

    ev = {"n_parcels": len(df), "n_bags": int(df[KEY_BAG].nunique()),
          "split_regime": HEADLINE_REGIME, "thresholds": THRESHOLDS}

    # ---- 1. calibration ---------------------------------------------------
    correct = (df.y_pred == df.y_true).to_numpy(float)
    raw = df.confidence_raw.to_numpy(float)
    df["confidence_calibrated"] = cross_fitted_calibration(raw, correct, df[KEY_BAG].values)

    ev["calibration"] = {
        "method": "two-fold bag-grouped isotonic, cross-fitted",
        "ece_raw": expected_calibration_error(raw, correct),
        "ece_calibrated": expected_calibration_error(df.confidence_calibrated, correct),
        "mean_confidence_raw": float(raw.mean()),
        "mean_confidence_calibrated": float(df.confidence_calibrated.mean()),
        "actual_accuracy": float(correct.mean()),
    }
    c = ev["calibration"]
    c["ece_improvement"] = round(c["ece_raw"] - c["ece_calibrated"], 4)

    # ---- 2. confident learning -------------------------------------------
    classes = sorted(c_ for c_ in df.y_true.unique())
    pcols = [f"p_{c_}" for c_ in classes]
    proba = df[pcols].to_numpy(float)
    y_idx = np.array([classes.index(v) for v in df.y_true])
    # The model's own measured accuracy caps how much its disagreement is worth.
    model_accuracy = float(correct.mean())
    p_wrong, is_err, best_alt = label_error_probability(
        proba, y_idx, classes, model_accuracy=model_accuracy)
    df["p_label_wrong"] = p_wrong
    df["is_candidate_label_error"] = is_err
    df["suggested_crop"] = [classes[i] if i >= 0 else None for i in best_alt]

    ev["confident_learning"] = {
        "model_accuracy_used_as_cap": model_accuracy,
        "candidate_label_errors": int(is_err.sum()),
        "pct_of_records": round(100 * is_err.mean(), 2),
        "mean_p_label_wrong": float(p_wrong.mean()),
        "by_declared_crop": df[df.is_candidate_label_error].y_true.value_counts().to_dict(),
    }

    # ---- 3. Record Trust Score -------------------------------------------
    # bag_support only enters if Phase 5 demonstrated it is informative. Wiring the
    # negative result into the product, rather than only reporting it.
    use_support = False
    if MIL.exists() and P5_EV.exists():
        p5 = json.loads(P5_EV.read_text())
        use_support = bool(p5.get("attention_check", {}).get("signal_is_informative"))
        if use_support:
            mil = pd.read_parquet(provenance.require(MIL))[[KEY_PARCEL, "bag_support"]]
            df = df.merge(mil, on=KEY_PARCEL, how="left", validate="one_to_one")
    ev["bag_support_used_in_trust"] = use_support
    ev["bag_support_reason"] = (
        "Phase 5 attention signal is informative" if use_support else
        "Phase 5 attention signal not demonstrated informative, or Phase 5 not yet run; "
        "bag_support is excluded and its weight redistributed")

    df["trust_score"], comps, weights = trust_score(df, use_bag_support=use_support)
    ev["trust_weights_applied"] = weights
    ev["trust_components_mean"] = {k: round(float(v.mean()), 4) for k, v in comps.items()}
    ev["trust_score_deciles"] = {
        str(q): round(float(df.trust_score.quantile(q / 10)), 4) for q in range(11)}
    # Trust is meant to describe the RECORD, independently of whether the model
    # agrees with it. bag_support is model-derived, so measure how much trust leaks
    # model agreement, with and without it. Published in doc 08; it was once only prose.
    agree = (df.y_pred == df.y_true).astype(float)
    ev["trust_vs_agreement_r"] = {
        "with_bag_support": round(float(np.corrcoef(df.trust_score, agree)[0, 1]), 4),
        "without_bag_support": round(float(np.corrcoef(
            trust_score(df, use_bag_support=False)[0], agree)[0, 1]), 4),
        "note": "Pearson r between trust_score and (y_pred == y_true). Near zero means "
                "trust is largely independent of model agreement.",
    }

    # ---- 4. agreement status ---------------------------------------------
    df["agreement_status"] = agreement_status(df)
    ev["agreement_status_counts"] = df.agreement_status.value_counts().to_dict()
    ev["agreement_status_area_ha"] = (
        df.groupby("agreement_status").area_m2.sum().div(1e4).round(1).to_dict())

    # ---- 5. verification economics ---------------------------------------
    budgets = [100, 250, 500, 1000, 2000]
    ev["budget_curve"] = [route_budget(df, b, seed=SEED) for b in budgets]
    ev["visit_cost_assumption"] = VISIT_COST

    # ---- 6. auto-clear ----------------------------------------------------
    cleared = df[df.agreement_status == "CONFIRMED"]
    per_day = VISIT_COST["parcels_per_surveyor_day"]
    ev["auto_clear"] = {
        "parcels": int(len(cleared)),
        "pct_of_parcels": round(100 * len(cleared) / len(df), 1),
        "area_ha": round(float(cleared.area_m2.sum()) / 1e4, 1),
        "surveyor_days_saved_per_season": round(len(cleared) / per_day, 1),
        "baseline_surveyor_days": round(len(df) / per_day, 1),
        "assumption": VISIT_COST["note"],
    }
    # NOT a validity check: CONFIRMED is DEFINED as the model agreeing with the
    # survey, so "accuracy within CONFIRMED" is 100% by construction and says
    # nothing. What we can honestly estimate is the residual risk — how often
    # auto-clearing would be wrong because model and surveyor are wrong TOGETHER —
    # which the calibrated confidence bounds.
    ev["auto_clear"]["accuracy_within_confirmed_is_tautological"] = True
    ev["auto_clear"]["expected_residual_error_rate"] = (
        float(1.0 - cleared.confidence_calibrated.mean()) if len(cleared) else None)
    ev["auto_clear"]["expected_parcels_wrongly_cleared"] = (
        float((1.0 - cleared.confidence_calibrated).sum()) if len(cleared) else None)
    ev["auto_clear"]["residual_note"] = (
        "Auto-clearing fails only when the satellite and the surveyor err in the "
        "SAME way. That quantity is UNIDENTIFIED from this data: the calibrator was "
        "fitted against the declared label, so 1 - calibrated confidence estimates the "
        "probability of an event CONFIRMED already conditions on. It is offered as a "
        "rough proxy, NOT a bound, and can only be settled by an independent field "
        "audit of a CONFIRMED sample.")

    df.to_parquet(OUT, index=False)
    (EVIDENCE / "p6_audit.json").write_text(json.dumps(ev, indent=2, default=str))
    write_markdown(ev)
    provenance.record(
        OUT, classification="DERIVED",
        source="Phase 4 out-of-fold predictions plus Phase 3 trust signals",
        licence="Derived", produced_by="KAVAL/scripts/p6_audit.py",
        inputs=["KAVAL/data/derived/oof_predictions.parquet",
                "KAVAL/data/derived/feature_store.parquet"],
        transform="cross-fitted isotonic calibration; confident learning; Record Trust "
                  "Score; agreement status; budget routing",
        notes=f"{len(df):,} parcels with calibrated confidence, trust score and "
              "agreement status.",
        agent="calibration-trust")
    print(json.dumps(ev, indent=2, default=str))


def write_markdown(ev):
    c, cl, ac = ev["calibration"], ev["confident_learning"], ev["auto_clear"]
    b = ev["budget_curve"]
    L = ["# Phase 6 — Trust, Calibration and Verification Economics\n",
         f"{ev['n_parcels']:,} parcels · {ev['n_bags']:,} capture events · "
         f"split regime `{ev['split_regime']}`\n",
         "## 1. Calibration\n",
         f"Method: {c['method']}. Every parcel is calibrated by a model fitted on "
         "capture events it did not belong to, so ECE is measured out-of-fit.\n",
         "| | Raw | Calibrated |", "|---|---:|---:|",
         f"| Expected Calibration Error | {c['ece_raw']:.4f} | **{c['ece_calibrated']:.4f}** |",
         f"| Mean confidence | {c['mean_confidence_raw']:.3f} | {c['mean_confidence_calibrated']:.3f} |",
         f"| Actual accuracy | {c['actual_accuracy']:.3f} | {c['actual_accuracy']:.3f} |",
         "",
         f"ECE improves by {c['ece_improvement']:.4f}. Raw confidence "
         + ("overstates" if c["mean_confidence_raw"] > c["actual_accuracy"] else "understates")
         + " accuracy.", "",
         "## 2. Label-error detection\n",
         f"**{cl['candidate_label_errors']:,} records ({cl['pct_of_records']}%)** are "
         "candidate label errors — the satellite confidently prefers a different crop "
         "than the surveyor declared.\n",
         f"`p_label_wrong` is discounted by the model's own measured accuracy "
         f"({cl['model_accuracy_used_as_cap']:.3f}), because a model that is right "
         f"{cl['model_accuracy_used_as_cap']:.0%} of the time cannot assert more than "
         "that about anyone else's label. Mean "
         f"`p_label_wrong` = {cl['mean_p_label_wrong']:.4f}.\n",
         "| Declared crop | Candidate errors |", "|---|---:|"]
    for k, v in sorted(cl["by_declared_crop"].items(), key=lambda x: -x[1]):
        L.append(f"| {k} | {v:,} |")
    L += ["", "> These are disagreements, not errors. Which side is right is what the "
              "field visit determines.", "",
          "## 3. Record Trust Score\n",
          f"Weights applied (bag_support {'included' if ev['bag_support_used_in_trust'] else 'excluded'} "
          f"— {ev['bag_support_reason']}):\n",
          "| Component | Weight | Mean score |", "|---|---:|---:|"]
    for k, w in ev["trust_weights_applied"].items():
        L.append(f"| `{k}` | {w:.3f} | {ev['trust_components_mean'].get(k, float('nan')):.3f} |")
    # Computed, not asserted: this line once claimed geometry_source was constant
    # (all Voronoi) long after AI-1 had delineated most parcels.
    g = ev["trust_components_mean"].get("geometry_source")
    L += ["", f"> `geometry_source` mean score {g:.3f}: parcels on their own delineated "
              "field score highest, shared fields lower, Voronoi fallback lowest."
              if g is not None else "> `geometry_source` not scored.", "",
          "## 4. Agreement status\n",
          "| Status | Parcels | Area (ha) |", "|---|---:|---:|"]
    for k, v in sorted(ev["agreement_status_counts"].items(), key=lambda x: -x[1]):
        L.append(f"| `{k}` | {v:,} | {ev['agreement_status_area_ha'].get(k, 0):,.1f} |")
    L += ["", "> `CONFIRMED` requires high trust; `DISPUTED` does not. We are "
              "deliberately conservative about clearing a parcel and liberal about "
              "flagging one, which inflates DISPUTED relative to CONFIRMED.", "",
          "## 5. Verification targeting\n",
          f"The base disagreement rate is **{b[0]['base_disagreement_rate']:.1%}** — "
          f"{b[0]['total_disagreements_available']:,} of {ev['n_parcels']:,} parcels "
          "carry a satellite prediction differing from the declared crop. A random "
          "visit lands on one that often; a routed visit essentially always does.\n",
          "| Budget | % of parcels | Routed hits | Random expected | Targeting |",
          "|---:|---:|---:|---:|---:|"]
    for x in b:
        L.append(f"| {x['budget']:,} | {x['pct_of_parcels_visited']}% "
                 f"| {x['routed_disagreements_found']:,} "
                 f"| {x['random_disagreements_expected']:.0f} "
                 f"| {x['targeting_efficiency']:.2f}x |")
    L += ["", "**Read this honestly.** Targeting efficiency is pinned to "
              f"1 / {b[0]['base_disagreement_rate']:.3f} = "
              f"{1/b[0]['base_disagreement_rate']:.2f}x at most, by construction: it reaches that cap whenever every "
              "routed parcel is a disagreement. It measures coverage, not "
              "ranking quality, and it establishes nothing about which side of a "
              "disagreement is correct. Any classifier can enumerate its own "
              "disagreements; the operational value is that only "
              f"{b[0]['base_disagreement_rate']:.1%} of parcels need looking at.", ""]
    if b[0].get("routed_mean_confidence"):
        L += ["The part that is *not* pinned — does the ranking put better-evidenced "
              "disagreements first?\n",
              "| | Mean calibrated confidence |", "|---|---:|",
              f"| Routed (budget {b[0]['budget']}) | {b[0]['routed_mean_confidence']:.3f} |",
              f"| All disagreements | {b[0]['all_disagreements_mean_confidence']:.3f} |", ""]
    L += [f"Model-estimated corrections, shown separately because they are an estimate "
          f"rather than a count: {b[2]['estimated_corrections_routed']:.0f} routed versus "
          f"{b[2]['estimated_corrections_random']:.0f} random at budget {b[2]['budget']}.", "",
          "## 6. Auto-clear\n",
          f"**{ac['parcels']:,} parcels ({ac['pct_of_parcels']}%)** are `CONFIRMED` — "
          "satellite and survey agree at high calibrated confidence on a record we "
          "trust. These need not be revisited next season.\n",
          f"- Area: {ac['area_ha']:,.1f} ha",
          f"- Surveyor-days saved per season: **{ac['surveyor_days_saved_per_season']:,.1f}** "
          f"of a {ac['baseline_surveyor_days']:,.1f}-day baseline",
          f"- Rough residual-risk proxy: {ac['expected_residual_error_rate']:.1%} "
          f"(~{ac['expected_parcels_wrongly_cleared']:.0f} parcels)", "",
          "> Accuracy *within* the auto-cleared set is 100% by construction — "
          "`CONFIRMED` is defined as the model agreeing with the survey — so it is not "
          "reported. " + ac["residual_note"], "",
          f"> Cost assumption: {ac['assumption']}"]
    (EVIDENCE / "p6_audit.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
