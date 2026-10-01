# KAVAL frontend — Phase 8

React + TypeScript + Vite + Leaflet. The audit surface for `KAVAL/api/main.py`.

**The map is coloured by agreement status, not by crop class.** That is the whole
point of this interface. A crop-coloured map answers "what is growing" and looks
like every other crop-classification demo; this one answers "what should a
surveyor do next". Crop class is available as a secondary, switchable layer.

---

## Run it

Node 24 (any Node ≥ 18 works).

```bash
cd KAVAL/frontend
npm install
```

### Against the live API

Start the backend first, from the repository root:

```bash
.venv/bin/uvicorn KAVAL.api.main:app --reload --port 8077
```

Then:

```bash
npm run dev            # http://localhost:5173
```

The dev server proxies `/api/*` → `http://localhost:8077` (stripping the `/api`
prefix). Point it elsewhere with `KAVAL_API=http://host:port npm run dev`. The
browser never sees an absolute API URL, so the same build runs behind any
reverse proxy.

> **Port 8077, not 8000.** Something unrelated squats on 8000 in the development
> environment and answers `/health` convincingly. The header chip now checks that
> `/health` carries `phases_available` and shows **"⚠ not the KAVAL API"** if it
> does not, so a stranger on the proxied port can never be mistaken for KAVAL.

### Without the API (mock mode)

```bash
VITE_USE_MOCK=1 npm run dev
```

A permanent hazard-striped banner reads **MOCK DATA — every figure on screen is
synthetic** and every response envelope carries `MOCK` in `meta.sources`. Nothing
in mock mode can be mistaken for a measurement.

### Build

```bash
npm run build          # tsc -b && vite build  → dist/
npm run preview        # serve dist/
```

Geometry needs no staging: village boundaries and parcel polygons come from the
API (`/geo/villages`, `/geo/parcels`). There is nothing to copy into `public/`.

---

## The views

| Tab | Endpoints | What it is for |
|---|---|---|
| **Audit map** `#map` | `/geo/parcels`, `/geo/villages`, `/parcels`, `/parcels/{id}`, `/audit/status-summary` | Parcel **polygons** by agreement status; click one for the full audit trail |
| **Village audit** `#villages` | `/summary/registry-delta`, `/summary/crop-area` | Satellite crop mix vs the published Agrisnet DCS village report (Rabi 2024), as crop *share*, sorted by divergence. **Both API caveats render above the chart, always** |
| **Field worklist** `#worklist` | `/audit/worklist?budget=N` | The budget slider, the random-visit counterfactual and the lift multiple |
| **Auto-clear** `#autoclear` | `/audit/auto-clear` | Parcels safe to skip, surveyor-days saved, residual risk, cost assumption |
| **Leakage Ladder** `#validation` | `/validation/ladder`, `/validation/confusion`, `/validation/calibration`, `/evidence/forensics` | The honesty credential, in-product |
| **Analyst** `#analyst` | `POST /analyst/query`, `/analyst/tools` | Conversational panel over AI-5 |

Tabs are hash-routed and the map takes a village: `#validation` sends a reviewer
straight to the credential, `#map?village=Rayagiri%20-%20Part-1` to one village's
full-detail polygons.

### The map layers

- **Parcel polygons** — `/geo/parcels`, simplified to 2 m server-side (in metres,
  then reprojected, so it does not distort with latitude). Default 3,000; raise to
  6,000, or filter by village for the whole village at full detail. If parcel
  geometry is unavailable (Phase 3 not run, `503`) the map falls back to survey
  centroids and says so — those are points, not land, and the banner says which
  you are looking at.
- **Village boundaries** — `/geo/villages`, dashed hairlines.
- **Reserve Forests** — the four `village_co='YYY'` polygons, drawn as a filled,
  dashed exclusion with their own legend entry. They carry no ground truth and are
  the project's **negative control**: a model confidently calling protected forest
  a crop is miscalibrated. They are deliberately *not* given an agreement status,
  because they are not a state anyone should act on. Toggleable.

---

## Rules this code is held to

From `plan.md` §6 Phase 8, the `react-map-ui` skill and the `audit-signals` skill.
Each is enforced somewhere specific, not merely intended.

1. **No hard-coded numbers.** `src/api/client.ts` is the only network code in the
   app, and no component contains a numeric literal that reaches the screen as
   data. When a call fails, the component renders `ErrorState` — never a
   placeholder. Even the default thresholds are fetched (`fetchDefaultThresholds`)
   rather than copied from `kaval/config.py`; if the API omits `meta.thresholds`
   the app refuses to boot rather than invent them.
