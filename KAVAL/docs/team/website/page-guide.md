# KAVAL website: page-by-page guide

**For:** the student team (M1 to M4), including those who do not write code, so that anyone
can explain any part of the screen to FarmwiseAI reviewers.

**How to use it:** open the app (`http://127.0.0.1:5173`) next to this file and read top to
bottom. Each tab is described from the top of the page to the bottom. For every visible
thing you get: what it is, what question it answers, where the number comes from, and how it
reacts to the controls.

**Where the example numbers come from.** Every "today it shows ..." figure was read on
2026-10-01 from the live API at `http://127.0.0.1:8077` (the same one the page calls through
`/api`), or from `docs/evidence/*.json`. Each time, the source is named. If the screen and
this file disagree, the screen is right and this file is stale. Nothing here was typed in
from memory.

**Three words used throughout.**

- **Declared** = what the surveyor recorded for the parcel in the Digital Crop Survey (the
  ground-truth file FarmwiseAI supplied).
- **Satellite** = what our model predicts for the same parcel from satellite embeddings.
- **Disagree** = declared and satellite differ. We never say the parcel or the surveyor is
  "wrong". Two sources disagree, and only a field visit can say which one is right.

**Split regime.** Every accuracy-type number is measured under a validation split. The
headline split is `3-event`: parcels that share one photograph (one "capture event") are
always kept on the same side of the train/test divide, so the model is never tested on a
photograph it has partly seen. The headline figure is **81.7% accuracy, MLP head,
capture-event-grouped ("3-event")**, macro F1 0.564. Never say 81.7% without "3-event".

---

## 0. How the pieces connect

```
scripts/ (p1 ... p7)         run once, offline
   |  produce
   v
data/derived/audit.parquet            one row per audited parcel (14,310 today)
data/derived/parcel_geometry.gpkg     parcel polygons (written by p3_feature_store.py)
data/derived/village_registry.parquet registry vs satellite per village x crop (p7_registry_comparison.py)
docs/evidence/*.json                  every published figure (p4_results.json, p6_audit.json, ...)
   |  loaded once at start-up by
   v
KAVAL/api/main.py  (FastAPI, port 8077)
   |  JSON over HTTP, always wrapped as {data, meta}
   v
frontend/src/api/client.ts   <- the ONLY network code in the app
   |
   v
React views (src/views/*.tsx)  ->  what you see
```

Five facts to be able to say out loud.

