"""
KAVAL / Phase 4 — The Leakage Ladder, model heads, and embedding sources.

Three experiments, all on the Phase 3 feature store, all with the split named:

  A. THE LADDER      one model, four split regimes. The headline evidence.
  B. HEADS           LightGBM / RandomForest / logistic / MLP, identical folds.
  C. SOURCES         GSE / seasonal / GSE+seasonal / Presto / GSE+Presto,
                     identical rows and folds, compared pair-wise.

Also produces out-of-fold predicted probabilities under the headline regime, which
Phase 6 needs for confident learning and calibration. Those must come from a
leakage-free split or every downstream trust signal inherits the leak.

Run:  .venv/bin/python KAVAL/scripts/p4_ladder_and_baselines.py
Out:  docs/evidence/p4_*.json/.md, data/derived/oof_predictions.parquet
"""

import json
import sys
import warnings
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold, StratifiedGroupKFold
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix, f1_score, log_loss)
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")
from kaval import provenance  # noqa: E402
from kaval.config import (DERIVED, EVIDENCE, GSE_BANDS, HEADLINE_REGIME,  # noqa: E402
                          KEY_BAG, KEY_PARCEL, LGBM_PARAMS, N_FOLDS,
                          SEASONAL_BANDS, SEED, SPLIT_REGIMES)
from kaval.splits import (describe, effective_n, headline_groups,  # noqa: E402
                          make_splits)

STORE = DERIVED / "feature_store.parquet"
PRESTO = DERIVED / "presto_embeddings.parquet"
OOF = DERIVED / "oof_predictions.parquet"
ALL_FEATURES = GSE_BANDS + SEASONAL_BANDS


def heads():
    """Model heads compared on identical folds. Scaling only where it matters."""
    return {
        "LightGBM": lambda: lgb.LGBMClassifier(random_state=SEED, **LGBM_PARAMS),
        "RandomForest": lambda: RandomForestClassifier(
            n_estimators=400, n_jobs=8, random_state=SEED, min_samples_leaf=2),
        "LogisticRegression": lambda: make_pipeline(
            StandardScaler(), LogisticRegression(max_iter=2000, random_state=SEED)),
        "MLP": lambda: make_pipeline(
            StandardScaler(),
            MLPClassifier(hidden_layer_sizes=(256, 128), max_iter=400,
                          early_stopping=True, random_state=SEED)),
    }


def run_cv(df, X, y, regime, make_model, collect_proba=False, splits=None):
    """
    One model, one regime. Returns fold metrics and optionally OOF probabilities.

    `splits` is only for labelled diagnostics that are deliberately NOT a regime
    (see group_structure_diagnostic); every reported regime goes through make_splits.
    """
    if splits is None:
        splits = make_splits(df, regime, y)
    accs, f1s, lls = [], [], []
    classes = np.unique(y)
    oof = np.full((len(y), len(classes)), np.nan) if collect_proba else None

    for tr, te in splits:
        model = make_model()
        model.fit(X[tr], y[tr])
        pred = model.predict(X[te])
        accs.append(accuracy_score(y[te], pred))
        f1s.append(f1_score(y[te], pred, average="macro"))
        proba = model.predict_proba(X[te])
        # Align fold classes to the global class list — a fold can miss a rare class.
        idx = [list(classes).index(c) for c in model.classes_]
        full = np.zeros((len(te), len(classes)))
        full[:, idx] = proba
        lls.append(log_loss(y[te], full, labels=classes))
        if collect_proba:
            oof[te] = full

    out = dict(
        regime=regime,
        accuracy=float(np.mean(accs)), accuracy_std=float(np.std(accs)),
        macro_f1=float(np.mean(f1s)), macro_f1_std=float(np.std(f1s)),
        log_loss=float(np.mean(lls)), folds=len(splits),
        # Per-fold scores, so two configurations on identical folds can be compared
        # pair-wise rather than by eyeballing two means.
        fold_accuracy=[float(a) for a in accs], fold_macro_f1=[float(f) for f in f1s])
    return (out, oof, classes) if collect_proba else (out, None, classes)


