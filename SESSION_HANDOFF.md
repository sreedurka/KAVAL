# SESSION HANDOFF — KAVAL

> **To the Claude session reading this:** you are continuing an existing working session,
> not starting a new project. Read this whole file before doing anything. It replaces the
> conversation history you do not have. Act on it the way you would act on a compacted
> summary of your own earlier turns: the decisions here are already made, the user has
> already approved them, and you should pick up at **§9 Next actions** without
> re-proposing, re-planning or re-asking what is settled.
>
> **Snapshot taken:** 2026-10-01, on the second machine (`/home/user/Downloads/FM_AI`).
> The first snapshot was 2026-09-30 on the original machine (`/home/user/FM_AI`). §14 records
> what the second session did. Nothing was left running.

---

## 0. Read these, in this order

| File | Why |
|---|---|
| **this file** | the session state |
| `KAVAL/plan.md` | **authoritative** plan — phases, gates, locked decisions, agent rules. If anything disagrees with it, `plan.md` wins. |
| `KAVAL/progress.md` | live phase status and the full 19-row corrections log |
| `KAVAL/docs/team/00_START_HERE.md` | the whole project in ten minutes |
| `KAVAL/docs/team/13_CORRECTIONS.md` | every mistake we made and caught. **Read before changing any number.** |
| `~/.claude/projects/-home-user-Downloads-FM-AI/memory/` | machine setup notes (the first machine's memory files did not come across; §2 carries the user's preferences) |

Everything else is detail you can look up when you need it.

---

## 1. What this project is

**KAVAL** (காவல், Tamil for "vigil") is a submission to the **FarmwiseAI Campus Product
Challenge, Task 3 — Satellite-Embedding-Based Crop Classification.** It is a student
hackathon with a team of four. The brief lives at
`documents/FarmwiseAI_Product_Challenge_Brief.md`, the supplied data at `Dataset/`.

The brief asks for a parcel-level crop classifier at **>95% accuracy**. We measured the
supplied data and found that target is only reachable by leaking at validation time. So
KAVAL was reframed around one line:

> **The classifier is the instrument. The product is the audit.**

The system tells an agriculture department **which Digital Crop Survey records to trust,
which to re-verify, and which parcels never need a visit again.**

### The findings everything rests on

- **14,643 ground-truth records are really 3,204 independent observations.** One survey
  photograph labels up to 43 parcels, and every one of the 3,204 capture events has a
  single crop label. The label belongs to the event and is copied to each parcel.
- **The photograph is a median 1,436 m from the parcel it documents.** 62% are more than
  1 km away.
- **The Leakage Ladder.** Same model (LightGBM, held fixed), same features. Only the
  split changes:

  | Split | Accuracy | Macro F1 |
  |---|---:|---:|
  | Random row | 89.7% | 0.772 |
  | Parcel | 89.5% | 0.769 |
  | **Capture event + shared field** | **81.2%** | **0.528** |
  | Village | 70.8% ±9.5 | 0.326 |

  Grouping by parcel is the obvious fix, and it changes almost nothing (−0.2 points),
  because each parcel is already exactly one row. Only grouping by capture event shows
  the leak.
- **Headline: 81.7% accuracy, 0.564 macro F1.** This is the best model (MLP) under the
  headline split. Do not mix it up with the ladder's 81.2%, which is LightGBM held fixed.
  They measure different things.
- **Only 18.3% of parcels have a satellite–survey disagreement at all.** That is the
  main thing the product delivers.

---

## 2. How this user works — follow these

- **Autonomy on execution, consent on architecture.** The user wants phases done with no
  prompting from them. The only questions worth asking are real architecture decisions.
  They said "decide the best recommended option", so make sensible calls yourself and
  record the reasoning.
- **Update `KAVAL/progress.md` as you go.** They asked for it more than once. It is the
  tracking document they read.
- **They want an approach other teams won't copy.** They pushed back on a generic first
  draft. Keep the audit framing. Don't drift back to "classifier plus a map".
- **AI has to be central.** They said it's for an AI company and "not just a full stack
  application plotting a map". The six AI components (§4) are the answer. Don't let the
  UI become the story.
- **The supplied data is a "small reference sample, not actual data"**, per the user. We
  acquire real data ourselves. Keep supplied and acquired data clearly separated.
- **Honesty over polish.** The project's credibility comes from reporting negative
  results and fixing its own overclaims. **Never claim >95%. Never quote a metric without
  its split regime. Never call a parcel "wrong".** The survey and the satellite
  *disagree*, and a field visit decides which is right.
