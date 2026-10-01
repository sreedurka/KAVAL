"""
KAVAL / Phase 5 — Multiple-Instance Learning over capture-event bags.

Trained on the SAME capture-event-grouped folds as Phase 4, so the comparison
against the per-parcel baselines is fair. Different folds would make it meaningless.

Produces:
  * per-parcel predictions from a bag-supervised model
  * `bag_support` — size-normalised attention per parcel, the audit signal Phase 6
    consumes
  * the honest verdict on whether MIL beats the baseline, in either direction

Run:  .venv/bin/python KAVAL/scripts/p5_mil.py
Out:  docs/evidence/p5_mil.{json,md}, data/derived/mil_predictions.parquet
"""

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")
from kaval import provenance  # noqa: E402
from kaval.config import (DERIVED, EVIDENCE, GSE_BANDS, HEADLINE_REGIME,  # noqa: E402
                          KEY_BAG, KEY_PARCEL, SEASONAL_BANDS, SEED)
from kaval.mil import bag_support, predict, train_mil  # noqa: E402
from kaval.splits import make_splits  # noqa: E402

STORE = DERIVED / "feature_store.parquet"
OOF = DERIVED / "oof_predictions.parquet"
OUT = DERIVED / "mil_predictions.parquet"
FEATURES = GSE_BANDS + SEASONAL_BANDS


def main():
    provenance.require(STORE)
    df = pd.read_parquet(STORE)
    df = df[df.has_features].reset_index(drop=True)
    y = df["y"].values
    classes = np.unique(y)
    cls_idx = {c: i for i, c in enumerate(classes)}
    y_idx = np.array([cls_idx[v] for v in y])
    bags = df[KEY_BAG].values

    # Identical folds to Phase 4 — same regime, same seed, same splitter.
    splits = make_splits(df, HEADLINE_REGIME, y)
    print(f"{len(df):,} parcels · {df[KEY_BAG].nunique():,} bags · "
          f"{len(splits)} folds (regime {HEADLINE_REGIME})")

    # Rice is 63% of parcels. Without reweighting the bag loss the model collapses
    # onto it and the attention signal becomes uninformative.
    counts = np.bincount(y_idx, minlength=len(classes)).astype(float)
    weights = (counts.sum() / (len(classes) * counts))

    inst_proba = np.full((len(df), len(classes)), np.nan)
    support = np.full(len(df), np.nan)
    fold_bag_acc = []

    for k, (tr, te) in enumerate(splits, 1):
        scaler = StandardScaler().fit(df.loc[tr, FEATURES].values)
        Xtr = scaler.transform(df.loc[tr, FEATURES].values)
        Xte = scaler.transform(df.loc[te, FEATURES].values)

        model = train_mil(Xtr, y_idx[tr], bags[tr], len(classes),
                          class_weight=weights, seed=SEED + k)
        p_inst, attn, bag_proba, ptr, order = predict(model, Xte, bags[te])
        inst_proba[te] = p_inst
        support[te] = bag_support(attn, bags[te])

        # Bag-level accuracy: one prediction per capture event, which is the unit
        # the label was actually observed at.
        bag_true = [y_idx[te][order[ptr[i]]] for i in range(len(ptr) - 1)]
        fold_bag_acc.append(accuracy_score(bag_true, bag_proba.argmax(1)))
        print(f"  fold {k}: bag acc={fold_bag_acc[-1]:.4f}")

    assert not np.isnan(inst_proba).any()
    pred = classes[inst_proba.argmax(1)]

    ev = {"regime": HEADLINE_REGIME, "folds": len(splits),
          "n_parcels": len(df), "n_bags": int(df[KEY_BAG].nunique()),
          "classes": list(classes),
          "mil_parcel_accuracy": float(accuracy_score(y, pred)),
          "mil_parcel_macro_f1": float(f1_score(y, pred, average="macro")),
          "mil_bag_accuracy": float(np.mean(fold_bag_acc)),
          "mil_bag_accuracy_std": float(np.std(fold_bag_acc))}

    # ---- honest comparison against the Phase 4 baseline -------------------
    base = pd.read_parquet(provenance.require(OOF))[[KEY_PARCEL, "y_true", "y_pred", "confidence_raw"]]
    merged = df[[KEY_PARCEL]].merge(base, on=KEY_PARCEL, how="left")
    assert (merged.y_true.values == y).all(), "baseline rows misaligned"
    ev["baseline_parcel_accuracy"] = float(accuracy_score(y, merged.y_pred))
    ev["baseline_parcel_macro_f1"] = float(f1_score(y, merged.y_pred, average="macro"))
    ev["delta_accuracy_pp"] = round(
        100 * (ev["mil_parcel_accuracy"] - ev["baseline_parcel_accuracy"]), 2)
    ev["delta_macro_f1"] = round(
        ev["mil_parcel_macro_f1"] - ev["baseline_parcel_macro_f1"], 4)
    ev["mil_beats_baseline"] = bool(ev["delta_macro_f1"] > 0)

    # ---- is the attention signal real? ------------------------------------
    # The claim Phase 6 depends on: low-support parcels should be the ones the
    # satellite disagrees with. If that link is absent, bag_support is noise and
    # must not be weighted in the Record Trust Score.
    out = pd.DataFrame({
        KEY_PARCEL: df[KEY_PARCEL].values, KEY_BAG: bags,
        "bag_size": df.bag_size.values, "y_true": y, "mil_pred": pred,
        "mil_confidence": inst_proba.max(1), "bag_support": support})
    out["agrees_with_survey"] = out.mil_pred == out.y_true

    # Measured two ways. Against MIL's OWN prediction the check is partly
    # self-referential: bag_support is this model's attention weight, and attention
    # is the mechanism that produced the prediction, so the model partly agrees with
    # itself. The honest test uses the INDEPENDENTLY trained Phase 4 baseline, which
    # never saw the attention weights. We report both.
    out["agrees_baseline"] = merged.y_pred.values == y
    multi = out[out.bag_size > 1]
    lo = multi.bag_support < multi.bag_support.quantile(0.25)
    ev["attention_check"] = {
        "parcels_in_multi_parcel_bags": int(len(multi)),
        "measured_against": "independent Phase 4 baseline",
        "agreement_low_support_quartile": float(multi[lo].agrees_baseline.mean()),
        "agreement_rest": float(multi[~lo].agrees_baseline.mean()),
        "self_referential_low_support_quartile": float(multi[lo].agrees_with_survey.mean()),
        "self_referential_rest": float(multi[~lo].agrees_with_survey.mean()),
    }
    ac = ev["attention_check"]
    ac["gap_pp"] = round(100 * (ac["agreement_rest"]
                                - ac["agreement_low_support_quartile"]), 2)
    ac["self_referential_gap_pp"] = round(
        100 * (ac["self_referential_rest"]
               - ac["self_referential_low_support_quartile"]), 2)
    # Gating uses the independent figure, never the flattering one.
    ac["signal_is_informative"] = bool(ac["gap_pp"] > 2.0)

    for i, c in enumerate(classes):
        out[f"mil_p_{c}"] = inst_proba[:, i]
    out.to_parquet(OUT, index=False)

    (EVIDENCE / "p5_mil.json").write_text(json.dumps(ev, indent=2, default=str))
    write_markdown(ev)
    provenance.record(
        OUT, classification="DERIVED",
        source="Attention-MIL over capture-event bags",
        licence="Derived", produced_by="KAVAL/scripts/p5_mil.py",
        inputs=["KAVAL/data/derived/feature_store.parquet",
                "KAVAL/data/derived/oof_predictions.parquet"],
        transform=f"gated-attention MIL, {len(splits)}-fold regime {HEADLINE_REGIME}, "
                  "identical folds to Phase 4",
        notes="bag_support is attention normalised by bag size: 1.0 = average support, "
              "<1 = passenger parcel.",
        agent="mil-modeler")
    print(json.dumps(ev, indent=2, default=str))


