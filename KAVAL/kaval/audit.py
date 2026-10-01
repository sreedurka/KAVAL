"""
KAVAL — the audit layer: confident learning, calibration, trust and routing.

Definitions live in the `audit-signals` skill; weights, thresholds and the
shaping constants live in config.py (`THRESHOLDS`, `TRUST_WEIGHTS`,
`TRUST_SCALES`, `AUDIT_CONSTANTS`). Nothing here hard-codes a number that moves a
published figure.
"""

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

from .config import AUDIT_CONSTANTS as K
from .config import THRESHOLDS, TRUST_SCALES, TRUST_WEIGHTS


# --------------------------------------------------------- calibration -----
def expected_calibration_error(conf, correct, n_bins=K["ece_bins"]):
    """ECE with equal-width bins. Reported alongside accuracy everywhere."""
    conf, correct = np.asarray(conf, float), np.asarray(correct, float)
    edges = np.linspace(0, 1, n_bins + 1)
    ece, n = 0.0, len(conf)
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.sum():
            ece += m.sum() / n * abs(correct[m].mean() - conf[m].mean())
    return float(ece)


def fit_calibrator(conf_fit, correct_fit):
    """
    Isotonic map from raw confidence to observed accuracy.

    Fitted on a disjoint set of capture events from the one it is evaluated on —
    fitting a calibrator is model fitting, and doing it on the evaluation set
    would manufacture the calibration it claims to measure.
    """
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    iso.fit(np.asarray(conf_fit, float), np.asarray(correct_fit, float))
    return iso


# ---------------------------------------------------- confident learning ---
def label_error_probability(proba, y_true_idx, classes, model_accuracy=None):
    """
    Cleanlab-style confident learning, implemented directly to avoid a dependency.

    Per-class thresholds are the mean self-confidence of parcels carrying that
    label. A record is a candidate label error when the model's confidence in the
    DECLARED class falls below that class's threshold while some other class
    exceeds its own. Using per-class thresholds rather than one global cut-off is
    what keeps a 63%-prevalence class like Rice from setting the bar for Banana.

    **On calling the result a probability.** The raw margin between the model's
    preferred class and the declared one is not a probability — it has no
    frequentist interpretation, and taking it at face value would let an 82%-accurate
    model assert 98% certainty that a surveyor is wrong. So the score is discounted
    by `model_accuracy`: the model's claim that a label is wrong is only worth as
    much as the model's own chance of being right. P(label wrong) <= P(model correct).
    Pass the measured accuracy for the regime the probabilities came from.

    Returns (p_label_wrong, is_candidate_error, suggested_class_idx).
    """
    proba = np.asarray(proba, float)
    n, k = proba.shape
    self_conf = proba[np.arange(n), y_true_idx]

    thresholds = np.array([
        self_conf[y_true_idx == j].mean() if (y_true_idx == j).any() else 1.0
        for j in range(k)])

    over = proba >= thresholds[None, :]           # classes confidently indicated
    over[np.arange(n), y_true_idx] = False
    best_alt = np.where(over.any(1), np.argmax(np.where(over, proba, -1), axis=1), -1)

    is_error = (self_conf < thresholds[y_true_idx]) & (best_alt >= 0)

    alt_mass = np.where(best_alt >= 0,
                        proba[np.arange(n), np.clip(best_alt, 0, k - 1)], 0.0)
    score = np.clip(alt_mass - self_conf, 0.0, 1.0)
    score = np.where(is_error, np.maximum(score, 1.0 - self_conf),
                     score * K["label_error_damping_no_candidate"])

    if model_accuracy is None:
        raise ValueError(
            "model_accuracy is required: an undiscounted margin is not a "
            "probability and must not be routed on. Pass the measured accuracy "
            "for the regime these probabilities came from.")
    p_wrong = np.clip(score * float(model_accuracy), 0.0, float(model_accuracy))
    return p_wrong, is_error, best_alt