1. **Every number on screen comes from the API.** `client.ts` is the only code that talks to
   the network. If a call fails, the page shows an error box ("No figure is shown in place of
   the missing one"), never a made-up value. A mock mode exists (`VITE_USE_MOCK=1`) but it
   puts a permanent striped banner on every page.
2. **Every response carries a `meta` block** (`sources`, `n`, `split_regime`, `generated_at`,
   `thresholds`). The grey monospace line under almost every panel is that block printed out.
   That is the "provenance footer".
3. **The status rule lives in exactly one place:** `KAVAL/kaval/audit.py`, function
   `agreement_status`. The browser never decides if a parcel is DISPUTED. It sends three
   threshold numbers to the API, the API runs `agreement_status` again, and the page draws
   what came back. That is why the map, the worklist and the auto-clear saving can never
   disagree with each other.
4. **The API refuses to serve a metric without a split regime.** `metric_response()` in
   `api/main.py` raises an error if `split_regime` is missing, and the page shows an
   amber-bordered "split regime not reported by the API" chip instead of guessing.
5. **Thresholds are query parameters.** The defaults (0.80 / 0.35 / 0.65) come from
   `kaval/config.py`; the page learns them from the API at boot (`meta.thresholds` of
   `/parcels?limit=1`) and does not contain them.

### The status rule in plain words (it is the whole product)

`agreement_status` in `kaval/audit.py` goes through five steps, and later steps override
earlier ones.

1. Start every parcel as **UNCERTAIN**.
2. If satellite and declared **agree**, calibrated confidence is at least `confidence_high`
   (0.80), and the Record Trust Score is at least `trust_high` (0.65): **CONFIRMED**.
3. If they **disagree** and calibrated confidence is at least `confidence_high`: **DISPUTED**.
4. If the Record Trust Score is **below** `trust_floor` (0.35): **UNVERIFIABLE**. This beats
   steps 2 and 3, deliberately: if the record is too weak to test, the model's opinion is
   irrelevant.
5. If there is no declared record at all: **UNSEEN**.

(Today this gives, from `GET /audit/status-summary`: CONFIRMED 4,825, DISPUTED 784,
UNCERTAIN 8,429, UNVERIFIABLE 272, total 14,310. These equal
`docs/evidence/p6_audit.json` → `agreement_status_counts`.)

---

## 1. The shell (visible on every tab)

### 1.1 Header
Source: `src/App.tsx`.

- **"KAVAL" and the line "The classifier is the instrument. The product is the audit."**
  The one-sentence thesis. The model is a measuring tool; what we sell is the audit of the
  survey records.
- **Six tabs:** Audit map, Village audit, Field worklist, Auto-clear, Leakage Ladder, Analyst.
  The tab is stored in the web address (`#map`, `#villages`, `#worklist`, `#autoclear`,
  `#validation`, `#analyst`), so you can send a reviewer straight to one. The map also takes
  `#map?village=Sivagiri`-style links.
- **API-health chip** (top right, "API ok"). Calls `GET /health`.
  - A plain "API ok" chip means the API answered and `phases_available` is present. If a
    pipeline phase had not produced its files the chip would add "missing: audit, p4, ..."
    (today `GET /health` returns `{"audit": true, "p4": true, "p5": true, "p6": true}`, so
    nothing is missing).
  - "API unreachable" (red-bordered chip): nothing answered on the proxied port. Start the API.
  - "not the KAVAL API" (warning): something answered `/health` but without
    `phases_available`. This exists because an unrelated app sits on port 8000 on the
    development machine.
  - Question it answers: "is what I am looking at live, and is it ours?"
- **Theme selector** ("system theme / light / dark"). Pure display. Remembered in the
  browser (`localStorage`). Dark mode uses a separately chosen set of colour steps, not an
  inversion, and the status colours were validated for colour-blind safety in both modes
  (`docs/evidence/p8_palette.md`).

### 1.2 The right-hand Thresholds rail
Source: `src/components/ThresholdControls.tsx`, `src/lib/thresholds.tsx`. It appears on
every tab, but it only changes **three** tabs: Audit map, Field worklist and Auto-clear.
(On Village audit, Leakage Ladder and Analyst, moving it does nothing. The analyst's
request carries only the question text, not the sliders.)

Three sliders. Defaults come from the API; "config:" under the buttons repeats them.

| Slider | Range | Default today | What it controls |
|---|---|---|---|
| `confidence_high` | 0.30 to 0.99 | 0.80 | The calibrated-confidence bar. At or above it, a disagreement is DISPUTED and an agreement may be CONFIRMED. 0.80 is the brief's own 80% line. |
| `trust_floor` | 0.00 to 0.90 | 0.35 | Below this Record Trust Score the record cannot be tested at all: UNVERIFIABLE, whatever the model thinks. |
| `trust_high` | 0.00 to 0.99 | 0.65 | A record must reach this trust before an agreement is allowed to auto-clear a visit. |

- **"Reset to API defaults"** button: greyed out until you move something. When moved, a
  "moved from config" chip appears.
- **"config: ..." and "sent as: confidence_high=0.8&trust_floor=0.35&trust_high=0.65"**
  The exact query string being sent to the API. This is the "an audit with invisible
  thresholds is not auditable" rule made visible.
- **How it reacts.** After you stop moving a slider for about a fifth of a second
  (debounce), each affected tab re-queries the API with the new triple. Nothing is
  calculated in the browser. Live examples (`GET /audit/status-summary` with one threshold
  changed):

  | Change | CONFIRMED | DISPUTED | UNCERTAIN | UNVERIFIABLE |
  |---|---:|---:|---:|---:|
  | default (0.80 / 0.35 / 0.65) | 4,825 | 784 | 8,429 | 272 |
  | `confidence_high` 0.90 | 3,761 | 405 | 9,872 | 272 |
  | `confidence_high` 0.95 | 1,465 | 122 | 12,451 | 272 |
  | `trust_floor` 0.50 | 4,825 | 604 | 6,737 | 2,144 |
  | `trust_high` 0.80 | 1,056 | 784 | 12,198 | 272 |

  Reading the table: raising `confidence_high` makes the system more demanding, so both
  DISPUTED and CONFIRMED shrink and UNCERTAIN grows. Raising `trust_floor` moves parcels
  into UNVERIFIABLE. `trust_high` only affects CONFIRMED (and so auto-clear).

### 1.3 "Why this map is not coloured by crop" note (bottom of the rail)
Static explanation text. Read it as the answer to the first question every reviewer asks:
a crop-coloured map answers "what is growing" (every classification demo does that); ours
answers "what should a surveyor do next". Disagreement is the product, so the most salient
colour belongs to DISPUTED parcels and agreement recedes. Crop class is still available as
a secondary layer on the map tab.

### 1.4 The colour vocabulary (used on the map, legend, tables and charts)
Defined in `src/lib/palette.ts` and the colour variables in `src/styles.css`.

| Status | Colour | How it is drawn | Plain meaning | Action |
|---|---|---|---|---|
| **CONFIRMED** | blue | faint wash (22% fill, thin line) | satellite agrees with the survey at high confidence, on a record we trust | auto-clear next season |
| **DISPUTED** | red | strongest: 95% fill, thickest line | satellite disagrees with the survey at high confidence | top of the field worklist |
| **UNCERTAIN** | amber | medium (50% fill) | the model cannot separate the classes here (confidence below the bar) | route by remaining budget |
| **UNVERIFIABLE** | teal, **hatched** (45 degree stripes) | 85% fill with stripes | the record is too weak to test (large photo bag, distant photo, mixed crop) | re-survey the **record**, not the parcel |
| **UNSEEN** | grey **outline only**, dashed, no fill | no fill | no survey record exists, so nothing to agree or disagree with | satellite-only, no audit claim (0 parcels today) |

**Why not green and red?** Two reasons, and say both.

1. *Colour blindness.* We tested green against red with the colour-validation tool: under
   the most common red-green colour blindness the two measured a colour difference of only
   4.1 (the tool's pass bar is far higher), so "skip the visit" and "send someone
   tomorrow" would look the same to roughly 1 in 12 men. Blue against red is a validated
   pair (`docs/evidence/p8_palette.md`). Be candid: in dark mode teal against red is in the
   tool's warning band (7.2), which is exactly why UNVERIFIABLE always carries a hatch as a
   second signal.
2. *Meaning.* Green-good and red-bad would claim a verdict we do not have. We claim two
   sources disagree. Blue to red reads as "opposite", not "better to worse".

**Why is UNVERIFIABLE hatched?** It is a different kind of problem, not a bigger amount of
the same problem. DISPUTED, UNCERTAIN and CONFIRMED sit on one axis (how much the two
sources agree). UNVERIFIABLE says the evidence is bad, so a field visit would not fix it.
Stripes say "different category".

**Why does CONFIRMED fade and DISPUTED shout?** Salience is assigned by fill opacity, line
thickness and (for dots) size, not by hue. Otherwise amber UNCERTAIN (8,429 parcels) would
be the loudest thing on the map while DISPUTED (784) is the money.

The same status swatch (colour, hatch or outline) is repeated in the legend, the status
table and the worklist "Status" column, so the vocabulary is learnt once.

### 1.5 Common footers and chips (they repeat on every tab)
- **Provenance footer** (grey monospace line): `sources · n=... · split: ... · date`.
  `sources` lists the data files behind the panel. `n` is the number of items the API
  counted for that response (see the caution below), `split` is the validation regime, the
  date is when the API generated the response. Source: `Provenance` in
  `src/components/common.tsx`, filled from `meta`.
  *Caution:* `n=` is whatever the API counted for that call, so it means different things:
  the status-summary footer shows `n=4` (four status rows, not four parcels), the ladder
  footer `n=7`. Only on `/parcels`, the worklist and auto-clear is it a parcel count.
- **"split: 3-event" chip** (blue-grey pill) next to a metric. Source: `RegimeChip`. It
  prints `meta.split_regime` of that response.
- **Tiles**: a labelled big number with a small note under it. Source: `Tile`.

---

## 2. Tab 1: Audit map
File: `src/views/AuditMapView.tsx`, with `ParcelPanel.tsx`, `StatusLegend.tsx`.
Question it answers: *where are the parcels a surveyor should walk to, and why is each one
there?*

### 2.1 Control row (top)
- **Village** dropdown. Choices: "all villages" plus the 21 survey villages (names come
  from `GET /summary/crop-area?group_by=village`). Picking one re-queries `/geo/parcels` and
  `/parcels` with `village=` and zooms the map to it, and writes `#map?village=...` in the
  address bar. Useful because "all villages" shows only a sample (see "Parcels fetched").
  Live example: "Rayagiri - Part-2" has 975 parcels (537 CONFIRMED, 432 UNCERTAIN, 6
  DISPUTED, 0 UNVERIFIABLE; from `GET /parcels?village=...&status=...`, field `meta.n`).
  "Thenmalai - Part-2" has 764 (111 / 61 / 497 / 95).
- **Colour by**: "agreement status" (default, the decision) or "crop class (secondary)". Crop
  mode uses the 8 categorical colours, and an amber-bordered notice reminds you it is the secondary
  layer. Crop colours come from `y_pred`, the satellite's class.
- **Parcels fetched**: 1000 / 3000 / 6000. How many parcel polygons to request. The API
  draws a **random sample** (`df.sample(limit, random_state=0)`) when more match, so the
  map is not biased to one corner. Default 3,000 of 14,310, about one in five. The footer
  says so ("3,000 polygons drawn of 14,310 matching parcels · simplified 2 m").
- **Reserve forests** checkbox. Shows or hides the four Reserve Forest polygons (Vasudevanallur
  R.F, Naranapuram R.F, CHINTAMANI R.F, Sivagiri Reserve Forest; `GET /geo/villages`
  marks them `is_reserve_forest`, because their village code is `YYY`, not a number).
- **Export GeoJSON / Export CSV**: downloads from `GET /export` for the chosen village, **at
  the thresholds the map is drawn at** (the links carry `confidence_high`, `trust_floor`,
  `trust_high`), so the file's statuses match the screen.

### 2.2 The map itself
- **Base map:** OpenStreetMap tiles (the faint streets/labels) with Leaflet. Needs internet
  for the tiles only; everything else is local.
- **Dashed grey hairlines:** village boundaries from `GET /geo/villages` (source file
  `Dataset/Administrative_Boundary/Sivagiri_Villages.geojson`, simplified about 10 m so the
  browser can draw it).
- **Filled, dashed grey areas:** the four Reserve Forests. Legend entry says "Negative
  control": there is no ground truth there, so a confident crop call inside them would be
  evidence of miscalibration, not of farmland. They deliberately get **no agreement
  status**.
- **Coloured parcel polygons:** one per parcel from `GET /geo/parcels?simplify_m=2&limit=...`
  plus the three thresholds. Geometry file: `data/derived/parcel_geometry.gpkg` (written by
  `scripts/p3_feature_store.py` from the Phase 2 parcel layer); status columns come from
  `audit.parquet` (written by `scripts/p6_audit.py`). Geometry is simplified to 2 m on the
  server (in metres, then converted back to latitude/longitude) so the browser can draw it;
  raw polygons would not render at taluk scale.
- **Hover tooltip** on a parcel: status, parcel id, "declared X · satellite Y", calibrated
  confidence, trust score, area in hectares, and the hint to click.
- **Click a parcel** opens the audit-trail panel (2.3). Click the legend to hide statuses.
- **Zoom +/-** buttons top left, standard Leaflet.
- **Footer:** `data/derived/parcel_geometry.gpkg · data/derived/audit.parquet · n=3,000 ·
  split: 3-event · ...` plus "N polygons drawn of M matching parcels · simplified 2 m".
- If polygons were unavailable (HTTP 503 "Phase 3 has not run") the map falls back to
  centroid dots and an amber-bordered notice says "These are points, not land".
- If you pick a village that carries no records, an amber-bordered chip says the map is empty
  because the filter matches nothing.

### 2.3 Parcel audit-trail panel (opens on the right when you click a parcel)
Source: `GET /parcels/{parcel_id}`. Everything is read from `audit.parquet`.

Top: status badge, the parcel id (`{village code}_{survey no}_{subdivision}`, e.g.
`152_399_1`), the village and survey number, a one-sentence meaning of the status, and an
arrow line with the action.

**Block "The disagreement"**

| Row | What it is | Question it answers |
|---|---|---|
| Declared by surveyor | the `y_true` crop in the survey | what does the record say? |
| Predicted from satellite | the model's crop | what does the satellite say? |
| Suggested correction | the crop the model prefers *if* confident learning flags the label; blank when there is no confident alternative | what would we change it to? |
| Calibrated confidence | the model's probability for its own prediction after isotonic calibration, so that "80%" really means about 80% right (calibration error 0.0046 after vs 0.1247 before, from `GET /validation/calibration`) | how sure is the satellite? This number routes the budget. |
| Raw confidence | the uncalibrated model output, shown only so the gap is visible (for `152_399_1` raw is 100.0% against calibrated 97.1%) | how overconfident would the raw model be? Never used for routing. |
| P(declared label needs correction) | see the explanation below | how likely is it that the record needs correcting? |

**Block "Provenance of the record"**

| Row | What it is |
|---|---|
| Record Trust Score | 0 to 1, a weighted mean of seven components: bag size 25%, bag support (MIL attention) 25%, photo distance 20%, stage plausibility 10%, mixed-crop flag 10%, geometry source 5%, within-parcel heterogeneity 5% (weights from `kaval/config.py`, listed in `p6_audit.json` → `trust_weights_applied`). Low trust means the record is weak evidence. |
| Capture event | the id of the photograph the label came from |
| Parcels sharing this photograph | "bag size": one photograph, one label, copied to every parcel in the bag. Up to 43 in the supplied data (`/evidence/forensics` → `max_parcels_per_capture_event`). The bigger the bag the less the label says about this particular parcel. |
| Photograph taken | distance from the photo's geotag to the parcel centre. The median over all records is 1,436 m and 62.3% are over 1 km (`/evidence/forensics`). |
| Geometry source | `ftw` = the satellite found this parcel as its own field; `ftw_shared` = several legal parcels sit on one physical field; `voronoi` = fallback tessellation. Lower fidelity lowers trust. |
| Physical field / Legal parcels sharing this field / Snapped to field by / Field area | which satellite-delineated field the parcel was matched to, how many legal parcels share it, how far the survey point was moved to reach it, and the field's area. (Delineation finds farmed fields, not legal parcels; 1.94 parcels share a field on average.) |
| Declared stage | growth stage written in the record (vegetation, full_growth, ...) |
| Village code mismatch | "yes" if the record's village code disagrees with the polygon the point falls in (1,930 records, 13%, mostly the Viswanathaperi 911/912 pair) |
| Parcel area | in hectares |
| Footer | sources, `n=1`, split regime, time |

**Worked example (live):** parcel `152_399_1`, Rayagiri - Part-2, survey 399/1. Declared
Rice (Paddy), satellite Sugarcane, calibrated confidence 97.1%, trust 0.846, P(label needs correction)
81.7%, bag size 1, photograph 743 m away, geometry `ftw` (its own field), field area
1.72 ha. Status DISPUTED. It is the number 1 row of the worklist at default thresholds.
`GET /parcels/152_399_1`.

**For UNVERIFIABLE, this panel is the whole finding.** Live example `142_521_1`
(Thenmalai - Part-2): declared Maize and satellite Maize (they *agree*), but trust 0.181,
shared by 25 parcels, photograph 3,402 m away, geometry `ftw_shared` (6 legal parcels on
the one field). The status is UNVERIFIABLE because the evidence is too weak to say
anything. `GET /parcels/142_521_1`.

#### What "P(declared label needs correction)" means
It is the model's estimate of the chance the *record* needs correcting. It comes from
confident learning in `kaval/audit.py::label_error_probability`: for each crop it takes the
average probability the model gives to parcels carrying that label; a parcel is flagged when
the model's probability for the *declared* crop falls below that bar while another crop
clears its own bar. The raw gap is not a real probability, so it is multiplied by the
model's measured accuracy, which is also a hard ceiling:
`p_wrong <= 0.8171` (`p6_audit.json` → `confident_learning.model_accuracy_used_as_cap`).
That is why many top worklist rows show exactly 82%: they sit on the ceiling. It is a model
estimate, not a measured error rate. Use the words "P(label needs correction)" out loud.

### 2.4 Card: "Agreement status across the taluk"
Source: `GET /audit/status-summary` with the three thresholds. Re-queried when sliders move.
- **Stacked bar:** one bar split into the status shares (hover for count and share).
  UNVERIFIABLE is hatched here too.
- **Table, one row per status:** Status (swatch + name), **Parcels** (count), **Area**
  (hectares, from the parcel area), **Action** (what to do).

  | Status | Parcels | Area (ha) |
  |---|---:|---:|
  | CONFIRMED | 4,825 | 870.8 |
  | DISPUTED | 784 | 100.8 |
  | UNCERTAIN | 8,429 | 1,143.0 |
  | UNVERIFIABLE | 272 | 23.0 |
  | UNSEEN | 0 | 0 |

  (live, default thresholds; same as `p6_audit.json` → `agreement_status_counts` and
  `agreement_status_area_ha`). UNSEEN is 0 because every supplied parcel has a survey
  record; it is kept in the vocabulary because in production a parcel with no record is a
  real state.
- Counts cover **all 14,310 parcels**, not just the sample drawn on the map.

### 2.5 Card: "Legend"
Four coloured rows plus UNSEEN, each with swatch, status name, current parcel count and the
action. **Click a row to hide that status on the map** (hidden statuses dim to 40%). Hovering shows the one-sentence meaning. Below it, the separate "Reserve Forest"
entry (dashed, "Negative control, no ground truth").

---

## 3. Tab 2: Village audit
File: `src/views/VillageAuditView.tsx`. Question: *where does the satellite crop mix differ
most from the published village report, and by how much?*

### 3.1 Two caveat boxes (always open, yellow)
Texts come from the API payload (`independence_caveat`, `scale_caveat` in `GET
/summary/registry-delta`), so the page cannot show the comparison without them.
- **Not independent validation.** The Agrisnet village figures are the published aggregate of
  the *same* Digital Crop Survey whose parcel sample is our ground truth. So we are auditing
  the survey's own published numbers against the satellite; this is a consistency check, not
  a second independent survey.
- **Share, not hectares.** We compare each crop's *share* of village cropped area, because
  our parcels cover only a fraction of each village; hectares would measure sampling
  coverage.

### 3.2 Filter row
- **Minimum registry area** (0, 1, 5, 10, 25 ha; default 1): hides tiny village x crop rows
  where a share is unstable. Re-queries the API (`min_registry_ha`). Live: 0 ha gives 90
  rows, 1 ha gives 76, 25 ha gives 50.
- **Crop** and **Village**: filter what is shown, in the browser only, from the rows already
  returned.

### 3.3 Three tiles
| Tile | Meaning | Today |
|---|---|---|
| Registry compared | the season of the registry used (`season`) | Rabi 2024 (Tamil Nadu Agrisnet village-wise Digital Crop Survey report) |
| Village x crop rows | rows after your filters, "of N returned at the area filter" | 76 of 76 |
| Registry area outside our scope | share of registry hectares in crops or villages the satellite model does not cover (`registry_out_of_scope_pct`) | 8.8% |

### 3.4 Chart: "Village x crop, sorted by share divergence"
Blue and red bars either side of a zero line, longest first (top 18 shown). Chips: the split
regime and "percentage points of village crop share".
- **Bar length** = `delta_share` x 100: satellite share of the village's crop area minus
  registry share, in percentage points (pp).
- **Red (left)** = satellite below the registry share; **blue (right)** = satellite above.
  (Here blue/red mean the sign of the gap, not a status.)
- **Sorted by size of divergence**, because the question is "where should a district officer
  look first".
- Hover shows registry share, satellite share and mean confidence for that bar.
- Live top bars (`GET /summary/registry-delta?min_registry_ha=1`): Rayagiri - Part-1 ·
  Sugarcane **-34.6 pp** (registry 58.2%, satellite 23.7%); Thenmalai - Part-2 · Rice
  (Paddy) **+32.6 pp** (registry 19.8%, satellite 52.3%); Rayagiri - Part-1 · Rice (Paddy)
  **+28.4 pp**; Inamkovilpatti · Coconut **+23.1 pp**.
- Footer: sources `village_registry.parquet`, `data/raw/tn_crop_registry.csv`, `n=76`,
  `split: 3-event`.
- Explanatory line under the chart: neither side is assumed correct, and agreement is
  weaker evidence than it looks.

### 3.5 Card: "Systematic bias by crop"
Satellite share minus registry share, pooled over villages, so a consistent sign is a model
or registry habit, not a village finding. Columns: **Crop**, **Registry share**,
**Satellite share**, **Bias (pp)** (coloured by sign). Live: Sugarcane registry 13.7%,
satellite 7.2%, bias **-6.5 pp**; Rice (Paddy) 62.8% vs 66.4%, **+3.6 pp**; Maize +2.1 pp.
Source: `systematic_bias_by_crop` from `docs/evidence/p7_registry.json` (script
`scripts/p7_registry_comparison.py`). This card is pooled over all villages **by design** (it asks "is there a habit across the taluk?"), so the Crop/Village filters do not apply to it.

### 3.6 Card: "Full comparison" (the table)
One row per village x crop, largest divergence first. Columns:

| Column | What it is | How computed |
|---|---|---|
| Village | survey village | |
| Crop | crop class | |
| **Registry ha** | hectares the Agrisnet registry publishes for that crop in the village | from `tn_crop_registry.csv` |
| **Registry share** | that crop's share of the village's registry area | registry ha / village registry total |
| **Satellite ha** | hectares our model assigns (crop area from the audited parcels, aggregated at field level by `kaval/area.py`) | sum of parcel area by predicted crop, one crop per physical field |
| **Satellite share** | that crop's share of the village's satellite-assigned area | satellite ha / village total |
| **Delta share (pp)** | satellite share minus registry share, in percentage points | shown signed; red negative, blue positive |
| **Implied ha delta** | what the share gap would mean in hectares *if* it applied to the registry's village area. An extrapolation, never a measurement. | delta share x registry village area |

Live row: Rayagiri - Part-1 · Sugarcane: registry 431.2 ha (58.2%), satellite 13.1 ha
(23.7%), delta **-34.6 pp**, implied -256.0 ha. Read the huge gap between 431 and 13 ha as
the scale caveat in action: our sample covers a fraction of the village, so only the share
is meaningful. Another live row: Rayagiri - Part-2 · Rice (Paddy) registry 99.3%, satellite
95.2%, delta -4.1 pp: this village agrees.
Chip: split regime. Footer as above.

### 3.7 Card: "Satellite-estimated crop area — whole taluk / <village>"
Follows the page's **Village** filter. With no village chosen it shows taluk totals from
`GET /summary/crop-area?group_by=taluk&source=predicted`; with a village chosen, that
village's rows from `group_by=village`. The totals are computed by the API (`kaval/area.py`,
which counts a shared physical field once, under one crop), never summed in the browser.
One bar per predicted crop, with hover note "N parcels · mean calibrated confidence", plus
the hectares sitting in shared fields whose records disagree, when there are any. Live totals (`group_by=taluk` call): Rice (Paddy) 1,523.2 ha (9,498 parcels,
mean confidence 0.853); Coconut 335.7 ha (0.769); Maize 160.2 ha (0.749); Sugarcane 71.1 ha
(0.776); Banana 44.9 ha (0.586); Other 2.6 ha (0.456). The point of the confidence: a large
area resting on low confidence (Banana, Other) is not a usable statistic. The API's
`conflicted_area_ha` (fields whose records disagree on the label) appears in the hover note.
Chip: split regime. Footer: sources, n.

This tab ignores the right-hand thresholds rail.

---

## 4. Tab 3: Field worklist
File: `src/views/WorklistView.tsx`. Question: *if the department can afford N visits, which N
parcels, and what are they worth compared with picking N at random?*

### 4.1 Card: "Verification budget"
- **Slider "Field visits available (N)"**, 10 to 5,000 in steps of 10, default 500. The
  number to its right is the live N. After you stop moving it for about a quarter second,
  the page calls `GET /audit/worklist?budget=N&confidence_high=...&trust_floor=...&trust_high=...`.
- **Village** dropdown: "whole taluk" or one village. Adds `village=` so the queue is
  restricted to it.
- The objective is "expected label corrections", not a heuristic ranking.

### 4.2 Three tiles
All from `data.economics` of the worklist response. Producer: `kaval/audit.py::route_budget`
(called by the API; data from `audit.parquet`, written by `scripts/p6_audit.py`).

| Tile | What it shows | How computed | Today (N=500) |
|---|---|---|---|
| **Estimated corrections: KAVAL routing** | how many of the N visits we expect to end with the record being corrected | sum of P(label needs correction) over the N routed parcels. A model estimate, not a count of confirmed corrections. | **390.5**, "from 500 visits · 3.49% of parcels · 142.8 ha covered" |
| **Estimated corrections: random visits** | what N randomly picked parcels would give | average of 200 random draws of N parcels, same sum | **53.9**, "sd 6.03" |
| **Ranking quality** | mean calibrated confidence of the routed parcels versus all disagreements | are the better-evidenced disagreements visited first? | **0.734 vs 0.652**, and "498 of 500 routed parcels are disagreements (targeting 5.45x, capped at 5.47x by construction, so not a result)" |

Notes on the third tile, which is the honest-weakness tile. "Targeting 5.45x" is routed
disagreements divided by random expected disagreements; it equals 1 divided by the base
disagreement rate (0.183), at any budget below the number of disagreements (2,617), by
arithmetic. So it measures *coverage*, not ranking skill, and the page says so itself.
`targeting_is_pinned_by_construction: true` is in the API response. The informative number is
the confidence pair, 0.734 against 0.652. As the budget grows the routed mean confidence
falls toward 0.652 (live: N=120 gives 0.759; N=1,000 gives 0.716; N=2,000 gives 0.708),
because the queue is dipping into weaker-evidenced cases.

Expected corrections at other budgets (live, same call):

| N | Routed | Random (sd) | Routed disagreements found | Routed mean confidence |
|---:|---:|---:|---:|---:|
| 120 | 94.5 | 13.1 (3.0) | 120 | 0.759 |
| 500 | 390.5 | 53.9 (6.0) | 498 | 0.734 |
| 1,000 | 764.5 | 108.8 (8.1) | 972 | 0.716 |
| 2,000 | 1,494.5 | 218.4 (10.5) | 1,882 | 0.708 |
| 5,000 | 1,569.7 | 547.9 (15.2) | 2,300 | 0.727 |

Past about N = 2,600 the extra visits add almost nothing (1,494.5 at 2,000 versus 1,569.7 at
5,000), because disagreements run out.

### 4.3 Chart: "Routing versus the counterfactual at N = 500"
Two horizontal bars on one axis in the **same blue** on purpose: the random bar is the same
quantity spent differently, not a rival series. The random bar has a whisker (the standard
deviation of the 200 draws). The chip says "estimated corrections = Σ P(declared label is
wrong), a model estimate". Hover for the note. Below: the provenance footer, the
`split: 3-event` chip, and a chip "thresholds sent: confidence_high=0.80 · trust_floor=0.35 ·
trust_high=0.65".