def write_markdown(ev):
    a = ev["attention_check"]
    verdict = ("MIL improves on the per-parcel baseline."
               if ev["mil_beats_baseline"] else
               "**MIL does not beat the per-parcel baseline on macro F1.** Reported as a "
               "negative result, per plan.md §11 rule 6. The attention signal is "
               "evaluated separately below and retains audit value regardless.")
    sig = ("The signal is informative and is weighted in the Record Trust Score."
           if a["signal_is_informative"] else
           "**The gap is too small to treat as a signal.** `bag_support` must not be "
           "weighted in the Record Trust Score on this evidence.")
    L = [
        "# Phase 5 — Multiple-Instance Learning over capture-event bags\n",
        f"Regime {ev['regime']}, {ev['folds']} folds, identical to Phase 4. "
        f"{ev['n_parcels']:,} parcels in {ev['n_bags']:,} bags.\n",
        "## Does modelling the bag structure help?\n",
        "| Model | Parcel accuracy | Parcel macro F1 |", "|---|---:|---:|",
        f"| Phase 4 baseline (per-parcel) | {ev['baseline_parcel_accuracy']:.1%} "
        f"| {ev['baseline_parcel_macro_f1']:.3f} |",
        f"| Attention-MIL (bag-supervised) | {ev['mil_parcel_accuracy']:.1%} "
        f"| {ev['mil_parcel_macro_f1']:.3f} |",
        f"| **Difference** | **{ev['delta_accuracy_pp']:+.2f} pp** "
        f"| **{ev['delta_macro_f1']:+.4f}** |", "",
        f"Bag-level accuracy (one prediction per capture event, the unit the label was "
        f"actually observed at): **{ev['mil_bag_accuracy']:.1%}** "
        f"± {ev['mil_bag_accuracy_std']:.3f}.", "", verdict, "",
        "## Is the attention signal real?\n",
        "The claim Phase 6 depends on: parcels the model attends to least should be "
        "the ones the satellite disagrees with. If not, `bag_support` is noise.\n",
        "Measured against the **independently trained Phase 4 baseline**, which never "
        "saw the attention weights. Measuring against MIL's own prediction would be "
        "partly self-referential, since attention is what produced that prediction — "
        "the inflated figure is shown alongside so the difference is visible.\n",
        "| Group (multi-parcel bags only) | vs independent baseline | vs MIL's own |",
        "|---|---:|---:|",
        f"| Lowest-support quartile | {a['agreement_low_support_quartile']:.1%} "
        f"| {a['self_referential_low_support_quartile']:.1%} |",
        f"| Remaining three quartiles | {a['agreement_rest']:.1%} "
        f"| {a['self_referential_rest']:.1%} |",
        f"| **Gap** | **{a['gap_pp']:+.2f} pp** | {a['self_referential_gap_pp']:+.2f} pp |",
        "", sig, "",
        f"The self-referential measurement overstates the gap by "
        f"{a['self_referential_gap_pp'] - a['gap_pp']:+.1f} pp. Gating uses the "
        "independent figure.", "",
        "`bag_support` is attention normalised by bag size, so it measures support "
        "rather than bag size: 1.0 is average support within the bag, below 1.0 marks "
        "a parcel the model treats as a passenger.",
    ]
    (EVIDENCE / "p5_mil.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