# ---------------------------------------------------------- trust score ----
def _decay(x, saturate):
    """1.0 at zero, falling linearly to 0.0 at `saturate` and flat beyond."""
    return 1.0 - np.clip(np.asarray(x, float) / saturate, 0.0, 1.0)


# How much the parcel's geometry is worth as evidence. `ftw` means the satellite
# delineated this parcel as its own field. `ftw_shared` means several legal parcels
# occupy one physical field, so the boundary is real but the attribution to THIS
# parcel is inferred. `voronoi` is our own tessellation of the survey points.
GEOMETRY_TRUST = {"ftw": 1.0, "ftw_shared": 0.75, "ftw_ambiguous": 0.6,
                  "voronoi": 0.5, "buffer": 0.4, "buffer_no_boundary": 0.3}


def trust_components(df, use_bag_support=True):
    """
    Each component in [0,1], 1 = trustworthy. Returned separately as well as
    combined so the frontend can show *why* a record scored as it did.
    """
    c = pd.DataFrame(index=df.index)
    # A singleton bag is direct evidence; a 20+ bag carries no per-parcel evidence.
    c["bag_size"] = _decay(df["bag_size"].astype(float) - 1.0,
                           TRUST_SCALES["bag_size_saturate"])
    c["photo_distance"] = _decay(
        df["photo_distance_m"].fillna(TRUST_SCALES["photo_distance_saturate_m"]),
        TRUST_SCALES["photo_distance_saturate_m"])
    if use_bag_support and "bag_support" in df:
        # 1.0 is average support within the bag; credit saturates at 1.5.
        c["bag_support"] = np.clip(
            df["bag_support"].fillna(1.0) / K["bag_support_saturate"], 0.0, 1.0)
    c["stage_plausibility"] = (
        df["stage_plausibility"].fillna(1.0) if "stage_plausibility" in df
        else pd.Series(1.0, index=df.index))
    c["mixed_crop"] = 1.0 - df["mixed_crop"].fillna(False).astype(float)
    c["geometry_source"] = df["geometry_source"].map(GEOMETRY_TRUST).fillna(0.4)

    het = df["heterogeneity"] if "heterogeneity" in df else None
    if het is not None and het.notna().any():
        scale = het.quantile(K["heterogeneity_scale_quantile"])
        c["heterogeneity"] = 1.0 - np.clip(
            het.fillna(het.median()) / (scale if scale else 1.0), 0.0, 1.0)
    else:
        c["heterogeneity"] = 1.0
    return c


def trust_score(df, use_bag_support=True):
    """Weighted mean of the components, renormalised over those actually present."""
    c = trust_components(df, use_bag_support)
    w = {k: v for k, v in TRUST_WEIGHTS.items() if k in c.columns}
    total = sum(w.values())
    score = sum(c[k] * v for k, v in w.items()) / total
    return score.clip(0, 1), c, {k: round(v / total, 4) for k, v in w.items()}


# ------------------------------------------------------ agreement status ---
def agreement_status(df, thresholds=None):
    """
    Assign the vocabulary the whole product speaks. Order matters: a record we
    cannot verify is UNVERIFIABLE regardless of what the model thinks of it,
    because the finding is about the evidence rather than the field.
    """
    t = {**THRESHOLDS, **(thresholds or {})}
    has_record = df["y_true"].notna()
    agrees = df["y_pred"] == df["y_true"]
    conf = df["confidence_calibrated"]

    status = pd.Series("UNCERTAIN", index=df.index, dtype=object)
    status[agrees & (conf >= t["confidence_high"])
           & (df["trust_score"] >= t["trust_high"])] = "CONFIRMED"
    status[(~agrees) & (conf >= t["confidence_high"])] = "DISPUTED"
    status[df["trust_score"] < t["trust_floor"]] = "UNVERIFIABLE"
    status[~has_record] = "UNSEEN"
    return status


