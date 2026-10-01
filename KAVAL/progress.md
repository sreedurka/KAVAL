# KAVAL — Progress

Phase status and the record of what changed. `plan.md` stays authoritative for *what* the
phases are; this file records where we are and what we got wrong on the way.

**Legend:** ✅ closed · ⚠️ closed with a documented caveat · ⏸ blocked · 🔄 running

**Last updated:** 2026-09-30

> **Continuing on another machine or in a new session?** Start with
> `SESSION_HANDOFF.md` at the project root (now `/home/user/Downloads/FM_AI/`).
> `CLAUDE.md` there points new sessions to it automatically.

---








































## Status

| Phase | Status | Gate |
|---|---|---|
| 0 — Evidence & Framing | ✅ | passed |
| 1 — Data Acquisition & Provenance | ⚠️ | everything acquired, including the full monthly S1/S2 series; only MODIS LST still needs Earthdata credentials (not on the critical path) |
| 2 — Parcel Delineation | ⚠️ | **failed, with a written explanation** — see below |
| 3 — Embeddings & Feature Store | ✅ | both arms built: GSE (64-d) and Presto (128-d). The gate first failed on audit because the FTW polygons came from a hand-run CLI step. That step is now `scripts/p2a_ftw_inference.py`, and a re-run **reproduces it within tolerance** (rasters byte-identical; polygons geometrically identical, 64,708/64,708, IoU 1.0; `p2a_ftw_inference.json` → `reproduction.verdict`). All three files are provenanced, and the input lists are fixed |
| 4 — Leakage Ladder & Baselines | ✅ | passed |
| 5 — Multiple-Instance Learning | ✅ | passed; negative on accuracy, positive on the attention signal |
| 6 — Trust, Calibration, Economics | ✅ | passed |
| 7 — API & Agentic Analyst | ✅ | **LLM planning verified on Gemini (free tier): 6 brief + 3 product questions pass 9/9; 2 extended (parcel lookup, calibration) pass 2/2** (`p7_analyst_verification.json` → `llm_planner`, which records per question the answering model, tools chosen, time and any ungrounded figure). Automatic fallback: Gemini 3.8-flash → 3-flash-preview → flash-lite → local Qwen2.5-7B → offline planner. The scope stays stated: this verifies planning by Gemini, not by Claude |
| 8 — React + Leaflet Frontend | ✅ | builds clean, wired to the live API |
| 9 — Validation Report | ✅ | `docs/VALIDATION_REPORT.md` |

### Headline

**81.7% accuracy, 0.564 macro F1** — MLP, capture-event-grouped with shared
delineated fields unioned in, 5-fold. That is the best model head.

The ladder below holds **LightGBM** fixed across all four regimes, precisely so the split
is the only variable; its row-3 figure is 81.2% / 0.528. The two numbers measure
different things and should not be mixed. Under a random row split the same pipeline
reports **89.7%** — the difference is the split, not the model.

We do not claim the brief's >95% target.

---

## What each phase produced

### Phase 0 — Evidence ✅

14,643 survey records resolve to **3,204 capture events** (4.57× label
inflation). One photograph supplies up to **43** parcel labels; 93.8% of records sit in a
multi-parcel event; **0** events contain more than one crop label. The photograph
sits a median **1,436 m** from the parcel it documents (62.3% over 1 km).

### Phase 1 — Acquisition ⚠️

| Deliverable | Status |
|---|---|
| Ground-truth repair, provenance system, central config | ✅ |
| TN Agrisnet village registry, Rabi 2024 | ✅ 21 villages |
| Presto checkpoint + documented input contract | ✅ |
| CHIRPS monthly rainfall | ✅ 56 cells × 12 months |
| Sentinel-2 / Sentinel-1 | ✅ via anonymous STAC |
| Monthly Sentinel series for Presto | 🔄 S2 80/80 and S1 31/31 cached; monthly composites building (second machine, see log below) |
| Monthly air temperature | ✅ **NASA POWER (MERRA-2), keyless** — substituted for ERA5-Land, 12/12 months |
| MODIS LST | ⏸ needs Earthdata credentials |