### 4.4 Card: "The queue"
- **Export CSV** (primary button) and **Export GeoJSON**: call `GET /export?fmt=...&budget=N`
  plus the village and the three thresholds. The file reproduces this on-screen queue (same
  rows, same order, same thresholds), with an extra `rank` column. This is what a field
  officer uses, not this screen.
- **The table**, highest priority first, **first 400 rows only** (the line under the table
  says so; the export has all N). Columns:

| Column | What it is |
|---|---|
| **#** | position in the queue (rank 1 = visit first) |
| **Parcel** | parcel id, `village code_survey no_subdivision` |
| **Village** | village name |
| **Status** | status swatch and name at the current thresholds |
| **Declared** | crop in the survey record |
| **Satellite** | crop the model predicts |
| **P(correction)** | P(label needs correction): model's estimate that the record should change (see 2.3). Capped at 82% (the model's accuracy), so the top rows tie |
| **Conf.** | calibrated confidence of the *satellite's* prediction |
| **Trust** | Record Trust Score, 0 to 1 |
| **Bag** | how many parcels shared this record's photograph |
| **Photo** | how far from the parcel the photograph was taken (m or km) |
| **Area** | parcel area in hectares |

  The queue is ranked by **priority = P(label needs correction) x area weight**, where area
  weight is the parcel's area divided by the median area, clipped to between 0.25 and 4
  (`kaval/audit.py::routing_priority`, constants in `kaval/config.py`). The idea: a visit to
  a bigger parcel resolves more land. The "P(correction)" column alone is therefore not strictly
  in order. The area weight steers the ranking only; it is never multiplied into the
  corrections count.