def paired_comparisons(rows, reference):
    """
    Each source against `reference`, fold by fold. The folds are identical, so the
    per-fold difference is the honest effect; its SD says whether the effect is
    distinguishable from fold-to-fold noise. We retracted one comparison (GSE vs
    GSE+seasonal) whose sign flipped across runs, so this is now computed, not judged.
    """
    ref = next(r for r in rows if r["source"] == reference)
    out = []
    for r in rows:
        if r["source"] == reference:
            continue
        for metric in ("macro_f1", "accuracy"):
            d = np.array(r[f"fold_{metric}"]) - np.array(ref[f"fold_{metric}"])
            sd = float(d.std(ddof=1)) if len(d) > 1 else float("nan")
            out.append({
                "source": r["source"], "reference": reference, "metric": metric,
                "mean_delta": float(d.mean()), "delta_sd": sd,
                "folds_favouring_source": int((d > 0).sum()), "folds": len(d),
                "reference_fold_sd": float(ref[f"{metric}_std"]),
                # Under ~1 fold SD, the handoff rule: call it underpowered.
                "underpowered": bool(abs(d.mean()) < max(sd, ref[f"{metric}_std"]))})
    return out


def event_only_splits(df, y):
    """
    DIAGNOSTIC ONLY — not a split regime, never a headline. Groups by capture event
    (bag_id) alone, WITHOUT the delineated-field union the headline regime applies,
    so the effect of that union on fold variance can be measured. Same splitter,
    N_FOLDS and SEED as kaval.splits.make_splits, and the same no-overlap check.
    """
    groups = df[KEY_BAG].to_numpy()
    try:
        splitter = StratifiedGroupKFold(N_FOLDS, shuffle=True, random_state=SEED)
        splits = list(splitter.split(np.zeros(len(df)), y, groups))
    except ValueError:
        splits = list(GroupKFold(N_FOLDS).split(np.zeros(len(df)), y, groups))
    for tr, te in splits:
        overlap = set(groups[tr]) & set(groups[te])
        if overlap:
            raise RuntimeError(f"event-only diagnostic: {len(overlap)} bags in both "
                               "train and test")
    return splits


def group_structure(df, X, y):
    """
    How much the field-id union coarsens the headline groups, and what that does to
    fold variance. Sources the '2,921 bags -> 2,269 components' and 'fold SD' figures.
    """
    comp = headline_groups(df)
    n_bags = int(df[KEY_BAG].nunique())
    n_comp = int(len(np.unique(comp)))
    sizes = pd.Series(comp).value_counts()
    largest = sizes.index[0]
    gs = {
        "n_bags": n_bags,
        "n_components": n_comp,
        "pct_groups_lost": round(100 * (1 - n_comp / n_bags), 2),
        "largest_component_parcels": int(sizes.iloc[0]),
        "largest_component_bags": int(df.loc[comp == largest, KEY_BAG].nunique()),
        "field_id_present": bool("field_id" in df.columns),
        "definition": "n_components = distinct splits.headline_groups (capture event "
                      "unioned with delineated field_id via union-find) over the "
                      "parcels with features.",
    }
    r, _, _ = run_cv(df, X, y, "diagnostic_event_only_no_field_union",
                     heads()["LightGBM"], splits=event_only_splits(df, y))
    r["description"] = ("DIAGNOSTIC, not a split regime and never a headline: grouped "
                        "by bag_id only, no field-id union. Same head, features, "
                        f"splitter, {N_FOLDS} folds and SEED as regime {HEADLINE_REGIME}.")
    gs["diagnostic_event_only_no_field_union"] = r
    return gs


