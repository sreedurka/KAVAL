"""
KAVAL — RETIRED. Superseded by scripts/p4_ladder_and_baselines.py.

This was the Phase 0 proof-of-concept, written before kaval/config.py and
kaval/splits.py existed. It carries its own SEED, its own LightGBM parameters and
GroupKFold rather than StratifiedGroupKFold, so its numbers differ slightly from
the canonical ladder and it does not honour the leakage protocol in splits.py.

Kept for provenance of the Phase 0 measurements quoted in the project history.
Do NOT cite its output; cite docs/evidence/p4_results.json.

--- original docstring follows ---

KAVAL / Phase 4 — The Leakage Ladder.

Holds the model, the features and the hyper-parameters fixed, and varies ONLY
the cross-validation split. Demonstrates that the headline accuracy of a crop
classifier on this dataset is mostly a property of the split, not the model.

Split regimes, weakest to strongest control:
  1. random    — stratified row-wise k-fold (the default most teams reach for)
  2. parcel    — grouped by parcel id
  3. event     — grouped by survey capture event (image_path)
  4. village   — grouped by village (spatial hold-out)

Writes docs/evidence/leakage_ladder.{json,md}.

Run:  .venv/bin/python KAVAL/scripts/leakage_ladder.py
"""

import json
import warnings
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, log_loss
from sklearn.model_selection import GroupKFold, StratifiedKFold

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
FEATS = ROOT / "CropSight/CropSight_Task3_UPGRADED/06_FEATURE_ACQUISITION/gse_plus_seasonal_features_2024.csv"
GT = ROOT / "Dataset/Ground Truth Points/Ground_truth_Points.csv"
OUT = ROOT / "KAVAL/docs/evidence"

EMB = [f"A{i:02d}" for i in range(64)]
SEAS = [f"S{s}_{b}" for s in (1, 2, 3, 4) for b in ("NDVI", "VH", "VV")]
FEATURES = EMB + SEAS
MIN_EVENTS_PER_CLASS = 5
PARAMS = dict(n_estimators=300, learning_rate=0.05, num_leaves=31, verbose=-1, n_jobs=4)
SEED = 0


def load():
    f = pd.read_csv(FEATS)
    g = pd.read_csv(GT)
    g["sub_divi_1"] = g["sub_divi_1"].fillna("").astype(str).str.strip()
    g["pid"] = (g["village__1"].astype(str) + "_" + g["survey_n_1"].astype(str)
                + "_" + g["sub_divi_1"])
    f["pid"] = f["parcel_id"].astype(str)
    keys = g.drop_duplicates("pid")[["pid", "image_path", "village__1", "final_crop_name"]]
    m = f.merge(keys, on="pid", how="inner").dropna(subset=FEATURES)

    # Collapse classes with too few INDEPENDENT observations to be evaluable.
    events = m.groupby("final_crop_name")["image_path"].nunique()
    keep = set(events[events >= MIN_EVENTS_PER_CLASS].index)
    m["y"] = np.where(m.final_crop_name.isin(keep), m.final_crop_name, "Other")
    return m


def evaluate(m, name, splits):
    accs, f1s, lls = [], [], []
    for tr, te in splits:
        clf = lgb.LGBMClassifier(random_state=SEED, **PARAMS)
        clf.fit(m.X[tr], m.y[tr])
        pred = clf.predict(m.X[te])
        accs.append(accuracy_score(m.y[te], pred))
        f1s.append(f1_score(m.y[te], pred, average="macro"))
        try:
            lls.append(log_loss(m.y[te], clf.predict_proba(m.X[te]), labels=clf.classes_))
        except ValueError:
            pass
    r = dict(
        regime=name,
        accuracy=round(float(np.mean(accs)), 4),
        accuracy_std=round(float(np.std(accs)), 4),
        macro_f1=round(float(np.mean(f1s)), 4),
        macro_f1_std=round(float(np.std(f1s)), 4),
        log_loss=round(float(np.mean(lls)), 4) if lls else None,
    )
    print(f"{name:34} acc={r['accuracy']:.4f}  macroF1={r['macro_f1']:.4f}")
    return r


class Bundle:
    pass


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    m = load()
    b = Bundle()
    b.X = m[FEATURES].values
    b.y = m["y"].values

    k = 5
    regimes = [
        ("1. Random row split", StratifiedKFold(k, shuffle=True, random_state=SEED).split(b.X, b.y)),
        ("2. Grouped by parcel", GroupKFold(k).split(b.X, b.y, m["pid"].values)),
        ("3. Grouped by capture event", GroupKFold(k).split(b.X, b.y, m["image_path"].values)),
        ("4. Grouped by village (spatial)", GroupKFold(k).split(b.X, b.y, m["village__1"].values)),
    ]
    rows = [evaluate(b, name, list(sp)) for name, sp in regimes]

    ev = dict(
        n_parcels=int(len(m)),
        n_capture_events=int(m.image_path.nunique()),
        n_villages=int(m.village__1.nunique()),
        n_features=len(FEATURES),
        model="LightGBM (identical hyper-parameters across all regimes)",
        classes=m.y.value_counts().to_dict(),
        folds=k,
        results=rows,
    )
    top, bottom = rows[0], rows[-1]
    ev["gap_random_to_event_acc_pp"] = round(100 * (rows[0]["accuracy"] - rows[2]["accuracy"]), 1)
    ev["gap_random_to_village_acc_pp"] = round(100 * (top["accuracy"] - bottom["accuracy"]), 1)
    ev["gap_random_to_village_macro_f1"] = round(top["macro_f1"] - bottom["macro_f1"], 3)
    (OUT / "leakage_ladder.json").write_text(json.dumps(ev, indent=2))

    L = ["# The Leakage Ladder\n",
         "Same model. Same features. Same hyper-parameters. **Only the split changes.**\n",
         f"LightGBM · {ev['n_features']} features "
         f"(64-d Google Satellite Embedding + 12 seasonal Sentinel-1/2) · "
         f"{ev['n_parcels']:,} parcels · {ev['folds']}-fold\n",
         "| # | Validation split | Accuracy | Macro F1 | What it leaks |",
         "|---|---|---:|---:|---|"]
    leaks = [
        "Near-duplicate parcels from the same capture event land on both sides",
        "Capture-event siblings still span the split",
        "Nothing from the same field visit — but neighbouring villages remain",
        "Nothing; the model must generalise to unseen geography",
    ]
    for r, why in zip(rows, leaks):
        L.append(f"| {r['regime'][0]} | {r['regime'][3:]} | {r['accuracy']:.1%} "
                 f"| {r['macro_f1']:.3f} | {why} |")
    L += ["",
          f"**Accuracy falls {ev['gap_random_to_village_acc_pp']} points** and "
          f"**macro F1 falls {ev['gap_random_to_village_macro_f1']}** between the loosest and "
          "the strictest regime, with no change to the model whatsoever.",
          "",
          "A team reporting row 1 and a team reporting row 4 have built the same system.",
          "Only one of them has measured it."]
    (OUT / "leakage_ladder.md").write_text("\n".join(L) + "\n")
    print("\n" + "\n".join(L))


if __name__ == "__main__":
    main()