- **Team member names are still missing** ("will be provided later"). Leave the
  placeholders M1–M4 in proposal §11.
- **The API key / LLM path is closed.** See §7. The user said topping up credits "is not
  possible". Don't ask for keys again. Don't try to route around it.

---

## 3. Directory map

```
/home/user/FM_AI/                     ← working directory (Claude Code project root)
├── SESSION_HANDOFF.md                ← this file
├── documents/                        ← FarmwiseAI brief + requirements (SUPPLIED, read-only)
├── Dataset/                          ← SUPPLIED data (3.2 MB) — ground truth + boundaries
├── CropSight/                        ← PRIOR WORK, superseded. Kept only because its GEE
│                                        feature export (GSE + seasonal) feeds Phase 3.
├── .venv/                            ← Python 3.12, uv-managed (NOT pip)
├── .cache/kaval_stac/                ← 15 GB Sentinel scene cache (machine-local)
├── .claude/agents/                   ← 14 phase-owning agent definitions
├── .claude/skills/                   ← 9 skills encoding project rules
└── KAVAL/
    ├── plan.md                       ← AUTHORITATIVE
    ├── progress.md                   ← live status + corrections log
    ├── proposal_updated.md           ← the FarmwiseAI submission (~780 lines)
    ├── README.md
    ├── kaval/                        ← library: config, splits, audit, mil, provenance, presto_io
    ├── scripts/                      ← one script per phase; every number comes from here
    ├── api/                          ← FastAPI main.py + analyst.py
    ├── frontend/                     ← React 18 + TS + Vite + Leaflet
    ├── models/presto/                ← Presto checkpoint
    ├── data/{raw,interim,derived}/   ← 148 MB; PROVENANCE.md lists every file
    └── docs/
        ├── evidence/                 ← GENERATED json+md. Never hand-edit.
        ├── team/                     ← 15 review-prep docs, 00–14 (see §6)
        ├── VALIDATION_REPORT.md      ← generated by p9
        ├── DEMO_WALKTHROUGH.md
        ├── PHASE2_GATE_EXPLANATION.md
        ├── DATA_REQUEST.md
        └── PRESTO_NOTES.md
```

**Not a git repository.** There is no history to fall back on, so edit carefully.

---

## 4. Architecture in one screen

```
SUPPLIED → P1 acquisition → P2 geometry (AI-1 FTW) → P3 features (AI-2 GSE/Presto)
        → P4 leakage ladder → P5 attention-MIL (AI-3) → P6 audit (AI-4 calibration,
          confident learning, trust score, agreement status, routing)
        → P7 FastAPI + agentic analyst (AI-5) → P8 React/Leaflet → P9 report
```

**Six AI components.** Each one has something downstream that depends on it:

| | Component | State |
|---|---|---|
| AI-1 | Fields of The World segmentation for parcel geometry | ran on real S2; **gate failed, explained** |
| AI-2 | Google Satellite Embedding + Presto | **both run**; Presto alone clearly behind GSE, and the combination adds nothing measurable (§14) |
| AI-3 | Attention-MIL over capture-event bags | **worse classifier; attention signal +16.2 pp works** |
| AI-4 | Calibration + confident learning + trust | done; ECE 0.1247 → 0.0046 |
| AI-5 | LLM agent over 9 typed tools | tool layer verified 9/9; **offline planner answers without a key (labelled)**; LLM planning unverifiable |
| AI-6 | Vision-language photo check | **conditional**: we have photo paths, not the images |

**Agreement status** is how the whole product talks. The map is coloured by it, not by
crop: `CONFIRMED` 4,825 · `DISPUTED` 784 · `UNCERTAIN` 8,429 · `UNVERIFIABLE` 272 ·
`UNSEEN` 0.

---

## 5. Phase status at snapshot

| Phase | Status | Note |
|---|---|---|
| 0 Evidence | ✅ | |
| 1 Acquisition | ⚠️ | everything acquired, including the monthly S1/S2 series; only MODIS LST is missing (needs credentials, not critical) |
| 2 Geometry | ⚠️ | **gate FAILED, with a written explanation.** See `docs/PHASE2_GATE_EXPLANATION.md` |
| 3 Features | ✅ | GSE and Presto arms both built |
| 4 Ladder | ✅ | |
| 5 MIL | ✅ | negative result as a classifier, reported |
| 6 Audit | ✅ | |
| 7 API + analyst | ⚠️ | tool layer ✅; the offline planner makes the panel work; LLM planning permanently unverifiable here |
| 8 Frontend | ✅ | builds clean |
| 9 Report + demo | ✅ | |