2. **No duplicated rule, either.** The browser does not derive agreement status.
   `/parcels`, `/geo/parcels` and every `/audit/*` route take the threshold triple
   and re-derive server-side, so `kaval/audit.py::agreement_status` is the single
   authority. (An earlier revision mirrored the rule in the browser because
   `/parcels` could not take thresholds. That mirror is deleted.) The one
   remaining copy lives in `src/api/mock.ts`, which is *standing in for the
   server* and is labelled as such.
3. **Every displayed metric shows its split regime.** `RegimeChip` renders
   `meta.split_regime` beside the metric, and `Provenance` (the footer of every
   panel) prints it too. All metric endpoints now name one; the chip's
   "not reported" guard is dormant against the current API and stays as a
   tripwire for a regression. Nothing borrows a regime from elsewhere.
   `/evidence/forensics` legitimately carries none (it describes the data, not a model).
4. **Thresholds are user-movable and everything updates live.** One
   `ThresholdProvider` holds the triple; the map, the polygons, the queue, the
   status summary and the saving all send it, so they cannot describe different
   policies. The rail prints the exact query string being sent.
5. **Popups cite provenance.** The parcel panel shows the capture event, how many
   parcels shared that one photograph, how far away it was taken, the geometry
   source and the village-code mismatch flag — because for `UNVERIFIABLE` those
   facts *are* the finding.
6. **Phone is a view, not the workflow.** Every tab has a phone layout and is tested
   at phone width; a field officer still works from the exported worklist.
7. **Light and dark both.** Dark is a selected set of steps validated against the
   dark surface, not an inversion.

### Degraded modes are designed, not accidental

