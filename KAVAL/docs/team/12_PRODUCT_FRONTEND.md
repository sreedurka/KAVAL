# 12 · Product & Frontend

**Audience:** M4 (owner), everyone else in outline. Phase 8. Code is in `KAVAL/frontend/`.

You are reviewed on judgement, not on React. Nobody will ask you to explain a hook. They
will ask why the map is blue, why a number on screen can be trusted, and what you did not
build. This document is organised around those questions.

Assumed reading: [00](00_START_HERE.md), [01](01_ARCHITECTURE.md), [02](02_DOMAIN_PRIMER.md).
The API you consume is [10 · API & Agentic Analyst](10_API_ANALYST.md) (M3).

---

## 1. The defining decision: the map is coloured by agreement status

> **The one-sentence defence.** A crop-coloured map answers "what is growing", which every
> classification demo already answers; ours is coloured by `CONFIRMED / DISPUTED /
> UNCERTAIN / UNVERIFIABLE / UNSEEN`, which answers "what should someone do next", and
> that is what makes it an audit product.

Say that sentence first. Everything else in this section is the support for it.

### Why it is the single most consequential UI choice

The first thing a reviewer sees is the map. It has about three seconds to tell them what
kind of thing they are looking at.

| If the map is coloured by | The reviewer concludes | Because |
|---|---|---|
| **Crop class** | "a crop classifier with a map" | Green rice, yellow maize. Every remote-sensing demo looks like this. Nothing on it says a decision is involved. |
| **Agreement status** | "a tool for deciding where to send people" | The colours are actions: skip, visit, re-survey the record. The map is evidence for the audit, not the product itself. |

This mirrors the framing in [00](00_START_HERE.md): the classifier is the instrument, the
product is the audit. A crop-coloured map hides the instrument-versus-product distinction;
a status-coloured map is that distinction rendered.

### What the map shows, from `docs/evidence/p6_audit.json`

The audit covers **14,310 parcels** (the 14,611 in the geometry layer minus the 301 with no
feature row, 2.06%). At the default thresholds:

| Status | Parcels | Area (ha) | Action |
|---|---:|---:|---|
| `CONFIRMED` | 4,825 | 870.8 | skip next season |
| `DISPUTED` | 784 | 100.8 | top of the worklist |
| `UNCERTAIN` | 8,429 | 1,143.0 | route by budget |
| `UNVERIFIABLE` | 272 | 23.0 | re-survey the **record** |
| `UNSEEN` | 0 | — | no survey record, no audit claim |

`UNSEEN` is zero because every parcel in the supplied data has a survey record. It is in
the legend and the type system anyway, because a parcel with no record is a real state
in production and the vocabulary should not change when the data does.

### Crop class is still there

`AuditMapView` has a `colourBy` switch (`status` or `crop`). Crop is a secondary layer for
the reviewer who wants to see where the classifier sees rice. It uses the categorical
series slots (`--series-1..8`) from `src/lib/palette.ts`, never cycles a ninth hue, and is
off by default. The default is the decision.

---

## 2. The palette, and why `CONFIRMED` is blue

A reviewer will expect green for "agrees" and red for "disagrees". They do not get it, and
you must be able to say why without hesitating.

### The failure

The reflex audit palette was the first thing tried. The `dataviz` skill's validator
rejected it:

```
node scripts/validate_palette.js "#0ca30c,#fab219,#d03b3b,#4a3aa7,#898781" --mode light --pairs all
  [FAIL] CVD separation   worst all-pairs #d03b3b <-> #0ca30c  dE 4.1 (deutan)
```

**dE 4.1 under deuteranopia.** Deuteranopia is the commonest form of red-green colour
blindness, affecting roughly 1 in 12 men. A dE that low means `#0ca30c` and `#d03b3b` are
close to indistinguishable. `CONFIRMED` and `DISPUTED` are the two most consequential
states in the product: the difference between "skip the visit" and "send someone
tomorrow". A palette that collapses exactly those two is not a cosmetic problem, it is a
correctness problem on a screen whose only job is to be read in three seconds.

### The fix, with the numbers

Blue against red is the validated diverging pair. The final palette, from the header of
`src/lib/palette.ts` and `frontend/README.md`:

| Status | Light | Dark | Rendering | Role |
|---|---|---|---|---|
| `DISPUTED` | `#d03b3b` | `#d03b3b` | 0.95 fill, weight 1.8, radius 7.5 | the money rows, most salient |
| `UNCERTAIN` | `#eda100` | `#c98500` | 0.50 fill, weight 0.8 | intermediate |
| `UNVERIFIABLE` | `#1baf7a` | `#199e70` | **45 degree hatch**, 0.85 fill | off the severity axis |
| `CONFIRMED` | `#2a78d6` | `#3987e5` | 0.22 fill, weight 0.6, radius 4 | recedes, "nothing to do" |
| `UNSEEN` | `#898781` | `#898781` | outline only, no fill | no record exists |

Validator results, re-run by `scripts/p8_validate_palette.py`, which reads the colours
straight out of `src/styles.css` and keeps the raw output in
`docs/evidence/p8_palette.{json,md}`. All four filled statuses, `--pairs all`:

| Mode | Worst CVD pair | CVD dE | Normal-vision floor | Verdict |
|---|---|---:|---:|---|
| Light | teal `#1baf7a` <-> amber `#eda100` (protan) | **9.1** | 22.9 | pass, **contrast WARN** |
| Dark | teal `#199e70` <-> red `#d03b3b` (deutan) | **7.2** (warn band) | 16.9 | pass, **CVD WARN** |

The same run reproduces the retired green/red palette's **4.1** failure. The committed
figures in `palette.ts` and `frontend/README.md` matched the re-run exactly. Before this
re-run they were copied numbers with no raw output behind them.

Three honest notes on those numbers.

1. **"ALL CHECKS PASS" sits on top of a warning in both modes.** That is the validator's
   verdict line, and it is true in the sense that nothing fails. An earlier version of
   this table quoted the verdict and dropped the WARN rows under it (the frontend README
   keeps them). Light mode carries a **contrast warning**: amber (2.11:1) and teal (2.74:1) are below
   3:1 against the light surface. The validator's rule is that this obliges visible
   labels or a table view. We have both: every legend row names its status and action,
   and the worklist is a table. So the palette is legal, but it is not unconditional.
2. **Dark mode is in the warn band, not comfortably clear.** 7.2 is above the failure line
   and inside the 6 to 8 range the skill permits only with secondary encoding. That is the
   reason for the hatch, below. Say this before someone finds it.
3. **The figures cover the four filled statuses, not `UNSEEN`.** Add grey `UNSEEN` and
   the palette fails outright (light CVD 5.1, dark 2.0, and the chroma floor). That is by
   design: `UNSEEN` is outline-only with no fill, so it is never a filled area that has to
   separate from teal. The evidence file records this failing run too, so the exclusion
   is visible rather than quietly assumed. Currently 0 parcels are `UNSEEN`.

The palette is also blue against red because it reads as **opposite**, not as
better versus worse. KAVAL never claims a parcel is wrong. It claims two sources disagree.
Green-good and red-bad would smuggle in a verdict we do not have.

### `--pairs all`, not the adjacent list

The validator can test only neighbouring legend entries or every pair. We use every pair,
because a map is a choropleth: any two statuses can end up sharing a border, so any two
must separate. Checking neighbours in the legend would test a situation the map never
guarantees.

### Why `UNVERIFIABLE` is hatched by default, not as a fallback

Teal against red is the one pair in the CVD warn band in dark mode, which is why the hatch
is *required*. But that is the secondary reason. The primary reason is meaning:

> A **different kind** of problem should not read as a different **amount** of one.

`DISPUTED`, `UNCERTAIN` and `CONFIRMED` sit on one axis: how much the satellite and the
survey agree. `UNVERIFIABLE` is not on that axis. It says the *evidence* is bad (a
photograph 3 km away shared by 40 parcels), so a field visit would not fix it. If it were
another solid colour it would read as "a bit worse than uncertain". The hatch says "this
is a different category". It is injected by `HatchDefs` in `AuditMapView.tsx` into
Leaflet's own overlay `<svg>`, referencing the same CSS token as the legend swatch, so it
tracks light and dark. It is on for every user, not a toggle.

### Why salience is opacity, stroke and radius, not saturation