---

## 6. The team docs (`KAVAL/docs/team/`)

These were built for the user's team to use in a live review. The roles are M1 Data &
Geospatial · M2 ML & Validation · M3 Audit & Backend · M4 Product & Frontend.

`00` start here · `01` architecture · `02` domain primer · `03`–`04` M1 · `05` `06` `07`
`11` M2 · `08` `09` `10` M3 · `12` M4 · `13` corrections · `14` review Q&A.

Every number in them is **generated from `docs/evidence/*.json`**. If you change a
pipeline result, the team docs, proposal, progress, README, walkthrough and Phase 2
explanation all need updating. Cross-check them against the evidence afterwards. §10 has
the search pattern.

---

## 7. Hard constraints — do not relitigate

- **The API key path is closed.** Three keys were supplied. All three authenticated. Two
  returned `400 credit balance too low`, and one was org-scoped with no workspace. The
  user says funding isn't possible. **No key is stored anywhere, and none should be.**
  They were only ever passed as process env vars. The analyst code already supports
  `ANTHROPIC_API_KEY` + `ANTHROPIC_WORKSPACE_ID` for whoever can fund it later.
  **Rotating the three keys is the user's job, because they appear in the old
  transcript.**
- **Port 8000 is taken** by an unrelated app of the user's (`/home/user/farmwiseAi/…`).
  KAVAL's API runs on **8077**. Don't kill the other one.
- **No Earth Engine credentials.** GSE only exists as the prior CropSight export. Anything
  that needs new GSE embeddings is blocked. That includes classifier confidence on
  reserve-forest patches and any geometry outside the 14,611 surveyed parcels.
- **No CDS key** (ERA5-Land) and **no Earthdata login** (MODIS). Temperature comes from
  NASA POWER instead, which needs no key.
- **Sentinel data needs no key.** It comes via anonymous STAC (Element84 for S2,
  Planetary Computer for S1). Early on we wrongly thought GEE was blocking this.

---

## 8. What was running at snapshot 🔄

### STAC acquisition → then Presto (chained)

- Process: `.venv/bin/python -u KAVAL/scripts/p1_acquire_stac.py`
- Log: `/tmp/claude-1000/-home-user-FM-AI/<session>/scratchpad/stac_resume.log`
  (this path is machine- and session-specific and **will not exist elsewhere**)
- At snapshot: **S2 160/160 cached, S1 18/31**, climbing steadily.
- A background chain was waiting for `KAVAL/data/raw/presto_monthly_series.parquet`,
  then would run `scripts/p3b_presto_embeddings.py`.

**Why it had failed before.** Planetary Computer SAS tokens expire. Items were signed at
search time and fetched about 65 minutes later, so all 31 S1 scenes returned HTTP 403
across 8 retry rounds. We had been reading that as "slow". `fetch_s1()` now re-signs each
item immediately before it reads. That fix is in the script.

**How to check on the same machine:**
```bash
cd /home/user/FM_AI
pgrep -fa "venv/bin/python.*p1_acquire_stac"          # still running?
ls .cache/kaval_stac/s1 | wc -l                         # /31
ls -la KAVAL/data/raw/presto_monthly_series.parquet     # produced?
ls -la KAVAL/data/derived/presto_embeddings.parquet     # Presto ran?
```
**Warning:** `pgrep -f p1_acquire_stac` without the `venv/bin/python` prefix also matches
leftover bash wait-loops that contain the script name. That fooled us once. Use the full
pattern above.

**On a different machine:** the 15 GB `.cache/kaval_stac` is not there. Re-running
`p1_acquire_stac.py` re-downloads S2 (~65 min) and then S1. Leave it running in the
background. It resumes from whatever it has cached.

### A second reproducibility audit (status unknown)

A `reproducibility-guard` agent was launched to check the fixes from the first audit. It
never reported back, and most likely hit the session rate limit like the other agents.
**Assume it did not run.** Re-running it is a good early task (§9).

---

## 9. Next actions, in priority order