def main():
    provenance.require(STORE)
    df = pd.read_parquet(STORE)
    df = df[df.has_features].reset_index(drop=True)
    X_all = df[ALL_FEATURES].values
    y = df["y"].values
    print(f"{len(df):,} parcels with features · {df[KEY_BAG].nunique():,} bags")

    ev = {"n_parcels": len(df), "n_bags": int(df[KEY_BAG].nunique()),
          "n_villages": int(df.village_spatial.nunique()),
          "n_features": len(ALL_FEATURES), "folds": N_FOLDS,
          "classes": pd.Series(y).value_counts().to_dict()}

    # ---- A. THE LADDER ----------------------------------------------------
    print("\nA. Leakage ladder")
    ladder = []
    for regime in SPLIT_REGIMES:
        r, _, _ = run_cv(df, X_all, y, regime, heads()["LightGBM"])
        r["description"] = describe(regime)
        ladder.append(r)
        print(f"  {regime:12} acc={r['accuracy']:.4f}  macroF1={r['macro_f1']:.4f}")
    ev["ladder"] = ladder

    # ---- A2. group structure + event-only diagnostic ----------------------
    print("\nA2. Group structure (diagnostic, not a regime)")
    ev["group_structure"] = group_structure(df, X_all, y)
    gsd = ev["group_structure"]["diagnostic_event_only_no_field_union"]
    print(f"  bags={ev['group_structure']['n_bags']:,} -> components="
          f"{ev['group_structure']['n_components']:,}  event-only diagnostic "
          f"acc={gsd['accuracy']:.4f}±{gsd['accuracy_std']:.4f}  "
          f"macroF1={gsd['macro_f1']:.4f}")

    # ---- B. HEADS, on the headline regime ---------------------------------
    print(f"\nB. Model heads (regime {HEADLINE_REGIME})")
    head_rows = []
    for name, mk in heads().items():
        r, _, _ = run_cv(df, X_all, y, HEADLINE_REGIME, mk)
        r["head"] = name
        head_rows.append(r)
        print(f"  {name:20} acc={r['accuracy']:.4f}  macroF1={r['macro_f1']:.4f}")
    ev["heads"] = head_rows
    best = max(head_rows, key=lambda r: r["macro_f1"])
    ev["best_head"] = best["head"]

    # ---- C. FEATURE SOURCES ----------------------------------------------
    # GSE vs Presto is the comparison the brief asks for. Every source is scored
    # on the SAME rows and the SAME folds: if Presto is missing for some parcels,
    # the GSE rows are restricted to match, never the other way round silently.
    print(f"\nC. Feature sources (regime {HEADLINE_REGIME}, {best['head']})")
    sources = {
        "GSE only (64-d)": GSE_BANDS,
        "Seasonal S1/S2 only (12)": SEASONAL_BANDS,
        "GSE + seasonal (76)": ALL_FEATURES,
    }
    src_df = df
    if PRESTO.exists():
        provenance.require(PRESTO)
        pr = pd.read_parquet(PRESTO)
        p_cols = [c for c in pr.columns if c != KEY_PARCEL]
        src_df = df.merge(pr, on=KEY_PARCEL, how="inner").reset_index(drop=True)
        sources.update({
            f"Presto ({len(p_cols)}-d)": p_cols,
            f"GSE + Presto ({64 + len(p_cols)})": GSE_BANDS + p_cols,
        })
        ev["sources_pending"] = []
    else:
        ev["sources_pending"] = ["Presto embeddings — requires the NASA Harvest checkpoint "
                                 "run over per-parcel Sentinel time series (Phase 1)."]
    ev["sources_n_parcels"] = len(src_df)
    ev["sources_n_dropped_no_presto"] = len(df) - len(src_df)
    y_src = src_df["y"].values
    src_rows = []
    for name, cols in sources.items():
        r, _, _ = run_cv(src_df, src_df[cols].values, y_src, HEADLINE_REGIME,
                         heads()[best["head"]])
        r["source"] = name
        r["n_features"] = len(cols)
        src_rows.append(r)
        print(f"  {name:26} acc={r['accuracy']:.4f}  macroF1={r['macro_f1']:.4f}")
    ev["sources"] = src_rows
    ev["source_comparisons"] = paired_comparisons(src_rows, "GSE only (64-d)")

    # ---- OOF probabilities for Phase 6 ------------------------------------
    print(f"\nD. Out-of-fold probabilities (regime {HEADLINE_REGIME}, {best['head']})")
    _, oof, classes = run_cv(df, X_all, y, HEADLINE_REGIME,
                             heads()[best["head"]], collect_proba=True)
    assert not np.isnan(oof).any(), "every parcel must receive an out-of-fold prediction"
    pred = classes[oof.argmax(1)]
    out = pd.DataFrame({
        KEY_PARCEL: df[KEY_PARCEL].values, KEY_BAG: df[KEY_BAG].values,
        "village_spatial": df.village_spatial.values,
        "y_true": y, "y_pred": pred, "confidence_raw": oof.max(1)})
    for i, c in enumerate(classes):
        out[f"p_{c}"] = oof[:, i]
    out.to_parquet(OOF, index=False)

    # ---- per-class metrics with effective n (metrics-report skill) --------
    rep = classification_report(y, pred, output_dict=True, zero_division=0)
    eff = effective_n(df)
    per_class = []
    for c in classes:
        per_class.append({
            "crop": c,
            "records": int(eff.loc[c, "records"]),
            "capture_events": int(eff.loc[c, "capture_events"]),
            "precision": rep[c]["precision"], "recall": rep[c]["recall"],
            "f1": rep[c]["f1-score"], "support": int(rep[c]["support"])})
    ev["per_class"] = per_class
    ev["confusion_matrix"] = {"labels": list(classes),
                              "counts": confusion_matrix(y, pred, labels=classes).tolist()}
    ev["headline"] = {
        "regime": HEADLINE_REGIME, "head": best["head"],
        "accuracy": best["accuracy"], "macro_f1": best["macro_f1"]}

    (EVIDENCE / "p4_results.json").write_text(json.dumps(ev, indent=2, default=str))
    write_markdown(ev)
    provenance.record(
        OOF, classification="DERIVED",
        source=f"Out-of-fold predictions, {best['head']}, regime {HEADLINE_REGIME}",
        licence="Derived", produced_by="KAVAL/scripts/p4_ladder_and_baselines.py",
        # p4 §C reads the Presto embeddings for the source comparison.
        inputs=["KAVAL/data/derived/feature_store.parquet",
                "KAVAL/data/derived/presto_embeddings.parquet"],
        transform=f"{N_FOLDS}-fold capture-event-grouped cross-validation",
        notes="Leakage-free out-of-fold probabilities. Phase 6 calibration and "
              "confident learning depend on this being regime-3, not random.",
        agent="leakage-auditor")
    print(f"\nwrote {EVIDENCE/'p4_results.md'}")