Amber (`#eda100`) has *higher* contrast against the light surface than red does; a
saturation-driven design would make `UNCERTAIN` the loudest thing on the map. That is
wrong, because `UNCERTAIN` is 8,429 of 14,310 parcels and `DISPUTED` is 784. So
prominence is assigned explicitly in `STATUS_STYLE`: `DISPUTED` gets full fill, the
thickest stroke and the largest radius; `CONFIRMED` recedes to a 0.22 wash. The map
ordering follows the severity order everywhere (legend, bars, tables).

### `UNSEEN` fails the chroma floor on purpose

It is achromatic and unfilled. It is the "no record" slot and must not look like a state
anyone can act on. The validator flags it; that is the intended result.

---

## 3. The views

Six tabs, hash-routed (`src/App.tsx`), so `#validation` sends a reviewer straight to the
credential and `#map?village=<name>` to one village.

### 3.1 Audit map and the parcel audit trail
`src/views/AuditMapView.tsx`, `src/components/ParcelPanel.tsx`, `StatusLegend.tsx`

**Question:** *where are the parcels a surveyor should walk to, and why is each one there?*

The map draws parcel **polygons** (`/geo/parcels`, simplified to 2 m server-side) rather
than dots, coloured by status, with dashed village hairlines (`/geo/villages`) and the
four Reserve Forest polygons as a filled dashed exclusion (the negative control from
[13](13_CORRECTIONS.md), toggleable). If parcel geometry is unavailable (`503`) the map
falls back to survey centroids and the banner says they are points, not land.

Clicking a parcel opens `ParcelPanel`, the audit trail in two blocks:

- **The disagreement:** declared crop, predicted crop, suggested correction, calibrated
  confidence, raw confidence, `P(declared label is wrong)`.
- **Provenance of the record:** Record Trust Score, capture event, parcels sharing that
  photograph, photograph distance, geometry source, village-code mismatch flag.

**What a reviewer should notice:** raw and calibrated confidence sit side by side, so the
calibration gap (ECE 0.1247 to 0.0046) is visible on a single parcel. And for an
`UNVERIFIABLE` parcel the provenance block *is* the finding: click one and see the large
bag and the distant photograph.

### 3.2 Village audit, with the registry comparison
`src/views/VillageAuditView.tsx` · `/summary/registry-delta`, `/summary/crop-area`

**Question:** *where does the satellite crop mix differ most from the published village
report?*

Diverging bars, sorted by divergence, blue to red with a neutral midpoint, compared as
crop **share** and not hectares. Two caveats from the API render in a fixed banner above
the chart, not in a tooltip:

- `independence_caveat`: the Agrisnet village report is the published aggregate of the
  *same survey* whose parcels are our ground truth. It is a consistency check, not
  independent validation.
- `scale_caveat`: our parcels cover only part of each village, so hectares would measure
  sampling coverage. Hence shares.

**What a reviewer should notice:** the banner cannot be collapsed. Agreement here is
weaker evidence than it looks; disagreement is worth a visit. `implied_ha_delta` is
labelled as an extrapolation. This view is also where the boundary-file error from
[04](04_GEOMETRY.md) surfaces.

### 3.3 Field worklist, the budget slider and the counterfactual
`src/views/WorklistView.tsx` · `/audit/worklist?budget=N`

**Question:** *if the department can afford N visits, which N, and what are they worth?*

A slider (budget up to 20,000) drives the queue. Beside "KAVAL-routed" it always shows
"Random visits (baseline)", drawn as the **same hue** on the same axis, because it is the
same quantity spent differently, not a rival series. The baseline shows a standard
deviation whisker (mean of repeated random draws).

**What a reviewer should notice, and what to volunteer.** The budget curve in
`p6_audit.json`:

| Budget | Routed disagreements found | Random expected |
|---:|---:|---:|
| 100 | 100 | 18.3 |
| 250 | 250 | 45.7 |
| 500 | 498 | 91.4 |
| 1,000 | 972 | 182.9 |
| 2,000 | 1,882 | 365.8 |

The ratio is 5.47 at every budget below the number of available disagreements (2,617). It
is `1 / 0.1829`, the base rate. The API says so itself
(`targeting_is_pinned_by_construction: true`) and the note is surfaced. It measures
coverage, not ranking quality; any classifier can list its own disagreements. This is
correction 2 in [13](13_CORRECTIONS.md). Volunteer it, then point at the quantity that is
informative: mean calibrated confidence of routed parcels (0.758 at budget 100) against
0.652 across all disagreements. The queue puts better-evidenced cases first.