# --------------------------------------------------- verification budget ---
def routing_priority(df):
    """
    The routing objective, per parcel: P(label wrong) weighted by clipped relative
    area. NaN where `p_label_wrong` is missing — those parcels are never routed.

    The single definition of the ranking. `route_budget`, `/audit/worklist` and
    `/export?budget=` all call this, so the list a surveyor downloads is the
    list whose economics the API reports. The median is taken over routable
    parcels only. The worklist route used to re-implement this with the median
    over ALL parcels; identical while no parcel lacks `p_label_wrong` (true
    today, verified), but it would have split the two the moment one did.
    """
    lo, hi = K["area_weight_clip"]
    routable = df["p_label_wrong"].notna()
    median_area = df.loc[routable, "area_m2"].median() or 1.0
    area_weight = np.clip(df["area_m2"] / median_area, lo, hi)
    return (df["p_label_wrong"] * area_weight).where(routable)


def routed_worklist(df, budget):
    """The top-`budget` parcels by `routing_priority`, ranked 1..N, highest first."""
    pr = routing_priority(df)
    d = df.assign(priority=pr).dropna(subset=["priority"])
    top = d.sort_values("priority", ascending=False, kind="mergesort").head(int(budget))
    return top.assign(rank=np.arange(1, len(top) + 1))


def route_budget(df, budget, seed=0, n_draws=K["random_baseline_draws"]):
    """
    Choose `budget` parcels to visit, and report honestly what that buys.

    **What this measures, and what it does not.** Every routed visit lands on a
    parcel where the satellite disagrees with the survey; a random visit does so
    only at the base disagreement rate. That ratio is therefore pinned at
    1 / base_rate by construction and carries no information about ranking
    quality — it says only that the system can enumerate its own disagreements,
    which is true of any classifier. We report it as *targeting efficiency* and
    say so, rather than dressing it up as a lift.

    Whether a routed visit yields more TRUE corrections than a random one cannot
    be measured against labels the surveyor supplied. That needs a field audit.

    The one thing here that does reflect ranking quality is
    `routed_mean_confidence` against `all_disagreements_mean_confidence`: among
    parcels that disagree, does the ranking put the better-evidenced ones first?
    """
    d = df.dropna(subset=["p_label_wrong"])
    budget = int(min(budget, len(d)))
    if budget == 0:
        return {"budget": 0}

    routed = routed_worklist(d, budget)

    disagree = (d["y_pred"] != d["y_true"])
    base_rate = float(disagree.mean())
    routed_hits = int((routed["y_pred"] != routed["y_true"]).sum())

    rng = np.random.default_rng(seed)
    p = d["p_label_wrong"].to_numpy()
    draws = [p[rng.choice(len(p), budget, replace=False)].sum() for _ in range(n_draws)]

    conf = "confidence_calibrated"
    out = {
        "budget": budget,
        "pct_of_parcels_visited": round(100 * budget / len(d), 2),
        "routed_area_ha": float(routed["area_m2"].sum() / 1e4),

        # Targeting: countable, but pinned by construction. Labelled as such.
        "base_disagreement_rate": base_rate,
        "total_disagreements_available": int(disagree.sum()),
        "routed_disagreements_found": routed_hits,
        "random_disagreements_expected": float(budget * base_rate),
        "targeting_efficiency": float((routed_hits / budget) / max(base_rate, 1e-9)),
        "targeting_is_pinned_by_construction": True,

        # Ranking quality: the part that is NOT pinned.
        "routed_mean_confidence": (float(routed[conf].mean()) if conf in routed else None),
        "all_disagreements_mean_confidence": (
            float(d.loc[disagree, conf].mean()) if conf in d else None),

        # Model estimate, clearly separated from the countable figures.
        "estimated_corrections_routed": float(routed["p_label_wrong"].sum()),
        "estimated_corrections_random": float(np.mean(draws)),
        "estimated_corrections_random_std": float(np.std(draws)),

        "note": "targeting_efficiency is capped at 1/base_disagreement_rate, and reaches "
                "it whenever every routed parcel is a disagreement; routing by "
                "P(label wrong) x area lets a few agreeing parcels in, so it can sit "
                "just below the cap. Either way it measures "
                "coverage, not ranking quality, and establishes nothing about which "
                "side of a disagreement is correct.",
    }
    return out