**The GEE blocker was not real.** Phase 1 was recorded as blocked on Earth Engine
credentials. Sentinel-1 and Sentinel-2 are served through public STAC endpoints needing no
account at all. Only the Google Satellite Embedding is genuinely GEE-only, and it was
already held. Phase 2's primary path was never blocked.

**Defects repaired:** 647 records store two coordinates in one cell;
13 geocode outside the study area; 32 duplicate parcel keys. And a new one: the
**same row stores the same date in two different formats** — `timestamp` is MM-DD-YYYY
while `image_timestamp` is DD-MM-YYYY. Parsed naively, an eight-day survey appears to span
June to December. It actually ran **2024-11-06 to 2024-11-13**.

### Phase 2 — Geometry ⚠️ failed gate, explained

Full write-up: **[`docs/PHASE2_GATE_EXPLANATION.md`](docs/PHASE2_GATE_EXPLANATION.md)**

FTW on real Sentinel-2 produced **64,708 field polygons (13,062 ha across the whole taluk)**.

Checked against the independently acquired registry, the first comparison we published was
wrong. We had said FTW was "within 8%" of the registry. That compared the whole-taluk figure
to a registry covering only the 21 revenue villages. Like for like, FTW delineates
**7,151 ha inside those villages against the registry's 12,097 ha, 41% short**, and 26% short of the
annual-crop area alone. A genuine under-recovery; cause not isolable with this data
(`scripts/p2c_ftw_registry_area.py`).

Both gate criteria fail: match 73.3% (needs 80%), one-point-per-field
20.4% (needs 60%). Phase 3 opened anyway because the fallback is in place, the
leakage consequence is handled structurally, and the area consequence is fixed.

> **The finding: satellite delineation recovers *physical fields*, not *legal parcels*.**
> 10,707 matched parcels map onto 5,528 fields — **1.94 legal parcels per physical field**,
> up to 19. Corroborated by crop type: Sugarcane 56.5% on 432 points (annual
> arable) against **Coconut 23.6%** (perennial tree crop).

Strict containment scored only 36.4%, but unmatched points sit a median 15.2 m from
the nearest field — GPS error, not delineation failure. Points are snapped within
20 m and the whole trade-off curve is published rather than a tuned number.

### Phase 2b — Reserve-forest negative control ✅

**734.7 ha (4.0%)** of 18,385 ha of protected land reads as field-like;
Naranapuram R.F reads 37%. **Deliberately not reported as encroachment** — there is no
ground truth inside these polygons, and it is equally consistent with delineation false
positives or another boundary error. It produces a ranked list of places worth a visit,
which is the thesis in miniature.

### Phase 3 — Feature store ⚠️

14,611 parcels · 76 features · 3,204 capture-event bags · 301 parcels without
features (flagged, not dropped). Evaluable classes: Banana, Coconut, Maize, Rice (Paddy), Sugarcane.
Seven crops with 1–4 capture events collapsed to `Other`.

With `field_id` carried, **2,921 bags collapse to 2,269 components** (`docs/evidence/p4_results.json` → `group_structure`) once parcels sharing a
physical field are unioned in — a 22% loss of independent groups, one chain spanning 164
parcels.

Presto arm ✅: 128-d embeddings for all 14,611 parcels from 12 monthly S1/S2 composites
(June 2024 – May 2025), CHIRPS rainfall, NASA POWER temperature and Copernicus DEM
terrain. The result is under Phase 4.

### Phase 4 — The ladder ✅

| Regime | Accuracy | Macro F1 |
|---|---:|---:|
| 1-random | 89.7% ± 0.004 | 0.772 |
| 2-parcel | 89.5% ± 0.005 | 0.769 |
| **3-event + field** | **81.2%** ± 0.022 | **0.528** |
| 4-village | 70.8% ± 0.095 | 0.326 |

Grouping by parcel — the obvious control — moves accuracy -0.2 points. It is not
protection. Unioning `field_id` costs a further 0.8 points (`group_structure`) and nearly quadruples fold
variance.

**Heads:** MLP best on macro F1.

**Sources** (regime 3-event, MLP, identical rows and folds, each paired against GSE fold
by fold):