Views are tagged `needsThresholds`. When Phase 6 has not run, `/parcels` 503s and
the threshold rail says so — but the Leakage Ladder, the analyst and the village
audit still render, because Phase 4 finishes long before Phase 6 and the honesty
credential must be viewable the moment it exists. Likewise the analyst never
fails for lack of a key: the API falls back through its provider chain to the offline
keyword planner, and each answer carries a chip naming what produced it ("LLM ·
gemini:…" or "offline planner — not LLM").

---

## The palette — and why `CONFIRMED` is blue, not green

**A reviewer will expect green/red. Here is why they do not get it.**

The reflex audit palette is green = agrees, red = disagrees. It was the first
thing tried, and the `dataviz` skill's validator rejected it:

```
$ node scripts/validate_palette.js "#0ca30c,#fab219,#d03b3b,#4a3aa7,#898781" --mode light --pairs all
  [FAIL] CVD separation   worst all-pairs #d03b3b↔#0ca30c ΔE 4.1 (deutan)
```

**CVD ΔE 4.1 under deuteranopia** means `CONFIRMED` and `DISPUTED` — the two most
consequential states this product has, the difference between "skip the visit" and
"send someone tomorrow" — are *indistinguishable* for the commonest form of colour
blindness, which affects roughly 1 in 12 men. On a screen whose entire job is to be
legible in three seconds, that is not a cosmetic problem.

Blue ↔ red is the validated diverging pair. It reads as *opposite* rather than as
*better/worse*, which is also the more honest framing: KAVAL never claims a parcel
is wrong, only that two sources disagree. The final palette passes every hard gate
in both modes:

```
$ node scripts/validate_palette.js "#2a78d6,#eda100,#d03b3b,#1baf7a" --mode light --pairs all
  [PASS] Lightness band · [PASS] Chroma floor
  [PASS] CVD separation        worst all-pairs #1baf7a↔#eda100 ΔE 9.1 (protan)
  [PASS] Normal-vision floor   worst all-pairs ΔE 22.9
  [WARN] Contrast vs surface   #eda100 2.11 — relief: legend + table view present
  → ALL CHECKS PASS

$ node scripts/validate_palette.js "#3987e5,#c98500,#d03b3b,#199e70" --mode dark --pairs all
  [WARN] CVD separation        worst all-pairs #199e70↔#d03b3b ΔE 7.2 (deutan)
  [PASS] Normal-vision floor   worst all-pairs ΔE 16.9
  → ALL CHECKS PASS
```

| Status | Light | Dark | Rendering | Role |
|---|---|---|---|---|
| `DISPUTED` | `#d03b3b` | `#d03b3b` | full opacity, thickest stroke | the money rows — most salient thing on screen |
| `UNCERTAIN` | `#eda100` | `#c98500` | 50% fill | intermediate |
| `UNVERIFIABLE` | `#1baf7a` | `#199e70` | **45° hatch** | off the severity axis: the record, not the field |
| `CONFIRMED` | `#2a78d6` | `#3987e5` | 22% fill, thin stroke | recedes — "nothing to do here" |
| `UNSEEN` | `#898781` | `#898781` | outline only, dashed, no fill | no record exists |

Three further decisions:

- **`--pairs all`, not the adjacent pairlist.** A map is a choropleth: any two
  statuses can end up touching, so every pair must separate, not just neighbours
  in a legend.
- **`UNVERIFIABLE` is hatched by default, not as an accessibility fallback.**
  Teal ↔ red is the one pair in the 6–8 CVD warn band in dark mode (ΔE 7.2), which
  the skill permits *only* with secondary encoding. The hatch is that encoding —
  and it also says the right thing: this status is a different *kind* of problem,
  not a different amount of one. The pattern is injected into Leaflet's own
  overlay `<svg>` so it tracks the theme.
- **`UNSEEN` deliberately fails the validator's chroma floor.** It is achromatic
  and unfilled because it is the "no record" slot and must not look like a state
  anyone can act on.

Salience is carried by fill opacity, stroke weight and radius — not by
saturation. That is why `DISPUTED` dominates even though amber has higher contrast
against the light surface.

Charts use the reference categorical slots, a single-hue blue sequential ramp for
the confusion heatmap, and the blue ↔ red diverging pair with a neutral midpoint
for village divergence. The random-visit counterfactual is drawn in the **same**
hue as the routed bar, because it is the same quantity spent differently — not a
rival series.

---

## Layout

```
src/
  api/client.ts      the only fetch() in the app; ApiError; exportUrl
  api/types.ts       the contract, mirrored from api/main.py + api/analyst.py
  api/mock.ts        VITE_USE_MOCK=1 stand-in; seeded PRNG, MOCK in every envelope
  lib/palette.ts     status → colour token, opacity, weight, hatch, meaning
  lib/thresholds.tsx one threshold triple for the whole app
  lib/useQuery.ts    fetch state; no cache, no silent staleness
  charts/            HBars, DivergingBars, Heatmap, StackedBar + hover tooltips
  components/        RegimeChip, Provenance, ErrorState, StatusLegend, ParcelPanel
  views/             one file per tab
```

---

## Contract notes for the backend

Resolved since the first pass: `/parcels` now takes the threshold triple (the
browser-side mirror is deleted); `/audit/auto-clear` goes through
`metric_response` and carries `split_regime`; `/geo/villages` and `/geo/parcels`
exist, so the map draws land instead of dots and nothing has to be staged by hand.

`accuracy_within_cleared` is gone and its replacement is better: it was circular
(`CONFIRMED` is *defined* as the model agreeing with the survey, so it was 100% by
construction). `expected_residual_error_rate` is the honest quantity and the panel
now explains why, with `residual_note` surfaced verbatim.

### The registry panel is a consistency check, not validation

`/summary/registry-delta` compares against the Tamil Nadu Agrisnet village-wise
Digital Crop Survey report, which is the published aggregate of the **same survey**
whose parcels are our ground truth. Two caveats travel in the payload and are
rendered as a fixed banner above the chart (not a tooltip, not collapsible):
`independence_caveat` (not an independent second source) and `scale_caveat`
(compared as crop *share*, because our parcels cover only part of each village, so
hectares would measure sampling coverage). `implied_ha_delta` is labelled as an
extrapolation. Agreement here is weaker evidence than it looks; disagreement is
worth a visit.

Still open, none blocking:

1. **`/audit/worklist` has no pagination.** `budget` goes to 20,000 and the whole
   queue returns in one response; the table renders the first 400 and says so.
2. **`/export` cannot reproduce the routed queue.** It filters by village and
   status but not by budget or priority, so the CSV a field officer downloads is
   not literally the worklist on screen. A `priority` column plus an optional
   `budget` parameter would fix it.
3. **`Citation` has no `parcel_id`.** The frontend type accepts one optionally and
   renders `parcel <id>` when present; citations currently carry
   `{source, n, split_regime}` only.
4. **`/health` does not carry `thresholds`**, so the app calls `/parcels?limit=1`
   at boot just to learn the defaults — which is also why a missing Phase 6 takes
   the threshold rail down.
5. **No endpoint for satellite-only inference in the Reserve Forest polygons.**
   They appear as a negative control only. Running the classifier over them would
   need satellite embeddings for geometry outside the 14,611 surveyed parcels,
   which needs Earth Engine access we do not have.

Resolved since the first pass:

- **Parcel detail now returns the field-join fields.** `/parcels/{id}` carries
  `field_id`, `snap_m`, `parcels_sharing_field` and `field_area_m2`. These briefly
  did not render because the API had renamed them (`snapped_m`,
  `legal_parcels_sharing_this_field`, `physical_field_area_m2`) while the client
  read the short names — and because the client types them optional, nothing
  errored, the three rows simply never appeared. The API now uses the same names as
  the parquet and the feature store: one name per concept, everywhere.
  `/geo/parcels` still does not carry them; it is a choropleth feed, and the panel
  fetches the detail route on click.
- **`/geo/parcels` no longer truncates with `head(limit)`.** It samples, so an
  unfiltered map is no longer biased by file order.
- **The worklist split-regime chip renders.** It was passed `metric={false}`.