- **Why the two columns "P(correction)" and "Conf." can look contradictory.** Live rank 5,
  `15_137_2` (Patakurichi): declared Banana, satellite Maize, P(correction) 82% but Conf. 34%
  and status UNCERTAIN. The model is not confident in Maize; it just gives the declared
  Banana very little probability. Conf. answers "how sure is the satellite?", P(correction)
  answers "how little support does the record get?". Different questions.
- **Not all rows are DISPUTED.** At N=500 the live queue holds 216 DISPUTED, 275
  UNCERTAIN, 9 UNVERIFIABLE: it chooses by expected correction, not by label.
- Live top of the queue at defaults (`GET /audit/worklist?budget=500`):

  | # | Parcel | Village | Declared | Satellite | P(correction) | Conf. | Trust | Bag | Photo | Area |
  |--:|---|---|---|---|---:|---:|---:|---:|---:|---:|
  | 1 | 152_399_1 | Rayagiri - Part-2 | Rice (Paddy) | Sugarcane | 82% | 97% | 0.85 | 1 | 743 m | 1.72 ha |
  | 2 | 7_176_3 | Ramanathapuram | Other | Rice (Paddy) | 82% | 86% | 0.68 | 3 | 1.53 km | 1.08 ha |
  | 3 | 7_127_1 | Ramanathapuram | Other | Rice (Paddy) | 82% | 92% | 0.53 | 13 | 2.75 km | 0.70 ha |

  ("Other" is a catch-all: crops with fewer than 5 independent capture events are merged
  into it, per `MIN_EVENTS_PER_CLASS` in `kaval/config.py`.)