1. **Check state (§8).** Did the monthly series land? Did Presto run?
2. **When `presto_embeddings.parquet` exists, close the Presto arm.** Add a
   "Presto (128-d)" source, and "GSE + Presto", to
   `scripts/p4_ladder_and_baselines.py` §C (sources), keyed on `parcel_id` and using the
   **same folds**. Re-run p4 (~25 min), then p6 → p7 → p9. Report GSE vs Presto
   **honestly, including the L1C→L2A domain shift** (Presto was pretrained on L1C and we
   feed it L2A) and the taluk-scale meteorology caveat. If the gap is under about 1 fold
   SD, **say it is underpowered**. We already retracted one comparison that flipped sign
   (correction #4).
3. **Propagate the new numbers** to `proposal_updated.md`, `progress.md`,
   `docs/team/*.md`, `DEMO_WALKTHROUGH.md` and `README.md`. The Presto rows currently
   say "not run / acquiring". Update each one.
4. **Re-run the reproducibility guard** (`subagent_type: reproducibility-guard`). Point
   it hard at: the shared-field area apportionment, the boundary-layer-error claim, and
   cross-document number consistency.
5. **Two small open product gaps** from M4's review: `/export` can't reproduce the routed
   worklist (it needs a `priority` column and a `budget` param), and analyst `Citation`
   has no `parcel_id`.
6. **Palette CVD figures are copied, not re-run.** `validate_palette.js` isn't in the
   repo. Either re-run the dataviz validator or state plainly in doc 12 that the figures
   are unverified.
7. Keep `progress.md` current after each of these.

**Don't** start new scope (cross-season change detection, mixed-crop detection, a
second taluk) without the user asking. `plan.md` lists them as deliberate non-starts.

---

## 10. Rules of the codebase

These are enforced in code. Don't weaken them.

- **`kaval/config.py` holds every threshold and constant.** A number in two files means
  one of them is wrong. `AUDIT_CONSTANTS`, `THRESHOLDS` and `TRUST_WEIGHTS` all live
  there.
- **`kaval/splits.py` is the only place splits are made.** `make_splits()` raises on an
  unknown regime name. The group-overlap check **raises** rather than `assert`s, so it
  survives `python -O`. The headline regime is `3-event`, grouping by `bag_id` ∪
  `field_id` via union-find.
- **`metric_response()` in `api/main.py` raises if `split_regime` is missing.** Every
  metric-bearing route goes through it.
- **`provenance.require(path)` guards every load.** A file with no entry in
  `data/PROVENANCE.md` doesn't exist. Write entries only via `provenance.record()`.
- **`label_error_probability()` raises without `model_accuracy`.** A raw margin is not a
  probability.
- **Agreement-status logic exists only in `kaval/audit.py`.** The frontend used to
  duplicate it, and that copy was deleted. Pass thresholds as arguments; **never mutate
  a module global**, because FastAPI runs requests in a threadpool.
- **One name per concept across parquet, API and frontend.** Renaming fields in the API
  once silently broke three UI rows (`snap_m`, `parcels_sharing_field`, `field_area_m2`).
- **Evidence is generated, never hand-edited.** Every figure in every document comes from
  a script writing into `docs/evidence/`.

**After any re-run, find stale numbers with:**
```bash
grep -rnE "81\.[0-9]%|89\.[0-9]%|70\.[0-9]%|18\.3%|4,825|\+16\.[0-9]" KAVAL --include=*.md \
  | grep -v node_modules
```
Then compare what it finds against the evidence JSON.

---

## 11. Mistakes we've already made — don't repeat them

These are in `docs/team/13_CORRECTIONS.md` in full. What they share: **numbers that looked
meaningful and weren't.**

- A routing "lift" of 5.58× that was **exactly 1 ÷ base rate**. It came out the same at
  every budget, so it was pinned by construction. It is now `targeting_efficiency`,
  labelled as pinned.
- "Accuracy within auto-cleared set = 100%" was **circular**, because CONFIRMED is
  defined as the model agreeing. The residual risk (7.6%) is a **rough proxy, NOT a
  bound**.
- "GSE beats GSE+seasonal" flipped sign across three runs, so it was **retracted**. It
  was noise.
- The attention gap was partly **self-referential** (+22.8). Measured against an
  independent baseline it is **+16.2**, and that's the number we report.
- **"FTW within 8% of the registry"** compared whole-taluk area against a registry that
  covers only the villages. Like for like, FTW is **41% short** (7,151 vs 12,097 ha).
  The comparison that made us look good was the one that needed checking.
- Shared-field area was **double-counted 3.88×**. It is now apportioned.
- The CRS was UTM **44N**; the correct zone is **43N**.
- The village-code discrepancy **reversed**. The registry agrees with the *recorded*
  codes, so the **supplied boundary layer** is the likely error, not the surveyors.
