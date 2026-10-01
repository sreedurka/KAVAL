---
name: audit-signals
description: Definitions of KAVAL's Record Trust Score components, agreement statuses and the verification-budget objective. Load when implementing or changing trust scoring, flagging, the field worklist, auto-clear logic, or the agreement vocabulary. Triggers: "trust score", "agreement status", "confidence", "flag", "worklist", "verification", "auto-clear", "disputed", "audit".
---

# Audit Signals

KAVAL's output vocabulary. Keep these definitions in one place; the API, the frontend
and the agentic analyst must all use the same words with the same meanings.

## Record Trust Score

A score in [0,1] describing how much we trust the **survey record**, computed
independently of whether the model agrees with it. Components:

| Signal | Source | Direction |
|---|---|---|
| `bag_size` | parcels sharing this capture event (1–43) | larger → less trust |
| `photo_distance_m` | photo geolocation → parcel centroid | farther → less trust |
| `bag_support` | attention weight from the MIL head (AI-3) | lower → less trust |
| `stage_plausibility` | is declared stage consistent with crop and survey date | implausible → less trust |
| `mixed_crop_flag` | `;` in `rabi_crop_classification` | present → less trust |
| `geometry_source` | delineated polygon vs buffered-point fallback | fallback → less trust |
| `within_parcel_heterogeneity` | std of embedding across the parcel | higher → less trust |

Combine with documented weights. **Publish the weights.** A trust score nobody can
interrogate is not an audit.

## Agreement status

Assigned per parcel from (model prediction, calibrated confidence, survey label, trust score).

| Status | Condition | Action |
|---|---|---|
| `CONFIRMED` | model agrees with survey, calibrated confidence ≥ high threshold, trust ≥ threshold | Auto-clear — skip next season's field visit |
| `DISPUTED` | model disagrees, calibrated confidence ≥ high threshold | Top of the field worklist |
| `UNCERTAIN` | calibrated confidence below threshold | Route by remaining budget |
| `UNVERIFIABLE` | trust score below floor (huge bag, distant photo, mixed crop) | Re-survey the **record**, not the parcel |
| `UNSEEN` | no survey record | Satellite-only prediction, no audit claim |

Thresholds are configuration, not magic numbers. Put them in one config file, expose
them in the UI, and show how the worklist changes when they move.

## Verification budget objective

Given a budget of N field visits, choose the N parcels maximising **expected corrections**:

```
expected_correction(parcel) = P(survey label is wrong) × area_weight
```

where `P(survey label is wrong)` comes from confident learning (AI-4) combined with
calibrated model disagreement, and `area_weight` reflects that a wrong label on a large
parcel distorts the crop-area statistic more.

Report the counterfactual: how many corrections would N *random* visits find? The gap is
the value KAVAL adds, and it is the number that justifies the system.

## Never

- Use raw model confidence where calibrated confidence is meant. They are different
  numbers and the routing depends on the difference.
- Describe a parcel as "wrong". The survey record and the satellite disagree; which is
  right is what the field visit determines.
- Hard-code a threshold in more than one place.