def group_structure_md(ev, lad):
    g = ev.get("group_structure")
    if not g:
        return []
    d = g["diagnostic_event_only_no_field_union"]
    h = lad[HEADLINE_REGIME]
    return [
        f"The headline regime unions capture events with delineated fields: "
        f"{g['n_bags']:,} bags collapse to {g['n_components']:,} components "
        f"({g['pct_groups_lost']:.1f}% of groups lost); the largest component spans "
        f"{g['largest_component_parcels']} parcels across "
        f"{g['largest_component_bags']} bags.\n",
        "| Grouping | Accuracy | Macro F1 |", "|---|---:|---:|",
        f"| Diagnostic: bag_id only, no field union (not a regime) "
        f"| {d['accuracy']:.1%} ± {d['accuracy_std']:.3f} | {d['macro_f1']:.3f} |",
        f"| Regime {HEADLINE_REGIME} (bag_id ∪ field_id, headline) "
        f"| {h['accuracy']:.1%} ± {h['accuracy_std']:.3f} | {h['macro_f1']:.3f} |",
        "", "LightGBM, all features, identical splitter settings. ± is the SD "
        "across the 5 folds.\n"]


def write_markdown(ev):
    L = ["# Phase 4 — Leakage Ladder, Heads and Sources\n",
         f"{ev['n_parcels']:,} parcels · {ev['n_bags']:,} capture events · "
         f"{ev['n_villages']} villages · {ev['n_features']} features · "
         f"{ev['folds']}-fold\n",
         "## A. The Leakage Ladder\n",
         "Same model, same features, same hyper-parameters. Only the split changes.\n",
         "| Regime | Accuracy | Macro F1 | Log loss | What it controls for |",
         "|---|---:|---:|---:|---|"]
    for r in ev["ladder"]:
        L.append(f"| {r['regime']} | {r['accuracy']:.1%} ± {r['accuracy_std']:.3f} "
                 f"| {r['macro_f1']:.3f} | {r['log_loss']:.3f} | {r['description']} |")
    lad = {r["regime"]: r for r in ev["ladder"]}
    gap_a = 100 * (lad["1-random"]["accuracy"] - lad["4-village"]["accuracy"])
    gap_f = lad["1-random"]["macro_f1"] - lad["4-village"]["macro_f1"]
    L += ["", f"Accuracy falls **{gap_a:.1f} points** and macro F1 falls **{gap_f:.3f}** "
              "from the loosest regime to the strictest, with no change to the model.", ""]
    d = 100 * (lad["2-parcel"]["accuracy"] - lad["1-random"]["accuracy"])
    L += [f"Grouping by parcel — the obvious control — moves accuracy by {d:+.1f} points. "
          "It is not protection. Only capture-event grouping exposes the drop.\n",
          "### Group structure behind regime 3\n",
          *group_structure_md(ev, lad),
          "## B. Model heads\n",
          f"Regime {HEADLINE_REGIME}, identical folds.\n",
          "| Head | Accuracy | Macro F1 | Log loss |", "|---|---:|---:|---:|"]
    for r in sorted(ev["heads"], key=lambda r: -r["macro_f1"]):
        L.append(f"| {r['head']} | {r['accuracy']:.1%} ± {r['accuracy_std']:.3f} "
                 f"| {r['macro_f1']:.3f} | {r['log_loss']:.3f} |")
    L += ["", "## C. Feature sources\n",
          f"Regime {HEADLINE_REGIME}, {ev['best_head']}, identical folds.\n",
          "| Source | Features | Accuracy | Macro F1 |", "|---|---:|---:|---:|"]
    for r in ev["sources"]:
        L.append(f"| {r['source']} | {r['n_features']} | {r['accuracy']:.1%} "
                 f"| {r['macro_f1']:.3f} |")
    if ev.get("sources_n_dropped_no_presto"):
        L += ["", f"Scored on the {ev['sources_n_parcels']:,} parcels that have every "
                  f"source ({ev['sources_n_dropped_no_presto']} without Presto input "
                  "excluded from all rows alike), so the folds are identical."]
    if ev.get("source_comparisons"):
        L += ["", "### Paired against GSE only, fold by fold\n",
              "| Source | Metric | Mean Δ | SD of Δ | Folds favouring | Verdict |",
              "|---|---|---:|---:|---:|---|"]
        for c in ev["source_comparisons"]:
            verdict = ("underpowered — within fold noise" if c["underpowered"]
                       else ("better" if c["mean_delta"] > 0 else "worse"))
            L.append(f"| {c['source']} | {c['metric']} | {c['mean_delta']:+.4f} "
                     f"| {c['delta_sd']:.4f} | {c['folds_favouring_source']}/{c['folds']} "
                     f"| {verdict} |")
    if ev["sources_pending"]:
        L += ["", "Pending: " + ev["sources_pending"][0]]
    L += ["", "## D. Per-class performance\n",
          f"Regime {HEADLINE_REGIME}, {ev['best_head']}. **Capture events, not record "
          "count, is the honest sample size.**\n",
          "| Crop | Records | Capture events | Precision | Recall | F1 |",
          "|---|---:|---:|---:|---:|---:|"]
    for c in sorted(ev["per_class"], key=lambda r: -r["capture_events"]):
        L.append(f"| {c['crop']} | {c['records']:,} | **{c['capture_events']}** "
                 f"| {c['precision']:.3f} | {c['recall']:.3f} | {c['f1']:.3f} |")
    L += ["", "> Classes with few independent capture events have metrics with very wide "
              "error bars. The `Other` class aggregates seven crops that individually "
              "have between 1 and 4 capture events; no per-class claim is made for them.",
          "", "## Confusion matrix\n",
          "| true \\\\ pred | " + " | ".join(ev["confusion_matrix"]["labels"]) + " |",
          "|---|" + "---:|" * len(ev["confusion_matrix"]["labels"])]
    for lab, row in zip(ev["confusion_matrix"]["labels"], ev["confusion_matrix"]["counts"]):
        L.append(f"| **{lab}** | " + " | ".join(str(v) for v in row) + " |")
    (EVIDENCE / "p4_results.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