| Source | Accuracy | Macro F1 | Δ macro F1 vs GSE (SD) | Verdict |
|---|---:|---:|---:|---|
| GSE only (64-d) | 81.5% | 0.563 | — | reference |
| Seasonal S1/S2 only | 73.7% | 0.399 | −0.165 (0.033), 0/5 folds | behind |
| GSE + seasonal | 81.7% | 0.564 | +0.001 (0.008) | underpowered |
| **Presto (128-d)** | **74.2%** | **0.452** | **−0.111 (0.011), 0/5 folds** | **behind, clearly** |
| GSE + Presto | 81.3% | 0.559 | −0.004 (0.006) | underpowered |

**GSE vs Presto, the comparison the brief asks for:** GSE wins clearly as a standalone
source, and combining the two adds nothing measurable. That is not a verdict on Presto as
a model. Four things limit it: the L1C→L2A domain shift, taluk-scale meteorology, a
parcel-mean series where Presto was pretrained per pixel, and a frozen encoder with no
fine-tuning. And Sentinel-2 saw only **38.1% of parcels in November 2024, the survey
month**, because of monsoon cloud, which is a structural handicap for any optical
time-series model here. Source: `docs/evidence/p4_results.json`, `p3b_presto.json`.

### Phase 5 — MIL ✅

MIL is a **worse classifier**: -3.00 pp, -0.0565 macro F1 (regime 3-event, same folds as Phase 4). Reported, not buried.

**Its attention signal works: +16.18 pp.** Parcels it attends to least agree with the
surveyor 69.4% of the time against 85.6% for the rest — measured
against the *independent* baseline. Measured against MIL's own prediction it reads
+22.81 pp, but attention produced that prediction, so the model would be partly
agreeing with itself. Gating uses the honest figure.

### Phase 6 — Audit ✅

**Calibration: ECE 0.1247 → 0.0046.** Raw confidence averages 0.942 against
0.817 actual accuracy (regime 3-event); cross-fitted isotonic lands it on 0.817.

**Agreement status:** 4,825 CONFIRMED · 784 DISPUTED ·
8,429 UNCERTAIN · 272 UNVERIFIABLE.

**Base disagreement rate 18.3%** — only one parcel in five needs looking at.
Targeting efficiency 5.45×, labelled as pinned by construction. The metric that
*is* informative about ranking: routed parcels carry mean calibrated confidence
**0.734** against **0.652** across all disagreements.

**Auto-clear 4,825 parcels (33.7%)** — 193 surveyor-days of a
572-day baseline. Residual risk 7.6%, described as a **rough proxy,
explicitly not a bound**.

### Phase 7 — API and analyst ✅

17 routes, all verified 200, `meta.split_regime` on every metric response. Analyst tool
layer: **6/6 brief queries, 3/3 product queries, 2/2 extended queries, 12/12 tools
exercised** (`export_layer`, the tool plan.md §3 names, was added on 2026-10-01; `get_parcel`
and `calibration_report`, plus a `declared_crop` filter on `query_parcels` and a `village`
parameter on `crop_area_summary`, were added after live testing showed a named-village crop
area query seeing a truncated table, a parcel lookup answering "not found", and a
calibration question improvised from unrelated tools).

**LLM planning: verified on Gemini's free tier, 9/9 core questions and 2/2 extended**
(`p7_analyst_verification.json` → `llm_planner`, which records per question which model in
the fallback chain answered, the tools it chose, its time, and any figure not traceable to a
tool result; those details change every run, so docs quote only the stable result). The
stable weakness: it sometimes skips a secondary tool call or states a figure no tool
returned (a mis-rounding, or a number it derived itself); the grounding check flags these. The analyst falls back
automatically: Gemini models → local Qwen2.5-7B → offline keyword planner, and every
answer names the model that produced it.

- **Verified:** the tool layer; the offline planner (9/9); planning by Gemini (9/9 core, 2/2 extended).
- **Not verified:** that *Claude* selects and composes the tools correctly. The Anthropic
  account could not be funded; Claude is first in the chain whenever a key exists.

*Every key (the three Anthropic keys earlier, the Gemini key now) was used only as a process
environment variable and never written to any file, log or provenance entry. They appear
in the working transcript and should be rotated.*

### Phase 8 — Frontend ✅