The queue table renders the first 400 rows and says so. The CSV export is a separate
endpoint (see section 9 for its gap).

### 3.4 Auto-clear
`src/views/AutoClearView.tsx` · `/audit/auto-clear`

**Question:** *which parcels never need visiting again, and what does that save?*

| Quantity | Value (evidence) |
|---|---:|
| Parcels auto-cleared | 4,825 (33.7%) |
| Area | 870.8 ha |
| Surveyor-days saved per season | 193.0 of a 572.4 baseline |
| Cost assumption | 25 parcels per surveyor-day, labelled an assumption |
| Expected residual error rate | 0.0757 (a proxy, not a bound) |

**What a reviewer should notice:** there is no "accuracy within the cleared set" tile.
It would be 100% by construction, since `CONFIRMED` is defined as the model agreeing with
the survey. The panel says so under "What this panel does not claim" and shows
`residual_note` verbatim. The real risk, satellite and surveyor wrong in the same way, is
unidentified from this data; only a field audit of a `CONFIRMED` sample settles it.

### 3.5 The Leakage Ladder
`src/views/ValidationView.tsx` · `/validation/ladder`, `/confusion`, `/calibration`,
`/evidence/forensics`

**Question:** *why should I believe the headline number?*

| Regime | Accuracy | Macro F1 |
|---|---:|---:|
| 1-random | 89.7% | 0.772 |
| 2-parcel | 89.5% | 0.769 |
| **3-event + field** | **81.2%** (LightGBM held fixed) | **0.528** |
| 4-village | 70.8% (SD 0.095) | 0.326 |

Below it: heads and sources comparisons, per-class metrics with **capture events as the
effective n** beside record count, the confusion matrix, the calibration figures, and the
ground-truth forensics panel.

See section 4 for why this is in the product. What to notice: row 2. Grouping by parcel
does nothing (-0.2 points), so the obvious control gives false comfort. Also see
section 9 on the 81.2 versus 81.7 figures.

### 3.6 Threshold controls
`src/components/ThresholdControls.tsx`, `src/lib/thresholds.tsx`

**Question:** *what policy produced this map, and what if the policy were different?*

Three sliders in a persistent rail: `confidence_high`, `trust_floor`, `trust_high`. Each
prints a plain sentence for what crossing it does. The rail prints the exact query string
being sent. Defaults come from the API. There is a "Reset to API defaults" button.

**What a reviewer should notice:** drag `confidence_high` and the map, the status counts,
the worklist and the surveyor-day saving move together. That is not a UI trick, it is the
architecture (section 5 and 6).

### 3.7 The analyst panel
`src/views/AnalystView.tsx` · `POST /analyst/query`, `/analyst/tools`

**Question:** *can I ask this in words and see where the answer came from?*

A conversational panel over AI-5. Each answer renders its citations as chips (source,
n, split regime). Starters, the nine callable tools, and "What the analyst will not do"
are listed on the page.

- **A model chip on every answer.** It names what produced the reply: "LLM · gemini:…"
  (or whichever provider in the fallback chain answered), or "offline planner — not LLM"
  when no model is reachable. The API no longer returns a 503 without a key; it falls
  back to the offline planner and says so.
- **Answers render as Markdown**, so the LLM's tables and lists read properly. Rendering
  is safe: raw HTML in an answer is not injected into the page.
- **Tested end to end.** The Playwright suite (`frontend/e2e/kaval.spec.ts`) passes 22/22
  across every tab at desktop, phone and dark, plus the analyst flow; screenshots are in
  `docs/e2e/` (`progress.md`, 2026-10-01 end-to-end testing entry).

**What a reviewer should notice, and volunteer:** planning is verified on Gemini's free
tier: the 6 brief + 3 product questions pass 9/9, and the 2 extended questions (parcel
lookup, calibration) pass 2/2 (`p7_analyst_verification.json` → `llm_planner`, which records
per question which model in the fallback chain answered, the tools it chose, its time, and
any figure not traceable to a tool result). It sometimes skips a secondary tool call or
states a figure no tool returned (a mis-rounding, or a number it derived itself); the
grounding check flags these, and every answer shows its tool calls so they can be checked. It is **not** verified for Claude, and a small local model or the offline
planner is labelled as such on every answer. The UI should not imply more. See
[10](10_API_ANALYST.md).

