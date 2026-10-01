---
name: react-map-ui
description: KAVAL's React + Leaflet frontend conventions - the agreement-status colour vocabulary, map layer structure, the budget slider, and how the conversational analyst panel is wired. Load before writing or changing any frontend component, map layer, or chart. Triggers: "React", "Leaflet", "frontend", "map", "component", "UI", "dashboard", "layer", "popup", "legend".
---

# Frontend Conventions

React + TypeScript + Vite + Leaflet. The product must not read as a map with a model
behind it — the map is evidence for an audit, and the UI should say so.

## The primary colour axis is agreement status, not crop class

This is the single most important UI decision. A map coloured by crop looks like every
other crop-classification demo. Colouring by agreement status is what makes KAVAL legible
at a glance.

| Status | Role |
|---|---|
| `CONFIRMED` | calm / receding — this is the "nothing to do here" state and should not dominate |
| `DISPUTED` | the most salient colour on the map — these are the money rows |
| `UNCERTAIN` | intermediate |
| `UNVERIFIABLE` | visually distinct from `UNCERTAIN`, hatched or patterned — the problem is the record, not the parcel |
| `UNSEEN` | neutral outline, no fill |

Crop class is a **secondary, switchable** layer. Load the `dataviz` skill before choosing
the actual palette; ensure it works in light and dark and is colour-blind safe.

## Required views

1. **Audit map** — taluk, parcels by agreement status, click for the full audit trail
   (prediction, calibrated confidence, survey label, bag size, photo distance, trust components)
2. **Village audit panel** — declared vs satellite-estimated crop area, sorted by divergence
3. **Field worklist** — ranked queue with a **budget slider**: move N, watch expected
   corrections update, and see the random-baseline counterfactual beside it
4. **Leakage Ladder** — shown in-product, not hidden in a report. It is the credential.
5. **Inference demo** — the 4 villages with no ground truth, satellite-only
6. **Analyst panel** — conversational, wired to AI-5, every answer showing the parcels it cites

## Rules

1. **No hard-coded numbers.** Everything from the API (`fastapi-contract`).
2. **Every displayed metric shows its split regime.** A bare accuracy figure is a bug.
3. **Thresholds are user-movable** and the map updates live — an audit whose thresholds
   are invisible is not auditable.
4. **Popups cite provenance:** which capture event, how many siblings, how far the photo was.
5. Keep parcel geometry in a vector tile layer or simplified GeoJSON; a taluk of parcels
   will not render as raw polygons.
6. Mobile is not a target. A field officer uses the exported worklist, not this screen.