React 18 + TS + Vite + Leaflet. `npm run build` clean under `strict`. Map coloured by
**agreement status**, not crop class. `src/lib/status.ts` deleted so the status rule
exists in one place. CONFIRMED is **blue, not green** — the reflex green/red palette fails
CVD validation at ΔE 4.1 under deuteranopia.

### Phase 9 — Validation report and demo ✅

`docs/VALIDATION_REPORT.md`, generated from evidence artefacts only, with sections marked
absent rather than omitted, and an explicit threats-to-validity section.

`docs/DEMO_WALKTHROUGH.md` — the twelve-minute walkthrough the gate also asks for, written
in the order that makes the argument rather than the order the pipeline runs. Its figures
are generated from the evidence artefacts, so it cannot drift from the system it
describes. It deliberately scripts the moments where we *volunteer* a weakness before a
reviewer finds it: that the targeting ratio is pinned by construction, that accuracy
within the auto-cleared set is circular, that field-like land inside reserve forest is not
a finding of encroachment, and (at the time) that the analyst's planning was unverified; it has since been verified on Gemini.

---

## Session log — second machine (2026-09-30, evening)

Work resumed on a new machine from `SESSION_HANDOFF.md` §9.

| # | Item (handoff §9) | Status |
|---|---|---|
| — | Environment | ✅ copied `.venv` re-linked to a uv-installed CPython 3.12; shebangs repointed; imports verified. The 15 GB scene cache came across. |
| 1b | Presto embeddings | ✅ `presto_embeddings.parquet`: 128-d, all finite. Inputs: S2 observed 92.2% overall, but **November 2024, the survey month, only 38.1%** (north-east monsoon cloud). S1 99.99%. Two contract defects surfaced on the first real run and are fixed: p3b read `lat`/`lon` from the monthly series, which never carried them (now taken from the feature store), and it never passed the DEM elevation and slope that acquisition produced (now fed to Presto's static slot, recorded as a Copernicus-for-SRTM substitution). |
| 1 | STAC acquisition → Presto | ✅ S1 went 29 → 31/31; monthly series written. The first resume **failed at the DEM step**: the public Copernicus DEM bucket needs anonymous S3, which the old machine had configured outside the repo. `p1_acquire_stac.py` now sets `AWS_NO_SIGN_REQUEST` itself (correction #21). Relaunched; Presto is chained behind it. |
| 2 | Presto arm in p4 §C | ✅ ran. Presto alone −0.111 macro F1 against GSE (0/5 folds); GSE + Presto underpowered. The ladder and 81.7% headline reproduce exactly. p6 → p2d → p7 → p9 re-run, and the audit figures are unchanged (status counts, ECE, auto-clear). The frontend's validation view now shows the paired verdicts. Code: Presto (128-d) and GSE + Presto added. **Every source is scored on the same rows and folds**, and each is compared with GSE **fold by fold**, with an `underpowered` flag computed rather than judged. |
| 5 | `/export` can't reproduce the worklist | ✅ `/export?budget=N` (plus the threshold params) returns the routed queue with `rank` and `priority`, row-for-row identical to `/audit/worklist` (verified at N=300). The ranking now has one definition, `audit.routing_priority`. The worklist route had its own copy with the median taken over a different set: latent, identical on today's data (verified at N = 100/500/2000). The UI's Export buttons now download the queue on screen, and the caveat explaining that they didn't has been removed. |
| 5 | Analyst `Citation` has no parcel IDs | ✅ `Citation.parcel_ids`: every parcel the tool returned (capped at 50). The frontend now reads the same field name. |
| 6 | Palette CVD figures unverified | ✅ `scripts/p8_validate_palette.py` re-runs the dataviz validator on the colours in `styles.css` → `docs/evidence/p8_palette.{json,md}`. Figures reproduce exactly (light 9.1/22.9, dark 7.2/16.9, retired 4.1). Doc 12 corrected: both modes pass **with a WARN** (light contrast, dark CVD), and the figures exclude outline-only `UNSEEN`, which fails when included. |
| 3 | Propagate numbers to documents | 🔄 area/registry corrections ✅ (proposal-writer, 11 files); Presto results 🔄 (proposal-writer) |
| 4 | Reproducibility guard, part 1 (area + boundary claim) | ✅ ran. **Shared-field apportionment verified**: every one of the 2,545 shared fields sums back to its field area (ratio 0.99999–1.00000), and 2,250.2 / 4,800.8 ha and 3.883× reproduce. But (a) 4,801 ha and 3.88× existed in no evidence file, and (b) apportionment is **not** the field-level aggregation plan.md §6 requires, since 386 shared fields are split across predicted crops (93.5 ha). **Boundary claim: numbers verified, conclusion overstated.** The registry is compiled from the recorded codes, so it agreeing with them is circular (correction #22). ✅ Fixed by `api-engineer`: `kaval/area.py` is now the one place crop area is summed. Each shared field gets one crop, totals are unchanged by an asserted invariant, and `conflicted_area_ha` shows the 93.5 ha (386 fields) where members disagree on the predicted crop. The registry conclusion no longer claims independence, and `p2d_shared_field_area.json` now backs the 4,801 ha / 3.88× figures. The registry pair figure moved 0.0163 → 0.0183 under field-level area. |
| — | Routing note overstated | The generated note said targeting efficiency *equals* 1/base rate. It is a **cap**: at N=500 it is 5.45× against the 5.47× cap, because the ranking lets 2 agreeing parcels in. Wording fixed in `audit.py`, p6 and p9. The numbers were already right. |
| — | Phase 8 gate on this machine | ✅ API on 8077: 16/16 GET routes 200, `split_regime` on every metric route. Vite on 5173 proxies to it. The worklist export downloads through the proxy. |
| — | Analyst panel returned 503 with no key | ✅ Requested by the user on 2026-10-01. `agent-analyst-builder` added an **offline planner**, used when no `ANTHROPIC_API_KEY` is set. It routes by keyword over 11 intents to the same typed tools and composes the answer only from their results, with citations, parcel IDs and split regimes. Verified 9/9 by function and 9/9 over HTTP, including through the UI's proxy; a nonsense question gets 0 tool calls (`p7_analyst_verification.json` → `offline_planner`). Every answer carries `planner: "offline"`, and the UI shows "offline planner — not LLM". **The panel works; the Phase 7b LLM-planning gate stays open.** The LLM path is unchanged and takes over when a key is set. |
| — | Final audit fixes (2026-10-01) | ✅ FTW step scripted and reproduced (above). New evidence: `p2e_ftw_match_detail.json`. The per-crop match table reproduces, but its top rows rest on 16 and 30 points, and the snap distance is **15.2 m / 58% within 20 m**, not the 14 m / 61% the docs said. `p4_results.json` `group_structure`: 2,921 → 2,269 components, largest 164, event-only fold SD ±0.006, all reproduced. `p6_audit.json` `trust_vs_agreement_r`: **0.124 / 0.077**, not the 0.115 / 0.055 quoted. p4 → p9 re-run: every accuracy and F1 identical, and `oof`/`audit` parquets byte-identical. Documents corrected. |
| — | End-to-end testing (2026-10-01) | ✅ `tests/test_api.py`: **41/41** behavioural API tests against the evidence. `frontend/e2e/kaval.spec.ts` (Playwright): **22/22**, covering every tab at desktop, phone and dark, plus the map, worklist, ladder and analyst flows; screenshots in `docs/e2e/`. The screenshots caught what green tests had not: **the worklist's headline tiles were blank** (the UI read field names the API had renamed when the "lift" was retracted) and still labelled "Lift multiple — the number that justifies the system", which is correction #2's retracted claim. Also fixed: auto-clear called the residual a "bound" (correction #1 says proxy); charts scaled their text to about 20 px and clipped labels; there was no phone layout (hard 1,024 px minimum). A test now fails on any blank stat tile. |
| — | Analyst on a real LLM, keyless (2026-10-01) | ✅ `api/llm.py` provider layer, in order: Anthropic, then a free Gemini, Groq or OpenRouter key, then any OpenAI-compatible URL, then a **local open-weight model**, then the offline planner. The local model is llama.cpp + Qwen2.5-7B-Instruct via `scripts/serve_local_llm.sh`, with no key or cost. It plans correctly on a real question but is slow on this CPU (reads about 35 tok/s, writes about 3; one to three minutes per question). 🔄 Per-question planning verification running (`p7_verify_analyst.py --llm`). |
| — | Gemini as the analyst's LLM (2026-10-01) | ✅ User supplied a free-tier Gemini key. It is passed **only as a process environment variable** and appears in no file, log, evidence or memory; it should be rotated, since it was pasted into the chat. `gemini-2.5-flash` is closed to new accounts, so the chain is 3.8-flash → 3-flash-preview → flash-lite-latest, then local, then offline, falling through on 404/429/5xx. That fallback fired for real during testing (3.8-flash returned 503 "high demand"). **Scored on the 9 brief and product questions (that run): 9/9 pass; all expected tools in 7/9** (the other two skipped a secondary `query_parcels` call); **2 answers mis-rounded a figure in the second decimal** (78.426 → "78.42", 142.834 → "142.84"), caught by the grounding check; 1 said "wrongly cleared", now covered by a prompt rule. Four precision rules added to the system prompt (underpowered means no difference, corrections are estimates, percentage points, the residual is a proxy). The UI renders the LLM's Markdown safely and names the model on every answer. Playwright 22/22, API 41/41. |
| — | `seasonal_s1_s2_stac.csv` decision (2026-10-01) | ✅ Kept and documented as a **keyless, seasonal-only alternative, not wired in**. Checked before documenting: it has no GSE bands, so `--features` would have dropped all 64 embedding features, and it agrees only moderately with the GEE seasonal columns (different windows and geometry). The docstring that said p3 "accepts it" is corrected. |
| — | Recorded walkthrough, Phase 9 (2026-10-01) | ✅ `docs/demo/kaval_walkthrough.webm`, 1 min 50 s, recorded through the real UI and API by `frontend/e2e-demo/walkthrough.spec.ts`, in `DEMO_WALKTHROUGH.md`'s order. A caption bar carries each beat, and **every caption figure is fetched from the API at record time**, none typed. Reviewing the frames caught Gemini answering in raw LaTeX (`$p(\text{label wrong})$`); fixed with a prompt rule and a renderer fallback, then re-recorded. |
| — | Phase 2 evidence and provenance fixes (2026-10-01) | ✅ `p2_ftw_delineation.json` now records the scenes FTW **actually** used (2024-05-07 and 2024-12-08, from `p2a`) instead of echoing the config windows it never used. The `parcels.gpkg` provenance names its prerequisite rather than itself. `p2c` no longer depends on the working directory. p2 → p3 re-run twice: **feature store byte-identical both times**, so everything downstream is unaffected by construction. |
| — | Final pre-submission audit (2026-10-01) | ✅ `reproducibility-guard`: **Phase 3, 7 and 9 gates PASS; correction logs consistent 1–23; all 44 provenance SHAs match.** Everything it found is fixed. **(1)** Gemini *refused* the brief's export query yet was scored a pass, because no tool offered an export. Built **`export_layer`**, the tool plan.md §3 names; its row counts are checked against what `/export` serves. Gemini now calls it, the verifier fails any refusal of a capability the tools provide, and the tool layer was 10/10 at that point (12/12 since `get_parcel` and `calibration_report` were added). **(2)** The evidence labelled every answer with the chain head (3.8-flash); `answered_by` now records who actually answered (all 9 from flash-lite in that run: the weakest model in the chain still passes 9/9). **(3)** The field-union cost was "half a point" in four places; the evidence says **0.8** (82.0% → 81.2%). **(4)** `parcels.gpkg` provenance recorded the config windows; it now records the real scenes (feature store byte-identical after the re-run). **(5)** Our own evidence text said satellite and surveyor are "wrong in the same way", which the LLM then quoted; now "err" (audit parquet byte-identical). **(6)** Missing split regimes added in 6 places; Phase 7's progress section rewritten to the verified state. |
| — | Team presentation and website docs (2026-10-01) | ✅ `docs/team/presentation/presentation-script.md` (15-min talk, timed to 15:00, M1–M4) · `presentation/app-demo-script.md` (page-by-page spoken demo) · `website/page-guide.md` (every element, top to bottom, with its data source) · `website/glossary.md` (144 terms) · `website/demo-test-inputs.md` (46 analyst questions **verified live**, with expected figures and offline backups; click paths for every page; pre-demo checklist). Writing them surfaced real defects, now fixed: the **analyst failed on crop area for most named villages** (`crop_area_summary` gained `village`), had no parcel lookup or calibration tool (added `get_parcel` and `calibration_report`, 12 tools), and could not filter by declared crop (`declared_crop`). The map exports ignored the thresholds; the village crop-area card summed in the browser and ignored its filter; "P(wrong)" labels broke the vocabulary; the map e2e test never verified the parcel panel (now a real click). Quota refusals are now scored "not run", not as planning failures. Re-verified: LLM 9/9 core + 2/2 extended, offline 9/9, API 41/41, UI 23/23. |
| — | Portable Windows package (2026-10-01) | ✅ `scripts/make_package.py` → `KAVAL_Package.zip` (178 MB; code, all served data, docs, demo video, supplied dataset, CropSight export). It excludes `.venv`, the scene cache and `node_modules`, and **refuses to build if any file holds a key-shaped secret**. `setup.cmd` (uv + Python 3.12 + pinned `requirements-app.txt`, Node LTS via winget, `npm ci`; `full` adds the pipeline set) and `run.cmd` (key prompt, kept in memory only; API pinned to Gemini then offline; `127.0.0.1` not `localhost`; `PYTHONUTF8=1` because Windows defaults to cp1252); guide in `WINDOWS_SETUP.md`. Both requirement sets resolve for Windows x64 with binary wheels only. **Verified from the unzipped package in a clean directory: fresh environment, 41/41 API tests, `npm ci` + build, 23/23 UI tests.** The `.cmd` files themselves are untested: no Windows machine was available. |
| — | Retracted claim still in the validation report | Found: `p9_validation_report.py` still hard-coded the GSE-vs-seasonal "negative result" retracted as correction #4, so `VALIDATION_REPORT.md` repeated it. Replaced with the computed paired comparison (correction #20). Regenerates on the p9 re-run. |
| — | Analyst tools 10 → 12; docs quote only the stable LLM result (2026-10-01) | ✅ Added `get_parcel` and `calibration_report`, a `declared_crop` filter on `query_parcels` and a `village` parameter on `crop_area_summary`, after live testing showed a named-village crop-area query reading a truncated table, a parcel lookup answering "not found", and a calibration question improvised from unrelated tools. Tool layer 12/12 exercised; Gemini planning 9/9 core and 2/2 extended (`p7_analyst_verification.json` → `llm_planner`). Every reviewer-facing doc now quotes only that stable result and points to `llm_planner` for per-run detail (answering model, tools chosen, time, ungrounded figures), which changes every run. |

---

## Corrections and retractions

Kept because a project whose thesis is validation honesty should show its own.

| # | What | Outcome |
|---|---|---|
| 1 | **"Accuracy within auto-cleared set: 100%"** | Circular — CONFIRMED is *defined* as the model agreeing. Replaced with a residual-risk proxy and an explicit statement that the quantity is unidentified. |
| 2 | **Routing "lift" of 5.58×** | Tautological — exactly 1/base-rate, constant at every budget. Replaced with `targeting_efficiency`, labelled as pinned, plus a ranking metric that is not. |
| 3 | **`p_label_wrong` asserting ~98% certainty** | From an 82%-accurate model, on uncalibrated probabilities. Now discounted by measured accuracy; the function refuses to run without it. |
| 4 | **"GSE alone beats GSE + seasonal"** | **Retracted.** Sign flipped twice across three runs (0.607/0.598 → 0.587/0.597 → 0.563/0.564). All gaps under 1 SD. The comparison is underpowered; there is no effect. |
| 5 | **"+22.8 pp attention gap"** | Partly self-referential: measured against MIL's own prediction (`p5_mil.json` `self_referential_gap_pp` 22.81). Now +16.2 pp against an independent baseline. (This row once said +26.4 pp, a figure no evidence file holds.) |
| 6 | **Regime 4 grouped by recorded village code** | Leaked 15 of 21 villages. Fixed to spatial. The change is 0.18 SD — worth fixing on principle, but not a result. |
| 7 | **"4 unlabelled villages for an inference demo"** | They are Reserve Forest. Reframed as a negative control. |
| 8 | **Village-code discrepancy blamed on surveyors** | **Reversed.** The registry agrees with the recorded code (0.0163) far better than with polygon membership (0.1053). The **supplied boundary layer** is the likely error. **The reversal itself overreached: see #22.** |
| 9 | **Shared-field area double-counting** | Each sharing parcel inherited the whole field's area — 3.88× inflation, 2,250 ha reported as 4,801 ha, in a figure we publish. Now apportioned. |
| 10 | **`METRIC_CRS` = UTM 44N** | AOI is 77.41°E — zone **43N**. Every area inflated 0.218%. Fixed and regenerated. |
| 11 | **Two contradictory Leakage Ladders published** | Phase 0's standalone script retired; README repointed at the canonical one. |
| 12 | **Analyst would have crashed on 5 of 6 brief queries** | FastAPI resolves `Query(...)` defaults only through HTTP; called directly the function got the `Query` object. Invisible to type-checking. |
| 13 | **`GEOMETRY_TRUST` had no `ftw_shared` entry** | 7,724 parcels (54%) would have silently fallen to the 0.4 default. |
| 14 | **Phase 6 not carrying Phase 2 geometry fields** | `field_id`, `snap_m` etc. could never have reached the UI. |
| 15 | **`/geo/parcels` used `head(limit)`** | File order is geographically clustered — an unfiltered map was silently biased. Now sampled. |
| 16 | **Bare `assert` for the leakage check** | Stripped by `python -O`. Now raises. |
| 17 | **Duplicate STAC writers** | Two processes writing one parquet. Killed mine; the delegated run continues. When work is delegated, the delegator must not also do it. |
| 18 | **"FTW within 8% of the registry"** | Compared mismatched footprints. Like for like FTW is 41% short. Caught while cross-checking numbers for the team docs. |
| 19 | **STAC acquisition silently dead for Sentinel-1** | Planetary Computer SAS tokens expire. Items were signed at search time and fetched ~65 min later, after S2 finished, so all 31 S1 scenes returned HTTP 403 across 8 retry rounds. It looked like a slow job. Fixed by re-signing each item immediately before its read; the S2 cache made the resume instant. |
| 20 | **Correction #4 retracted in the docs, not in the generator** | `p9_validation_report.py` hard-coded "adding seasonal features makes the model slightly worse" as a finding, so every regeneration of `VALIDATION_REPORT.md` reinstated the retraction. The source verdict is now computed from paired per-fold deltas. A retraction has to reach the script, not just the prose. |
| 21 | **"All sources anonymous" held only on the first machine** | The Copernicus DEM read needs `AWS_NO_SIGN_REQUEST=YES`. The first machine evidently had it set outside the repo, so the script failed on the second. Now set in the script. |
| 22 | **"The boundary layer is the likely error" rested on a circular test** | The registry is the survey's own published aggregate, compiled by the *recorded* village code, so it must agree with those codes. Its by-code vs by-polygon gap on the 911/912 pair (0.0163 vs 0.1053 as published; 0.0183 vs 0.1053 now that area is aggregated at field level) therefore cannot show which attribution is right, and the generated conclusion called the registry "sourced independently". Across all 21 villages the gap is small (0.0569 vs 0.0655, `p7_registry.json`); only the 911/912 pair shows it. The only independent evidence is geometric (every record coded 912 falls inside the 911 polygon). That *suggests* a boundary or labelling error but does not prove it, so it is now a question for FarmwiseAI, not a finding. |
| 23 | **Phase 4 results predated a `splits.py` edit by 108 seconds** | The published numbers were not reproducible from the committed code: fold assignments agreed only 23% with what the code then produced. Re-run. Logged in `docs/team/13_CORRECTIONS.md` and added here so both logs number the same things. |

---

## Open

| Item | Blocker |
|---|---|
| Claude's planning, specifically | No funded Anthropic key. Planning is verified on Gemini; Claude is first in the chain whenever a key exists |
| Cadastral IoU benchmark | Needs FMB geometry from FarmwiseAI — `docs/DATA_REQUEST.md` |
| AI-6 vision-language photo check | Needs the survey photographs |
| Reserve-forest classifier confidence check | Needs embeddings for geometry outside the surveyed parcels (GEE) |
| MODIS LST | Needs Earthdata credentials; not on the critical path |
| Team member names | §11 of the proposal |