---

## 4. Why the Leakage Ladder is inside the product

The ladder is the core contribution of the project ([06](06_LEAKAGE_PROTOCOL.md)). It
would be natural to put it in a report and link to it. We did not, on purpose.

- **A credential you must be shown a document to see is a claim.** A credential a reviewer
  meets by clicking a tab is evidence. The tab is named after the thing.
- **It sits beside the product's outputs.** Anyone reading "18.3% of parcels disagree"
  can, one click later, see the accuracy that figure rests on, under four splits.
- **The brief's own clause justifies it.** The brief says spatial or parcel leakage
  invalidates a claimed result. An honest answer to that clause has to be visible in the
  thing being evaluated. The view's opening text says exactly this.
- **It is wired to the API, not pasted.** It is fetched from `/validation/ladder`, so it
  cannot go stale relative to the model that produced the audit.

The DEMO_WALKTHROUGH deliberately opens on this tab before the map.

---

## 5. The rules the UI enforces

Each rule from `plan.md` §6 Phase 8 and the `react-map-ui` skill is enforced in a
specific place, not merely intended.

| Rule | Where it is enforced |
|---|---|
| **No hard-coded numbers** | `src/api/client.ts` is the only network code. A failed call renders `ErrorState`, never a placeholder ("No figure is shown in place of the missing one"). Even the default thresholds are fetched (`fetchDefaultThresholds`); if the API omits `meta.thresholds` the app refuses to boot rather than invent them. |
| **Every metric shows its split regime** | `RegimeChip` (`components/common.tsx`) renders `meta.split_regime` beside the metric; `Provenance`, the footer of every panel, prints it too. If the API omits a regime the chip shows a visible warning instead of borrowing one. |
| **Thresholds movable, everything updates** | One `ThresholdProvider`. The map, polygons, status summary, worklist and auto-clear all send the same triple. |
| **Popups cite provenance** | `ParcelPanel`: capture event, parcels sharing that photograph, photograph distance, geometry source, mismatch flag. |
| **Simplified geometry** | `/geo/parcels` simplifies in metres (2 m) then reprojects; default 3,000 polygons, filterable by village to get a whole village at full detail. |
| **Phone is a view, not the workflow** | The hard 1,024 px minimum was replaced by a phone layout, and every tab is tested at phone width (section 7.4). A field officer still works from the exported worklist. |
| **Light and dark** | Dark is a selected set of steps validated against the dark surface, not an inversion. |

**Why the provenance rule matters most.** For `UNVERIFIABLE` the provenance is not a
footnote, it is the reason the status exists. A popup that said only "UNVERIFIABLE" would
be an assertion. "Shared by 12 parcels, photograph 2,384 m away" is an argument. (Those
values are from a live parcel I queried; they will differ per parcel.)

### Mock mode

`VITE_USE_MOCK=1 npm run dev` runs without the API against `src/api/mock.ts`. It exists so
the UI can be built and reviewed when the backend is down. It is labelled as loudly as
possible: a permanent hazard-striped banner reads "MOCK DATA, every figure on screen is
synthetic" and every response envelope carries `MOCK` in `meta.sources`. The seeded
generator means it is reproducible. It cannot be mistaken for a measurement, which is the
only condition under which a mock is acceptable in an audit product.

---

## 6. The duplicated-rule problem, and its fix

**What happened.** The first build of the frontend had `src/lib/status.ts`, a TypeScript
re-implementation of the rule that turns (prediction, confidence, trust) into an agreement
status. It existed because `/parcels` did not accept thresholds: the sliders had to move
the map, and the only way to do that was to re-derive status in the browser.

**What we did.** Deleted `status.ts`. Added `confidence_high`, `trust_floor` and
`trust_high` query parameters to `/parcels`, `/geo/parcels` and every `/audit/*` route.
The server calls `recompute_status()` in `api/main.py`, which calls
`kaval/audit.py::agreement_status`. That is now the only implementation. The frontend
sends three numbers and draws what comes back.

### Why a duplicated business rule is worse than an extra parameter