- Provenance footer: `data/derived/audit.parquet · n=500 · split: 3-event`.

---

## 5. Tab 4: Auto-clear
File: `src/views/AutoClearView.tsx`. Question: *which parcels need no visit next season,
and what does that save?* Data: `GET /audit/auto-clear` + thresholds. "Cleared" means
status CONFIRMED. Producer of the data: `audit.parquet` via `scripts/p6_audit.py`.

### 5.1 Three tiles
| Tile | Meaning | Today |
|---|---|---|
| **Parcels safe to skip** | count of CONFIRMED parcels | **4,825**, 33.7% of parcels, 870.8 ha |
| **Surveyor-days saved** | cleared parcels divided by parcels per surveyor-day (25) | **193.0**, against a baseline of 572.4 days to visit everything (14,310 / 25) |
| **Expected residual error rate** | average of (1 - calibrated confidence) over the cleared parcels, with its split regime chip | **7.6%** (`split: 3-event`), "about 365 of the 4,825 cleared parcels are expected to be cleared in error" |

The "residual error" is a **proxy, not a bound**. Auto-clear fails only where satellite and
surveyor are wrong in the *same* way, which cannot be measured against a label the surveyor
supplied.

### 5.2 Card: "What this panel does not claim"
Explains why there is no "accuracy within the cleared set": CONFIRMED is *defined* as the
model agreeing with the survey, so agreement inside the cleared set is 100% by construction.
It would look like a validation result and carry no information. The card shows the API's
`residual_note` verbatim ("Settle it with an independent field audit of a CONFIRMED
sample"), the split chip, and a chip "7.6% x 4,825 cleared ≈ 365 parcels".

### 5.3 Chart: "Where the season's surveyor-days go"
Three bars on one axis (days): "Visit every parcel (status quo)" 572, "Visit only what KAVAL
does not clear" 379, "Saved by auto-clear" 193. (572.4 minus 193.0 is 379.4.)

### 5.4 Card: "The cost assumption"
Shows `parcels_per_surveyor_day` = **25** and the API's note: "Assumption. Derived from 3,204
capture events over a ~7-day survey window across 21 villages in the supplied sample; revise
with FarmwiseAI's actuals." The page says this is the one number FarmwiseAI can replace with
an actual. It comes from `VISIT_COST` in `kaval/config.py`, passed through the API
(`cost_assumption`).

### 5.5 Card: "What auto-clear does and does not claim" (four bullets)
It claims the *record* is consistent with the satellite at the set thresholds, not that the
crop is certainly what the record says; the residual is estimated, and settling it needs an
independent field audit of a sample of CONFIRMED parcels (nobody has done one); it clears a
parcel from *next season's* list, not permanently; raising `trust_high` shrinks the set so
saving and risk move together.

### 5.6 How it reacts to the rail
Live: `confidence_high` 0.90 gives 3,761 parcels, 150.4 days saved, residual 5.2% (about 196
wrongly cleared). `trust_high` 0.80 gives 1,056 parcels, 42.2 days, residual 7.7%.
Fewer cleared, lower risk or similar, smaller saving: the trade-off the sliders exist to show.

---

## 6. Tab 5: Leakage Ladder (the credential)
File: `src/views/ValidationView.tsx`. Question: *why should I believe the headline number?*
Data: `GET /validation/ladder`, `/validation/confusion`, `/validation/calibration`,
`/evidence/forensics`. This tab does not depend on the thresholds rail. All numbers are
from `docs/evidence/p4_results.json` (script `scripts/p4_ladder_and_baselines.py`),
`p6_audit.json` and `gt_forensics.json` (script `scripts/gt_forensics.py`).

### 6.1 Card: "The Leakage Ladder"
Subtitle: one model, one feature set, four validation splits; only the split changes. The
brief's own clause, that spatial or parcel leakage invalidates a claimed result, is why this
is in the product and not in an appendix.

**Three tiles**
| Tile | Meaning | Today |
|---|---|---|
| **Headline accuracy** | best head under the headline split, with its regime chip and "head: MLP. Never quoted without the regime" | **81.7%**, `split: 3-event`, MLP head |
| **Headline macro F1** | average of per-class F1, so rare classes are not hidden by the 63% rice majority | **0.564**, `split: 3-event` |
| **Cost of honesty** | accuracy lost moving from the loosest rung (1-random) to the strictest (4-village), same model | **18.9 pp** (89.7% to 70.8%) |

**Chart "Accuracy and macro F1 under each split".** Two bars per regime (blue accuracy,
orange macro F1) on a 0 to 1 axis, with whiskers for the fold standard deviation. Chip: "split:
all four regimes reported side by side" (the only place that wording is correct, because the
chart really shows four).

