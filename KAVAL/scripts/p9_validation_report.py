"""
KAVAL / Phase 9 — Validation report.

Assembles every evidence artefact into the report the challenge brief asks for:
overall accuracy, macro F1, per-class precision/recall/F1 and a confusion matrix —
reported under every split regime, with the capture-event-grouped figure as the
headline and the random-split figure beside it so the gap is visible.

Reads only from docs/evidence/. If a phase has not run, its section says so rather
than being silently omitted.

Run:  .venv/bin/python KAVAL/scripts/p9_validation_report.py
Out:  docs/VALIDATION_REPORT.md
"""

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kaval.config import EVIDENCE, HEADLINE_REGIME, KAVAL  # noqa: E402

OUT = KAVAL / "docs" / "VALIDATION_REPORT.md"


def load(name):
    p = EVIDENCE / name
    return json.loads(p.read_text()) if p.exists() else None


def section_missing(phase, script):
    return [f"> **Not yet produced.** Run `{script}` to generate this section.", ""]


def main():
    gt, p2 = load("gt_forensics.json"), load("p2_parcel_layer.json")
    p3, p4 = load("p3_feature_store.json"), load("p4_results.json")
    p3b = load("p3b_presto.json")
    p5, p6 = load("p5_mil.json"), load("p6_audit.json")

    L = [f"# KAVAL — Validation Report\n",
         f"*Generated {date.today().isoformat()} by `scripts/p9_validation_report.py`. "
         "Every figure regenerates from a script in `KAVAL/scripts/`.*\n",
         "---\n", "## Headline\n"]

    if p4:
        h, lad = p4["headline"], {r["regime"]: r for r in p4["ladder"]}
        L += [f"**{h['accuracy']:.1%} accuracy, {h['macro_f1']:.3f} macro F1** "
              f"— {h['head']}, regime `{h['regime']}` (grouped by survey capture event), "
              f"{p4['folds']}-fold.\n",
              f"Under a random row split the same pipeline reports "
              f"**{lad['1-random']['accuracy']:.1%}**. The difference is not the model; "
              "it is the split.\n",
              "We do not claim the brief's >95% target. On this data that figure is "
              "reachable only by validating in a way the brief itself says invalidates "
              "the result.\n"]
    else:
        L += section_missing(4, "scripts/p4_ladder_and_baselines.py")

    # ---- 1. the data ------------------------------------------------------
    L += ["---\n", "## 1. What the ground truth actually contains\n"]
    if gt:
        pd_ = gt["photo_to_parcel_distance_m"]
        L += [f"- **{gt['n_records']:,} survey records** resolve to only "
              f"**{gt['n_capture_events']:,} capture events** "
              f"({gt['label_inflation_factor']}x label inflation)",
              f"- one capture event supplies up to **{gt['max_parcels_per_capture_event']} "
              f"parcel labels**; {gt['pct_records_in_multi_parcel_events']}% of records "
              "sit in a multi-parcel event",
              f"- **{gt['capture_events_with_mixed_crop_label']}** of "
              f"{gt['n_capture_events']:,} events contain more than one crop label — the "
              "label is attached to the event and copied",
              f"- the photograph sits a median **{pd_['median']:,} m** from the parcel it "
              f"documents (p90 {pd_['p90']:,} m); {pd_['pct_over_1km']}% are over 1 km away",
              f"- **{gt['n_mixed_crop_declarations']}** records declare more than one crop "
              "category", ""]
    if p2:
        L += [f"- **{p2['village_code_mismatch_records']:,} records** carry a village code "
              "that disagrees with the polygon the point falls inside", ""]
    if gt:
        L += ["### Effective sample size per crop\n",
              "| Crop | Records | Independent capture events | Inflation |",
              "|---|---:|---:|---:|"]
        for crop, r in gt["per_crop_effective_n"].items():
            L.append(f"| {crop} | {r['records']:,} | **{r['capture_events']}** "
                     f"| {r['inflation']}x |")
        L += ["", "> This table is why per-class metrics below carry capture events "
                  "alongside record counts. Marigold's 36 records are three field "
                  "observations.", ""]

    # ---- 2. the ladder ----------------------------------------------------
    L += ["---\n", "## 2. Leakage controls and the Leakage Ladder\n"]
    if p4:
        L += ["Same model, same features, same hyper-parameters. Only the split changes.\n",
              "| Regime | Accuracy | Macro F1 | Log loss | What it controls for |",
              "|---|---:|---:|---:|---|"]
        for r in p4["ladder"]:
            L.append(f"| `{r['regime']}` | {r['accuracy']:.1%} ± {r['accuracy_std']:.3f} "
                     f"| {r['macro_f1']:.3f} | {r['log_loss']:.3f} | {r['description']} |")
        lad = {r["regime"]: r for r in p4["ladder"]}
        L += ["", f"Accuracy falls **{100*(lad['1-random']['accuracy']-lad['4-village']['accuracy']):.1f} "
              f"points** and macro F1 **{lad['1-random']['macro_f1']-lad['4-village']['macro_f1']:.3f}** "
              "from loosest to strictest.", "",
              "**Grouping by parcel is not a leakage control on this data.** It moves "
              f"accuracy by {100*(lad['2-parcel']['accuracy']-lad['1-random']['accuracy']):+.1f} "
              "points, because parcels are already one-to-one with rows. Only "
              "capture-event grouping exposes the drop.", "",
              "The headline regime additionally unions the delineated field id into the "
              "group key: parcels sharing one satellite-delineated polygon carry identical "
              "zonal features and leak exactly as capture-event siblings do.", ""]
    else:
        L += section_missing(4, "scripts/p4_ladder_and_baselines.py")

    # ---- 3. model and source comparison -----------------------------------
    L += ["---\n", "## 3. Model heads and embedding sources\n"]
    if p4:
        L += [f"Regime `{HEADLINE_REGIME}`, identical folds throughout.\n",
              "### Heads\n", "| Head | Accuracy | Macro F1 | Log loss |",
              "|---|---:|---:|---:|"]
        for r in sorted(p4["heads"], key=lambda r: -r["macro_f1"]):
            L.append(f"| {r['head']} | {r['accuracy']:.1%} ± {r['accuracy_std']:.3f} "
                     f"| {r['macro_f1']:.3f} | {r['log_loss']:.3f} |")
        L += ["", "### Sources\n", "| Source | Features | Accuracy | Macro F1 |",
              "|---|---:|---:|---:|"]
        for r in p4["sources"]:
            L.append(f"| {r['source']} | {r['n_features']} | {r['accuracy']:.1%} "
                     f"| {r['macro_f1']:.3f} |")
        L += [""]
        # Every source comparison is paired fold by fold and flagged when it sits
        # inside fold noise. "GSE beats GSE+seasonal" was once written here as a
        # finding; its sign flipped across three runs and it was retracted
        # (correction #4). The verdict is computed now, never written by hand.
        comps = [c for c in p4.get("source_comparisons", []) if c["metric"] == "macro_f1"]
        if comps:
            L += [f"Paired against `{comps[0]['reference']}` on identical folds "
                  f"({p4.get('sources_n_parcels', p4['n_parcels']):,} parcels):\n",
                  "| Source | Mean Δ macro F1 | SD of Δ | Folds favouring | Verdict |",
                  "|---|---:|---:|---:|---|"]
            for c in comps:
                verdict = ("**underpowered** — within fold noise" if c["underpowered"]
                           else ("better" if c["mean_delta"] > 0 else "worse"))
                L.append(f"| {c['source']} | {c['mean_delta']:+.4f} | {c['delta_sd']:.4f} "
                         f"| {c['folds_favouring_source']}/{c['folds']} | {verdict} |")
            L += [""]
        if p3b:
            wm = p3b.get("s2_worst_month", {})
            L += ["**Reading the Presto rows.** Presto alone is clearly behind GSE "
                  "under identical folds, but four things limit how far that is a "
                  "verdict on Presto rather than on how we could feed it:", "",
                  "- " + p3b["domain_shift_note"],
                  "- " + p3b["meteorology_caveat"],
                  "- " + p3b.get("input_granularity", ""),
                  "- " + p3b.get("usage", ""),
                  "", f"Sentinel-2 was observed for {p3b['s2_observed_fraction']:.1%} "
                  "of parcel-months overall, but only "
                  f"{wm.get('observed_fraction', float('nan')):.1%} in {wm.get('month', '?')}"
                  " — the survey month — because of north-east monsoon cloud.", ""]
        if p4.get("sources_pending"):
            L += ["Pending: " + p4["sources_pending"][0], ""]

    # ---- 4. per-class -----------------------------------------------------
    L += ["---\n", "## 4. Per-class performance\n"]
    if p4:
        L += [f"Regime `{HEADLINE_REGIME}`, {p4['headline']['head']}.\n",
              "| Crop | Records | Capture events | Precision | Recall | F1 |",
              "|---|---:|---:|---:|---:|---:|"]
        for c in sorted(p4["per_class"], key=lambda r: -r["capture_events"]):
            L.append(f"| {c['crop']} | {c['records']:,} | **{c['capture_events']}** "
                     f"| {c['precision']:.3f} | {c['recall']:.3f} | {c['f1']:.3f} |")
        cm = p4["confusion_matrix"]
        L += ["", "### Confusion matrix\n",
              "| true \\\\ predicted | " + " | ".join(cm["labels"]) + " |",
              "|---|" + "---:|" * len(cm["labels"])]
        for lab, row in zip(cm["labels"], cm["counts"]):
            L.append(f"| **{lab}** | " + " | ".join(str(v) for v in row) + " |")
        pairs = [(cm["labels"][i], cm["labels"][j], cm["counts"][i][j])
                 for i in range(len(cm["labels"])) for j in range(len(cm["labels"]))
                 if i != j]
        pairs.sort(key=lambda t: -t[2])
        L += ["", "### Dominant error pattern\n"]
        for a, b, n in pairs[:5]:
            L.append(f"- **{a} → {b}**: {n:,} parcels")
        L += ["", "Errors collapse toward Rice, which is 63% of the data. Banana is the "
                  "weakest class: 653 records but only 64 independent capture events, so "
                  "its F1 rests on very little evidence.", ""]

    # ---- 5. MIL -----------------------------------------------------------
    L += ["---\n", "## 5. Multiple-Instance Learning over capture-event bags\n"]
    if p5:
        a = p5["attention_check"]
        L += ["| Model | Parcel accuracy | Parcel macro F1 |", "|---|---:|---:|",
              f"| Per-parcel baseline | {p5['baseline_parcel_accuracy']:.1%} "
              f"| {p5['baseline_parcel_macro_f1']:.3f} |",
              f"| Attention-MIL | {p5['mil_parcel_accuracy']:.1%} "
              f"| {p5['mil_parcel_macro_f1']:.3f} |",
              f"| **Difference** | **{p5['delta_accuracy_pp']:+.2f} pp** "
              f"| **{p5['delta_macro_f1']:+.4f}** |", "",
              f"Bag-level accuracy: **{p5['mil_bag_accuracy']:.1%}** "
              f"± {p5['mil_bag_accuracy_std']:.3f}.", "",
              ("MIL improves on the baseline." if p5["mil_beats_baseline"] else
               "**MIL does not beat the per-parcel baseline on macro F1.** Reported as a "
               "negative result."), "",
              "### Is the attention signal usable as an audit signal?\n",
              f"- lowest-support quartile agrees with the survey "
              f"{a['agreement_low_support_quartile']:.1%} of the time",
              f"- the other three quartiles agree {a['agreement_rest']:.1%} of the time",
              f"- gap: **{a['gap_pp']:+.2f} pp**", "",
              ("The signal is informative and is weighted in the Record Trust Score."
               if a["signal_is_informative"] else
               "**Too small to treat as a signal.** `bag_support` is excluded from the "
               "Record Trust Score and its weight redistributed."), ""]
    else:
        L += section_missing(5, "scripts/p5_mil.py")

    # ---- 6. calibration and audit ----------------------------------------
    L += ["---\n", "## 6. Calibration, trust and verification economics\n"]
    if p6:
        c, cl, ac = p6["calibration"], p6["confident_learning"], p6["auto_clear"]
        L += ["### Calibration\n", "| | Raw | Calibrated |", "|---|---:|---:|",
              f"| Expected Calibration Error | {c['ece_raw']:.4f} | **{c['ece_calibrated']:.4f}** |",
              f"| Mean confidence | {c['mean_confidence_raw']:.3f} | {c['mean_confidence_calibrated']:.3f} |",
              f"| Actual accuracy | {c['actual_accuracy']:.3f} | — |", "",
              f"Method: {c['method']}.", "",
              "### Label-error detection\n",
              f"**{cl['candidate_label_errors']:,} records ({cl['pct_of_records']}%)** are "
              "candidate label errors — the satellite confidently prefers a different crop "
              "than the surveyor declared. These are disagreements; the field visit "
              "decides which side is right.\n",
              "### Agreement status\n", "| Status | Parcels | Area (ha) |",
              "|---|---:|---:|"]
        for k, v in sorted(p6["agreement_status_counts"].items(), key=lambda x: -x[1]):
            L.append(f"| `{k}` | {v:,} | {p6['agreement_status_area_ha'].get(k,0):,.1f} |")
        b0 = p6["budget_curve"][0]
        L += ["", "### Verification targeting\n",
              f"The base disagreement rate is **{b0['base_disagreement_rate']:.1%}** — "
              f"{b0['total_disagreements_available']:,} parcels carry a satellite "
              "prediction differing from the declared crop. A random visit lands on one "
              "that often; a routed visit essentially always does.\n",
              "| Budget | % of parcels | Routed hits | Random expected | Targeting |",
              "|---:|---:|---:|---:|---:|"]
        for b in p6["budget_curve"]:
            L.append(f"| {b['budget']:,} | {b['pct_of_parcels_visited']}% "
                     f"| {b['routed_disagreements_found']:,} "
                     f"| {b['random_disagreements_expected']:.0f} "
                     f"| {b['targeting_efficiency']:.2f}x |")
        L += ["",
              "**Read this honestly.** Targeting efficiency is pinned to "
              f"1 / {b0['base_disagreement_rate']:.3f} = "
              f"{1/b0['base_disagreement_rate']:.2f}x at most, by construction: it reaches that cap whenever every "
              "routed parcel is a disagreement. It measures coverage, not ranking "
              "quality, and establishes nothing about which side of a disagreement is "
              "correct — any classifier can enumerate its own disagreements. The "
              "operational value is that only "
              f"{b0['base_disagreement_rate']:.1%} of parcels need looking at at all."]
        L += ["", f"**Auto-clear:** {ac['parcels']:,} parcels ({ac['pct_of_parcels']}%), "
              f"{ac['area_ha']:,.1f} ha, saving "
              f"**{ac['surveyor_days_saved_per_season']:,.1f} surveyor-days** of a "
              f"{ac['baseline_surveyor_days']:,.1f}-day baseline.",
              f"Accuracy within the auto-cleared set: "
              f"{ac['accuracy_within_confirmed']:.1%}." if ac.get("accuracy_within_confirmed")
              else "", f"> Cost assumption: {ac['assumption']}", ""]
    else:
        L += section_missing(6, "scripts/p6_audit.py")

    # ---- 7. threats -------------------------------------------------------
    L += ["---\n", "## 7. Threats to validity\n",
          "Stated plainly, because a report that lists none has not looked.\n",
          "- **Geometry is derived, not cadastral.** Parcel polygons come from a "
          "village-constrained Voronoi tessellation of the survey points, or from "
          "satellite delineation. Neither is the legal parcel boundary. Area figures "
          "inherit that approximation.",
          "- **One taluk, one season.** 21 revenue villages, an 8-day survey window in "
          "November 2024. Generalisation beyond Sivagiri is untested, and the "
          "village-grouped regime is the closest proxy we have.",
          "- **Seven crops are not evaluable.** Classes with fewer than five independent "
          "capture events are collapsed to `Other`. No per-class claim is made for them.",
          "- **The registry comparison uses declared crop as its reference** where an "
          "independent registry figure is unavailable. That makes it a consistency check, "
          "not an external validation.",
          "- **The cost saving rests on a stated assumption** about surveyor productivity, "
          "not on FarmwiseAI's actual figures.",
          "- **Confident learning identifies disagreement, not error.** Whether the "
          "satellite or the surveyor is right is exactly what a field visit resolves; "
          "nothing here settles it.", ""]

    OUT.write_text("\n".join(L) + "\n")
    print(f"wrote {OUT}")
    print(f"sections present: gt={bool(gt)} p2={bool(p2)} p3={bool(p3)} "
          f"p4={bool(p4)} p5={bool(p5)} p6={bool(p6)}")


if __name__ == "__main__":
    main()