| | Extra API parameter | Rule copied into the browser |
|---|---|---|
| **Cost** | three query fields | a second implementation, in another language |
| **Failure mode** | a slow request | the copy drifts silently |
| **When it fails** | loudly (wrong param, 422) | quietly: both sides run, both look plausible |
| **What it breaks** | nothing | the map says `DISPUTED` while the worklist and the auto-clear count, computed on the server, disagree |

The dangerous case is the last one. If someone changes a comparison in `kaval/audit.py`
from `>=` to `>`, a browser copy still says the old thing. The map and the worklist then
describe different policies, and nothing crashes. For a product whose entire claim is
"you can audit this", a map that disagrees with its own worklist is fatal. An extra
parameter costs nothing to maintain; a drifted rule cannot be detected without already
knowing the answer.

There is one honest exception. `src/api/mock.ts` contains a copy of the rule, because in
mock mode it is *standing in for the server*. It is labelled as such, and only runs when
the MOCK banner is up.

The server side is also written to be safe under concurrency: thresholds are passed as an
argument to `recompute_status`, not patched into a module global, because FastAPI runs
sync endpoints in a threadpool and two users with different sliders would otherwise
corrupt each other's results.

---

## 7. Three API defects the frontend found

None of these was found by an API test or by reading the API code. All three were found
because a UI has to *put the data in front of a person*, which is a different test from
"does the endpoint return 200". They are corrections 14, 15 and part of the regime-chip
work in [13](13_CORRECTIONS.md).

### 7.1 `/parcels/{id}` did not return the Phase 2 geometry fields
The parcel panel was designed to show which physical field a parcel was snapped to, how
far it was moved, and how many legal parcels share it. The fields were not in the
response. Chasing that revealed the real problem one layer down: **Phase 6 was not
carrying the Phase 2 geometry columns forward at all.** They existed in `parcels.gpkg`,
were dropped when the audit table was built, and could never have reached any consumer.
Only the UI, which wanted them on screen, needed them. Fixed upstream; the API now
returns them.

### 7.2 `/geo/parcels` used `head(limit)`
`head()` returns the first N rows in file order. File order in this dataset is
geographically clustered, so an unfiltered map was silently showing one part of the taluk
and looking complete. Nothing crashed and the counts looked plausible. It was visible only
by looking at the map, not at counts. Now the endpoint uses
`df.sample(limit, random_state=0)`, and the seed makes it reproducible. (For a complete
picture of one village, filter by village and get everything.)

### 7.3 The worklist's split-regime chip rendered nothing
A metric was on screen with no regime beside it, which is the exact bug `react-map-ui`
rule 2 forbids ("a bare accuracy figure on screen is a bug"). An API test would not catch
it, because the endpoint returned valid data; the *absence* was only visible on the page.
Fix: every metric endpoint now goes through `metric_response()`, which raises if
`split_regime` is absent, and `RegimeChip` shows a visible warning instead of rendering
nothing if one ever does slip through. I confirmed the current API returns
`split_regime: '3-event'` on `/parcels`, `/geo/parcels`, `/audit/worklist` and
`/summary/registry-delta`. I did not have the pre-fix code to reproduce the original
failure, so treat the exact mechanism as M3's to state.

**The lesson for review:** a UI is an integration test for honesty. "Every displayed
metric shows its regime" is trivially true of a response and only checkable on a screen.

### 7.4 What the end-to-end screenshots caught
The Playwright suite (`frontend/e2e/kaval.spec.ts`, 22/22 passing; screenshots in
`docs/e2e/`) found what green unit tests had not. **The worklist's headline tiles were
blank**: the UI read field names the API had renamed when the routing "lift" was
retracted, and the tile was still labelled "Lift multiple — the number that justifies the
system", which is the claim [13](13_CORRECTIONS.md) correction 2 withdrew. Both are fixed,
and a test now fails on any blank stat tile. The same pass fixed auto-clear calling the
residual a "bound" (correction 1 says proxy), chart text that scaled to about 20 px and
clipped labels, and the missing phone layout. Source: `progress.md`, 2026-10-01
end-to-end testing entry.

---

## 8. Honest status

### Live against the API
Everything except the item in the next subsection. I ran the API in-process and confirmed
`/parcels`, `/parcels/{id}`, `/audit/status-summary` (counts match `p6_audit.json`:
4,825 / 784 / 8,429 / 272), `/geo/parcels` and `/audit/worklist` respond with
`thresholds` and `split_regime` in `meta`.