**Table** (same data; the bold row with a star is the headline regime):

| Split regime | Accuracy | Macro F1 | Log loss | What it tests |
|---|---:|---:|---:|---|
| 1-random | 89.7% ± 0.4% | 0.772 | 0.343 | rows shuffled; parcels from the same photograph land on both sides of the split. Diagnostic only |
| 2-parcel | 89.5% ± 0.5% | 0.769 | 0.343 | grouped by parcel id; barely moves the number, so parcel grouping is no protection |
| **3-event ★** | **81.2% ± 2.2%** | **0.528** | 0.823 | grouped by capture event: one photograph, one label, one side of the split. THE HEADLINE REGIME |
| 4-village | 70.8% ± 9.5% | 0.326 | 1.459 | grouped by the village the parcel really falls in; tests transfer to unseen land |

These four rungs hold the model fixed at **LightGBM**; the tile above shows the **MLP** head
(81.7%, 0.564), the best of four heads at the same 3-event regime. Both are capture-event
grouped; name the head when you quote either. The ± is the standard deviation over 5 folds
(village grouping, ±9.5 pp, is noisy because there are only 21 villages).

Under the chart, an on-screen note explains exactly this: why the ★ 3-event row shows the
LightGBM figure while the headline tile shows the best head (MLP) at the same split.