- The four "unlabelled villages" are **Reserve Forest**. That area is a negative control,
  and the field-like patches there are **not** evidence of encroachment.
- A slow-looking STAC job had **already failed** on expired tokens. Read the log before
  assuming something is just slow.

**The rule that follows:** before reporting any comparison that favours us, check that
both sides measure the same thing, and check the effect against fold variance.

---

## 12. Environment setup on a new machine

```bash
cd /home/user/FM_AI                       # adjust if the path differs
curl -LsSf https://astral.sh/uv/install.sh | sh    # if uv is absent
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python \
  numpy pandas scikit-learn lightgbm torch geopandas shapely rasterio pyarrow \
  fastapi "uvicorn[standard]" anthropic pystac-client planetary-computer odc-stac einops
uv pip install --python .venv/bin/python --prerelease=allow "ftw-tools>=2.0.0b5"
# Presto: --no-deps is REQUIRED — upstream pins numpy 1.23 / torch 2.0 and would break the venv
uv pip install --python .venv/bin/python --no-deps \
  git+https://github.com/nasaharvest/presto@11e207a668a34336ced1d8e492a1bd5849b96c4a
cd KAVAL/frontend && npm install && npm run build
```

Versions at snapshot: numpy 2.5.3 · pandas 3.0.6 · scikit-learn 1.9.1 · lightgbm 4.7.0 ·
torch 2.10.0 · geopandas 1.2.0 · rasterio 1.5.1 · fastapi 0.142.0 · ftw-tools 2.0.0b5 ·
presto 0.0.1. There is **no pip in the venv**. Always use
`uv pip install --python .venv/bin/python`.

**If `KAVAL/data/` was copied across (148 MB), nothing needs re-running.** If only the
code came across, rebuild in this order (README has the full list):
`p1_repair_ground_truth → p1_register_inputs → p2_parcel_layer → [ftw inference all +
p2_ftw_delineate] → p3_feature_store → p4 (~25 min) → p5 (~1 h) → p6 → p7 → p9`.
`p3_feature_store` also needs the CropSight GEE export at
`CropSight/CropSight_Task3_UPGRADED/06_FEATURE_ACQUISITION/gse_plus_seasonal_features_2024.csv`.

**Run the product:**
```bash
.venv/bin/uvicorn KAVAL.api.main:app --port 8077
cd KAVAL/frontend && npm run dev
```

---

## 13. Useful facts you'd otherwise have to rediscover

- The AOI is Sivagiri taluk, bbox `77.2704,9.1744,77.5500,9.4198`, 437 km², **UTM 43N
  (EPSG:32643)**.
- The survey ran **6–13 Nov 2024**. `timestamp` is MM-DD-YYYY and `image_timestamp` is
  DD-MM-YYYY *in the same row*. `image_timestamp` is authoritative.
- 25 polygons: 21 revenue villages plus 4 Reserve Forest (`village_co='YYY'`).
- 14,611 canonical parcels. 14,310 have features, so 301 are flagged, not dropped.
- Evaluable classes: Rice, Coconut, Maize, Banana, Sugarcane. Seven more collapse into
  `Other`.
- Sentinel-1 over this AOI is **descending orbit only**.
- The FTW model is `FTW_PRUE_EFNET_B7_CCBY`, run via `ftw inference all`. The Sentinel-2
  processing baseline is 5.11 where the model expects 5.1, and the tool warns about it.
- Satellite delineation finds **physical fields, not legal parcels**: 1.94 parcels per
  field on average, up to 19. `field_id` is also a leakage group key.
- The registry (TN Agrisnet) is **not independent**. It is the published aggregate of the
  same survey. That caveat is carried in the API payload.
- **Background agents in this project kept hitting the session rate limit mid-task.**
  Before delegating, weigh whether you can do the work directly. If you do delegate,
  make the task small enough to finish.


---

## 14. Second session, 2026-09-30 → 2026-10-01 (second machine)

**Setup on this machine.** The copied `.venv` had lost its interpreter symlinks. uv was
installed to `~/.local/bin/uv` (not on PATH), CPython 3.12 was fetched with it, and
`.venv/bin/python*` were re-linked to it, so the site-packages were reused. Entry-point
shebangs were repointed to the new root. There's no `curl` here (use `wget`), and port 8000
is free on this machine. See the memory file for detail.