### Build output (verified for this document)
`npm run build` (`tsc -b && vite build`, TypeScript strict) completes cleanly in 1.39 s:
91 modules, `index-*.js` 371.97 kB (113.27 kB gzip), `index-*.css` 26.43 kB (9.23 kB
gzip). About 4,000 lines of TypeScript across `src/`.

### Run it
```bash
# backend, from the repository root
.venv/bin/uvicorn KAVAL.api.main:app --port 8077
# frontend
cd KAVAL/frontend && npm install && npm run dev      # http://localhost:5173
```
Port 8077 and not 8000, because something unrelated answers `/health` on 8000. The header
chip therefore checks that `/health` carries `phases_available` and shows "not the KAVAL
API" if not. Mock mode: `VITE_USE_MOCK=1 npm run dev`.

### Degraded modes are designed
Views are tagged `needsThresholds`. If Phase 6 has not run, `/parcels` returns 503 and the
threshold rail says so, but the Leakage Ladder, analyst and village audit still render,
because Phase 4 finishes well before Phase 6 and the credential should be viewable the
moment it exists.

### Known defect I found while writing this: field-join field names do not match
The API's `/parcels/{id}` returns `evidence.snapped_m`, `legal_parcels_sharing_this_field`
and `physical_field_area_m2`. The frontend type in `src/api/types.ts` and the rows in
`ParcelPanel.tsx` read `snap_m`, `parcels_sharing_field` and `field_area_m2`. Only
`field_id` matches. So against the live API the panel shows the physical field id but
silently omits "Snapped to field by", "Legal parcels sharing this field" and "Field area",
and it does so without an error, because they are typed optional. I confirmed the
returned key names by calling the endpoint. Fix is either side (rename in the type and
panel, or in the API); it is a five-line change. **Fix this before the review**, since
"legal parcels sharing this field" is the panel row that shows the Phase 2 finding (fields
are not parcels). Also, `frontend/README.md` still lists this as an open item ("neither
endpoint returns them yet") and its item 6 (`head(limit)`) is also already fixed; the
README's "Still open" list is stale.

### What is NOT built
**The satellite-only inference demo on the four unlabelled villages has no endpoint and no
view.** The `plan.md` Phase 8 list includes it and we have not delivered it. Why:

1. The four villages are the `village_co='YYY'` Reserve Forest polygons. They have no
   survey records, so there is nothing to compare a prediction against. (This is the
   reframing in [13](13_CORRECTIONS.md), correction 7: it was never a proper
   inference demo, it is a negative control.)
2. To run the classifier over them we need per-parcel embeddings for geometry **outside
   the 14,611 surveyed parcels**. Our embeddings came from Google Satellite Embedding via
   Earth Engine, and we do not have Earth Engine credentials. `p2b_reserve_forest.json`
   records this as "not done rather than approximated".
3. A frontend cannot fill this gap. Showing a crop class on those polygons would need a
   number from somewhere, and the rule is that every number comes from the API.

What the UI does instead: the four polygons draw as a toggleable dashed exclusion with
their own legend entry, deliberately given no agreement status. What we *do* have is the
delineation-only result, 734.7 ha (4.0%) of 18,384.8 ha of reserve forest, in 2,919
field-like patches, which is **not** a claim of encroachment. The classifier-confidence
test (does it return low confidence on forest, as a calibrated model should) is the
missing half and is listed under Open in `progress.md`.

### Other open items (from the README, all non-blocking)
- `/audit/worklist` has no pagination; the table shows 400 rows and says so.
- `/export` filters by village and status but not budget or priority, so the CSV a field
  officer downloads is **not literally the worklist on screen**. This is the item a
  reviewer is most likely to hit, because "export the worklist" is the whole mobile story.
- `Citation` carries `{source, n, split_regime}` but no `parcel_id`, so analyst
  citations cannot link to the map.
- `/health` does not carry thresholds; the app calls `/parcels?limit=1` at boot to learn
  the defaults, so a missing Phase 6 takes the threshold rail down.

---

## 9. Numbers that look inconsistent, and why they are not

| You will see | Also see | Resolution |
|---|---|---|
| 14,643 records | 14,611 parcels, 14,310 audited | Records are supplied points; 14,611 have a geometry and feature row; 301 have no feature row, leaving 14,310 in the audit. The status counts sum to 14,310. |
| **81.2%** on the ladder | **81.7%** elsewhere (calibration `actual_accuracy` 0.8171) | The ladder rung is LightGBM (0.8119). 81.7% is the MLP head, the best of the four heads at the same regime. Both are capture-event grouped. Whichever you quote, name the head. |
| 3,204 capture events | 2,921 in the audit | Same 301-parcel gap. 3,204 is over all records, 2,921 over the audited set. |
| Photograph median 1,436 m (walkthrough) | 1,432.9 m (`p3_feature_store.json`) | Different method and population: the canonical published figure is the haversine median over all valid records in `gt_forensics.json`; p3's is a projected distance over the joined parcel set, and is now labelled as such in its own evidence. Quote 1,436 m. |

---

## 10. Questions you must be able to answer

**Why not colour by crop?**
Because a crop map answers what a classifier already does and every demo does it. This
is an audit, so the map shows what to do: skip, visit, re-survey the record. Crop is still
one click away as a secondary layer. And a crop palette would put rice, a class with 63%
of records, in a solid colour over most of the map, hiding the 784 parcels that matter.

**Why is a student project worrying about colour blindness?**
Because the two states that matter most are `CONFIRMED` and `DISPUTED`, and the reflex
green/red pair measured a CVD dE of 4.1 under deuteranopia, which is 1 in 12 men. The
users are civil servants who read this screen for a living; some are colour blind, and if
one confuses skip-the-visit with send-someone-tomorrow, the product has failed at its
one task. It cost a validator run. It is the
kind of decision that shows the interface was designed for a decision, not decorated.
Be candid that the dark theme sits in the warn band at 7.2 and is covered by hatching.

**Why is `UNVERIFIABLE` hatched rather than another colour?**
Because it is a different kind of problem, not a different amount of one. Solid colour
puts it on the severity axis. The hatch says "this is about the record".

**How do I know the numbers on screen are real?**
Four things. (1) `src/api/client.ts` is the only network code and no component holds a
literal that reaches the screen as data. (2) A failed call shows an error, never a
placeholder. (3) Every panel's footer prints sources, n, split regime and timestamp from
`meta`. (4) The tab you are looking at is a live query: the status counts I saw from the
running API (4,825 / 784 / 8,429 / 272) equal `docs/evidence/p6_audit.json`, which is
generated by `scripts/`. If the app is in mock mode, a hazard banner says so on every
page. What I cannot claim: that the API's own numbers are right; that is M2 and M3's
evidence chain.

**The map and the worklist agree with each other. Is that not obvious?**
Only because the rule exists in one place. When we had a browser copy they could have
diverged silently. See section 6.

**Why is the Leakage Ladder a tab and not an appendix?**
A credential you have to be shown a document for is a claim. Section 4.

**The worklist says 5.47 times better than random. Impressive?**
No, and say so first. It equals 1 divided by the base disagreement rate (0.183) at any
budget below 2,617, and the API flags it as pinned by construction. It measures coverage.
The informative numbers are the mean confidence of routed parcels versus all
disagreements (0.758 against 0.652 at budget 100), and the expected corrections
`sum P(label wrong)`, which is a model estimate and not a measured correction count.

**You have no accuracy figure for the auto-cleared set. Why?**
It would be 100% by construction. We show the residual-risk proxy (0.0757, about 365
parcels expected wrongly cleared) and state it is unidentified. Only a field audit of a
`CONFIRMED` sample settles it.

**Where is the inference demo the plan promised?**
Not built. Reserve Forest has no survey records and we have no embeddings for it without
Earth Engine. Section 8. We show delineation only and refuse to invent a crop.

**Can this go to a field officer's phone?**
The screens now render at phone width and are tested there (section 7.4), but the phone
is not the field workflow. The field officer uses an exported worklist, and today that
export does not carry the budget or priority order (section 8). Do not claim otherwise.

**What did the frontend teach you about the backend?**
Three defects (section 7). A UI is where "the endpoint returned 200" meets "a person can
see this is right".

**What is wrong with the frontend right now?**
The field-join name mismatch in section 8, the stale "still open" list in
`frontend/README.md`, the un-reproduced palette validator output in this session, the
missing inference demo, the export gap, and that analyst planning is verified on Gemini
only (Claude untested; the keyless local model is slow on CPU).