**Reading the ladder (the story).** Random split 89.7% to parcel-grouped 89.5% (nothing
changes) to event-grouped 81.2% (the real drop). The obvious control (group by parcel) gives
false comfort, because the leak is the photograph, not the parcel: 14,643 records trace back
to only 3,204 capture events (4.57x), one photograph can label up to 43 parcels, and no event
contains more than one crop.

**Two side-by-side charts**
- **"Model heads, identical folds"** (`split: 3-event`): LightGBM 81.2% / 0.528, RandomForest
  79.1% / 0.469, LogisticRegression 80.6% / 0.537, **MLP 81.7% / 0.564**. Same rows, same
  folds, only the model changes.
- **"Feature sources, identical folds"** (`split: 3-event`): GSE only (64-d) 81.5% / 0.563;
  Seasonal S1/S2 only 73.7% / 0.399; GSE + seasonal (76) 81.7% / 0.564 (this is the
  headline configuration); Presto only (128-d) 74.2% / 0.452; GSE + Presto (192) 81.3% /
  0.559. (GSE = Google Satellite Embeddings; Presto = a remote-sensing foundation model.)
- **Mini-table "Each source against GSE only, macro F1, fold by fold"**: **Mean Δ** (average
  difference from GSE alone), **SD of Δ**, **Folds ahead** (how many of 5 folds the source
  beat GSE), **Verdict**. A gap smaller than fold-to-fold noise is labelled "underpowered:
  within fold noise", not called a result. Live: Presto only Δ **-0.111**, 0/5 folds ahead,
  "behind" (a real gap); GSE + Presto Δ **-0.004**, 1/5, underpowered (no measurable gain);
  GSE + seasonal Δ +0.001, 2/5, underpowered.

### 6.2 Card: "Per-class metrics with effective n"
Chips: split regime and "head: MLP". A bar chart "F1 by crop" with hover "N records but
only M independent capture events", then a table:

| Column | Meaning |
|---|---|
| Crop | class (classes with under 5 independent capture events are merged into "Other") |
| **Records** | number of survey records |
| **Effective n** | independent capture events: the real sample size |
| **Inflation** | records divided by effective n: how many times each independent observation is counted |
| Precision / Recall / F1 | standard per-class scores, 3-event |

Live: Rice (Paddy) 8,970 records, 2,102 events, F1 0.890; Coconut 2,566 / 463, 0.769; Maize
1,560 / 159, 0.694; Sugarcane 429 / 117, 0.719; **Banana 653 records but only 64 events,
F1 0.322**; Other 132 / 16, F1 0.000. Footer line: low F1 on a class with few events is a
finding about the data, not a modelling failure. (Counts are from the confusion call, which
covers the model-ready rows, so they differ slightly from the forensics table below.)

### 6.3 Card: "Confusion matrix"
Rows are the *declared* crop, columns the *satellite* prediction. A single-hue blue grid
(darker = larger share of that declared row, so rice does not swamp the picture); the number
in each cell is the record count; hover gives the share. Chips: split and head. Below:
**"Most-confused pairs"** table (Declared, Predicted, Records). Live top: Coconut declared,
Rice predicted 457; Maize to Rice 388; Rice to Maize 320; Rice to Coconut 280; Banana to
Rice 270.

### 6.4 Card: "Calibration"
A two-column table of whatever the API returns (`GET /validation/calibration`, from
`p6_audit.json`), with the split chip. Live: method "two-fold bag-grouped isotonic,
cross-fitted"; `ece_raw` 0.1247; `ece_calibrated` 0.0046; `mean_confidence_raw` 0.9418;
`mean_confidence_calibrated` 0.8170; `actual_accuracy` 0.8171; `ece_improvement` 0.1201.
Read: the raw model claims 94.2% and delivers 81.7% (3-event), a 12-point overstatement; after
calibration the average confidence equals the accuracy. You cannot spend a budget on a
number that overstates itself. ECE = expected calibration error, the average gap between
claimed confidence and actual accuracy. The calibrator is fitted only on separate capture
events from the ones it is evaluated on.

### 6.5 Card: "What the supplied survey records actually contain"
Phase 0 forensics (`GET /evidence/forensics`; no split regime because these are measurements
of the data, not of the model). Three tiles:
- **Records → capture events:** 14,643 → 3,204, "4.57x label inflation. One photograph
  supplies up to 43 parcel labels."
- **Median photo-to-parcel distance:** 1,436 m; p90 3,808 m; 62.3% of photographs were taken
  over a kilometre from the parcel they document.
- **Capture events with a mixed crop label:** 0, "which is exactly why event-grouped splitting
  is the honest one".