**§9 items closed:**
1. The STAC series completed (S1 31/31). The first resume failed at the DEM step because
   `s3://copernicus-dem-30m` needs anonymous S3. `p1_acquire_stac.py` now sets
   `AWS_NO_SIGN_REQUEST` itself (correction #21).
2. **Presto ran** (`p3b`). That surfaced two contract bugs: `lat`/`lon` now come from the
   feature store, and the DEM terrain is now fed to Presto. p4 §C scores five sources on
   identical rows and folds, paired fold by fold with a computed `underpowered` flag. At
   regime 3-event with the MLP head: GSE 81.5% / 0.563; **Presto 74.2% / 0.452 (Δ −0.111,
   0/5 folds)**; GSE + Presto underpowered. Caveats: L1C→L2A, taluk-scale meteorology,
   parcel-mean series, frozen encoder, and November 2024 only 38.1% S2-observed. The
   ladder and the 81.7% headline reproduce exactly; the p6 figures are unchanged.
3. Documents propagated by `proposal-writer`, in three passes.
4. `reproducibility-guard` ran twice. The first pass found that the registry-attribution
   argument was **circular** (correction #22) and that the shared-field area was
   apportioned rather than aggregated at field level as plan.md requires. `api-engineer`
   fixed both: `kaval/area.py` is now the one crop-area function, and new evidence is in
   `p2d_shared_field_area.json`.
5. `/export?budget=N` reproduces the worklist row for row, with the ranking defined once in
   `audit.routing_priority`. `Citation.parcel_ids` added.
6. The palette check is reproducible: `scripts/p8_validate_palette.py` →
   `p8_palette.{json,md}` (the dataviz validator ships with Claude Code's bundled skill;
   pass `--validator`).

**Also:** p9 was regenerating retraction #4 as a finding (correction #20). The routing note
said "equals 1/base rate" where it is a cap. And, at the user's request, **the analyst
panel now answers without a key** via an offline keyword planner. It uses the same tools,
every answer is labelled `planner: "offline"`, and it is verified 9/9. It is **not** LLM
planning, and Phase 7b's LLM half stays open.

**Pitfall hit twice:** `pgrep -f`/`pkill -f` with a pattern matches the shell running the
command. A wait-loop waited on itself and a `pkill` killed its own shell. Kill by PID from
`ss -ltnp`.

**Run the product:** `.venv/bin/uvicorn KAVAL.api.main:app --port 8077` from the root, and
`cd KAVAL/frontend && npm run dev` (5173, proxies `/api` → 8077).

**Next actions now:** only external inputs remain. These are a funded API key (Phase 7b),
FMB cadastral geometry (Phase 2 IoU and the 911/912 boundary), the survey photographs
(AI-6), GEE and Earthdata credentials, and team names. See `KAVAL/docs/DATA_REQUEST.md`.

### 14b. Addendum, 2026-10-01 (later)

- **Analyst LLM:** `api/llm.py` is a fallback chain: Anthropic → **Gemini free tier**
  (3.8-flash → 3-flash-preview → flash-lite-latest) → Groq/OpenRouter → custom URL →
  **local Qwen2.5-7B** (`KAVAL/scripts/serve_local_llm.sh`, llama.cpp, port 8078) →
  offline planner. Verified on Gemini: 9/9 (`p7_analyst_verification.json` →
  `llm_planner`).
- **The user supplied a Gemini key in chat.** It is NOT stored anywhere by design. Start
  the API with `GEMINI_API_KEY=… .venv/bin/uvicorn KAVAL.api.main:app --port 8077`. Ask
  the user for it, or for a fresh one, in a new session. Recommend rotating the pasted one.
- **Tests:** `pytest KAVAL/tests` (41) and `cd KAVAL/frontend && npx playwright test`
  (22, screenshots in `KAVAL/docs/e2e/`).
- **Phases:** 3 ✅ (the FTW step is scripted and reproduces exactly) and 7 ✅ (Gemini).
  Still external: FMB geometry, survey photos, GEE/Earthdata credentials, team names.

### 14c. Addendum, 2026-10-01 (final)

- A final `reproducibility-guard` audit passed **Phases 3, 7 and 9**, with the correction
  logs consistent (1–23) and all provenance SHAs matching. Its findings are fixed; see
  `KAVAL/progress.md` session log.
- **`export_layer` now exists** (the tool plan.md §3 names). The analyst has **ten** tools.
- Recorded walkthrough: `KAVAL/docs/demo/kaval_walkthrough.webm`; re-record with
  `npx playwright test -c playwright.demo.config.ts`.
- Still the human's call: the plan.md updates (the 4 villages are a Reserve Forest
  negative control, not an inference demo; AI-5 is a provider fallback chain, not
  Claude-only).