Then **"Effective n per crop"**: Records, Capture events, Inflation per crop (e.g. Maize 1,568
records, 162 events, 9.7x; Marigold 36 records, 3 events, 12.0x).

---

## 7. Tab 6: Analyst
File: `src/views/AnalystView.tsx`. Question: *can I ask this in words and see where the
answer came from?* Endpoints: `GET /analyst/tools` (planner info and tool list) and
`POST /analyst/query` (the question). Producer: `KAVAL/api/analyst.py`.

### 7.1 Left card: the chat
- **Title and subtitle.** The analyst plans over a typed tool layer and never computes a
  number itself; every figure in an answer came out of a tool call.
- **"Active planner:" chip.** Which engine will plan. Today: "LLM · gemini:gemini-3.8-flash"
  (from `GET /analyst/tools` → `provider`; fallback chain: gemini-3.8-flash,
  gemini-3-flash-preview, gemini-flash-lite-latest, a local Qwen2.5-7B, then the offline
  planner). If no model is reachable the chip reads "offline planner, not LLM" (keyword
  routing to the same tools). A monospace pill means LLM; an amber-bordered one means offline.
- **Empty state:** "Nothing asked yet. Try one of the starters on the right".
- **Chat area.** For each question: your message ("You") and the reply ("KAVAL analyst" with
  the same planner chip, which names the model that answered that specific reply). While
  waiting: "Planning over tools...". Replies are shown as formatted text (tables, bold,
  lists), safely, with no raw HTML.
  - **Citation chips** under each answer: source file or endpoint, "n parcels cited", `n=`,
    and `split: ...`. These prove where each figure came from. An amber chip says "no tools
    called, no figures stated" or "answer carried no citations".
  - **"N tool calls" drawer** (click to open): the exact tool names and arguments the
    planner chose, e.g. `route_verification_budget({"budget": 500})`. This is how you check
    the answer.
  - **Error state:** a red "analyst could not answer" or "(503)" message; the rest of the app
    still works.
- **Input box and "Ask" button.** Free text. Disabled while a question is running ("Thinking...").
- **Grey note under the box:** "Planned by an LLM (gemini:gemini-3.8-flash) choosing among
  KAVAL's typed tools; every figure comes from those tool results." (`planner_note`).

### 7.2 Right column
- **"Starters"**: nine buttons, the six analysis requests from the challenge brief and three
  product questions. Clicking one asks it. All nine are verified end to end by
  `scripts/p7_verify_analyst.py`.
- **"Tools the analyst can call"**: the twelve typed tools and their descriptions, straight
  from `GET /analyst/tools`: `query_parcels`, `crop_area_summary`, `compare_to_registry`,
  `confusion_report`, `leakage_ladder`, `route_verification_budget`, `auto_clear_summary`,
  `status_summary`, `ground_truth_forensics`, `get_parcel`, `calibration_report`,
  `export_layer`. They are the same endpoints this UI reads, so the agent and the screen
  cannot disagree. `query_parcels` filters on the satellite-predicted crop (`crop`) or the
  surveyor's declared crop (`declared_crop`); `crop_area_summary` takes a `village`.
- **"What the analyst will not do"**: compute a number itself, state a metric without its
  split regime, call a parcel "wrong".

Other tabs' sliders are not passed to the analyst; it always uses the API's default
thresholds. (The full tested list of questions is kept in a separate file,
`docs/team/website/demo-test-inputs.md`, by another agent.)

**What was verified, and what was not** (`docs/evidence/p7_analyst_verification.json`):
the tool layer passes (6/6 brief queries, 3/3 product queries, 12/12 tools exercised). LLM
planning was verified on **Gemini only**: the 6 brief + 3 product questions pass 9/9, and
the 2 extended questions (parcel lookup, calibration) pass 2/2 (`llm_planner`, which
records per question which model in the fallback chain answered, the tools it chose, its
time, and any figure not traceable to a tool result). It sometimes skips a secondary tool
call or states a figure no tool returned (a mis-rounding, or a number it derived itself);
the grounding check flags these, and every answer shows its tool calls. Claude's planning
was **not** verified (the Anthropic account could not be funded).

---

## 8. Quick reference: where each panel's data comes from

| Panel | API endpoint | File / evidence | Script |
|---|---|---|---|
| Header health chip | `GET /health` | files present on disk | n/a |
| Rail defaults | `meta.thresholds` of `GET /parcels?limit=1` | `THRESHOLDS` in `kaval/config.py` | n/a |
| Map polygons | `GET /geo/parcels` | `parcel_geometry.gpkg` + `audit.parquet` | `p3_feature_store.py`, `p6_audit.py` |
| Map village lines, Reserve Forests | `GET /geo/villages` | `Dataset/Administrative_Boundary/Sivagiri_Villages.geojson` | supplied data |
| Parcel panel | `GET /parcels/{id}` | `audit.parquet` | `p6_audit.py` |
| Status table, legend counts, stacked bar | `GET /audit/status-summary` | `audit.parquet`; cross-check `p6_audit.json` | `p6_audit.py` |
| Village audit chart, tiles, tables | `GET /summary/registry-delta` | `village_registry.parquet`, `p7_registry.json` | `p7_registry_comparison.py` |
| Satellite crop area chart; village dropdown names | `GET /summary/crop-area` | `audit.parquet` via `kaval/area.py` | `p6_audit.py` |
| Worklist tiles, chart, table, exports | `GET /audit/worklist`, `GET /export?budget=` | `audit.parquet` via `kaval/audit.py` | `p6_audit.py` |
| Auto-clear | `GET /audit/auto-clear` | `audit.parquet`, `VISIT_COST` | `p6_audit.py` |
| Ladder, heads, sources | `GET /validation/ladder` | `p4_results.json` | `p4_ladder_and_baselines.py` |
| Per-class, confusion | `GET /validation/confusion` | `p4_results.json` | `p4_ladder_and_baselines.py` |
| Calibration | `GET /validation/calibration` | `p6_audit.json` | `p6_audit.py` |
| Forensics | `GET /evidence/forensics` | `gt_forensics.json` | `gt_forensics.py` |
| Analyst | `GET /analyst/tools`, `POST /analyst/query` | tool layer over the endpoints above; `p7_analyst_verification.json` | `p7_verify_analyst.py` |

**Not on the site:** the "satellite-only inference demo" on the four unlabelled villages was
not built. The four villages are the Reserve Forests; they have no survey records, and we
have no embeddings for them without Earth Engine credentials. The site shows them only as a
dashed negative-control exclusion on the map. If asked, say so plainly and do not invent a
crop for those polygons (see `docs/team/12_PRODUCT_FRONTEND.md` section 8).
