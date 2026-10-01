# KAVAL

**An Agentic Satellite Audit System for the Digital Crop Survey**
FarmwiseAI Campus Product Challenge — Task 3

> The classifier is the instrument. The product is the audit.

---

## Start here

| File | What it is |
|---|---|
| **[`plan.md`](plan.md)** | **Authoritative.** Thesis, locked architecture decisions, AI spine, data register, phases with acceptance gates, risks, team, agent rules. Everything defers to this file. |
| [`proposal_updated.md`](proposal_updated.md) | The submission document for FarmwiseAI. |
| [`docs/evidence/gt_forensics.md`](docs/evidence/gt_forensics.md) | What the supplied ground truth actually contains. |
| [`docs/evidence/p4_results.md`](docs/evidence/p4_results.md) | Same model, four splits. The canonical ladder. |
| [`docs/VALIDATION_REPORT.md`](docs/VALIDATION_REPORT.md) | The full validation report. |
| [`progress.md`](progress.md) | Live phase status, every correction and retraction. |
| [`docs/PHASE2_GATE_EXPLANATION.md`](docs/PHASE2_GATE_EXPLANATION.md) | Why the delineation gate failed, and what that measured. |
| [`docs/DEMO_WALKTHROUGH.md`](docs/DEMO_WALKTHROUGH.md) | A twelve-minute route through the system, in the order that makes the argument. |
| [`docs/DATA_REQUEST.md`](docs/DATA_REQUEST.md) | The two things we would ask FarmwiseAI for. |

## The short version

The supplied 14,643 Digital Crop Survey records resolve to **3,204 photo-capture events** —
one photograph supplies a crop label to up to 43 parcels, and the parcels sharing a label
sit a median 117 m apart. The photograph itself sits a median 1.4 km from the parcel it
documents.

Holding the model, features and hyper-parameters fixed and varying only the split,
the accuracy gap between the loosest and strictest regime is large enough that the
headline number is mostly a property of the split, not the model. The canonical figures
live in **[`docs/evidence/p4_results.md`](docs/evidence/p4_results.md)** and are
deliberately not duplicated here: a number in two files means one of them is wrong.

Grouping by parcel — the obvious control — changes nothing. Only capture-event grouping
exposes the drop. The brief's >95% target is not reachable honestly, so KAVAL builds what
the target was standing in for: a system that tells an agriculture department which survey
records to trust, which to re-verify, and which parcels never need visiting again.

## What has actually been run

This is not a proposal for a pipeline; the pipeline runs. Every figure in every document
regenerates from a script in `scripts/` writing into `docs/evidence/`.

| Phase | What exists |
|---|---|
| 0 Evidence | Ground-truth forensics; the Leakage Ladder |
| 1 Acquisition | Record repair; TN Agrisnet village registry (Rabi 2024, 21 villages); Presto checkpoint and monthly Sentinel-1/2 series per parcel, embedded to 128-d; CHIRPS rainfall; Sentinel-2 via STAC |
| 2 Geometry | FTW delineation on real Sentinel-2 — 64,708 raw polygons covering 13,062 ha across the whole taluk; after dropping 178 slivers, 64,530 fields (12,246.7 ha) are used downstream; Voronoi fallback for unmatched points |
| 3 Features | 14,611 parcels, 76 features, `field_id` carried for leakage grouping |
| 4 Validation | Four split regimes, four model heads, five feature sources, identical folds. The Presto arm ran: under the 3-event regime (MLP, 5-fold) frozen Presto alone reaches 74.2% / 0.452 macro F1 against GSE's 81.5% / 0.563, behind in all 5 folds, and GSE + Presto is within fold noise of GSE alone. Caveats and paired deltas: [`docs/evidence/p4_results.md`](docs/evidence/p4_results.md) |
| 5 MIL | Attention-MIL over capture-event bags |
| 6 Audit | Calibration, confident learning, trust score, agreement status, budget routing |
| 7 Surface | FastAPI, 17 routes; agentic analyst over 9 typed tools |
| 8 Product | React + Leaflet, map coloured by agreement status |
| 9 Report | Validation report under every split regime |

## Reproduce

```bash
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python numpy pandas scikit-learn lightgbm \
    geopandas shapely rasterio pyarrow torch fastapi "uvicorn[standard]"

.venv/bin/python KAVAL/scripts/gt_forensics.py              # forensics, seconds
.venv/bin/python KAVAL/scripts/p1_repair_ground_truth.py    # canonical records
.venv/bin/python KAVAL/scripts/p1_register_inputs.py        # provenance for supplied data
.venv/bin/python KAVAL/scripts/p2_parcel_layer.py           # Voronoi fallback geometry
.venv/bin/python KAVAL/scripts/p3_feature_store.py          # feature store
.venv/bin/python KAVAL/scripts/p4_ladder_and_baselines.py   # the ladder, ~25 min
.venv/bin/python KAVAL/scripts/p5_mil.py                    # attention-MIL, ~1 h
.venv/bin/python KAVAL/scripts/p6_audit.py                  # trust, calibration, routing
.venv/bin/python KAVAL/scripts/p7_registry_comparison.py    # vs the TN registry
.venv/bin/python KAVAL/scripts/p9_validation_report.py      # the report
```

Satellite delineation (Phase 2 primary path) additionally needs `ftw-tools`:

```bash
uv pip install --python .venv/bin/python --prerelease=allow "ftw-tools>=2.0.0b5"
.venv/bin/ftw inference all --out KAVAL/data/interim/ftw_run \
    --model FTW_PRUE_EFNET_B7_CCBY --year 2024 \
    --bbox "77.2704,9.1744,77.5500,9.4198" --gpu -1
.venv/bin/python KAVAL/scripts/p2_ftw_delineate.py \
    --fields KAVAL/data/interim/ftw_run/polygons.parquet
```

## Run the product

```bash
.venv/bin/uvicorn KAVAL.api.main:app --port 8077     # API + agentic analyst
cd KAVAL/frontend && npm install && npm run dev      # React + Leaflet
```

**The analyst's LLM.** It uses the first of these that is available: `ANTHROPIC_API_KEY`;
a **free** `GEMINI_API_KEY` (Google AI Studio, no card needed), `GROQ_API_KEY` or
`OPENROUTER_API_KEY`; or a **local, keyless** open-weight model. To run the local one:

```bash
KAVAL/scripts/serve_local_llm.sh     # llama.cpp + Qwen2.5-7B on 127.0.0.1:8078 (CPU: 1–3 min/question)
```

With none of them, the panel still answers through an offline keyword planner, labelled
"offline planner — not LLM" on every answer. Details: `docs/team/10_API_ANALYST.md`.
The local-model binaries and weights live in `~/.local/share/kaval-llm/` (llama.cpp
release build; `Qwen2.5-7B-Instruct-Q4_K_M.gguf` from Hugging Face).

## Windows

Everything ships as one zip: `KAVAL/scripts/make_package.py` builds `KAVAL_Package.zip`.
Unzip it, double-click `setup.cmd` once, then `run.cmd`. Details and troubleshooting are in
`WINDOWS_SETUP.md` at the package root.

## Watch it

`docs/demo/kaval_walkthrough.webm`: the 12-minute argument of `docs/DEMO_WALKTHROUGH.md`
in under two minutes, recorded through the running product. Re-record it with
`cd KAVAL/frontend && npx playwright test -c playwright.demo.config.ts`.

## Test it

```bash
.venv/bin/python -m pytest KAVAL/tests -q                 # 41 behavioural API tests
cd KAVAL/frontend && npx playwright test                  # UI e2e, screenshots → docs/e2e/
.venv/bin/python KAVAL/scripts/p7_verify_analyst.py [--llm]   # analyst; --llm also scores the active LLM
```

## Layout

```
KAVAL/
  plan.md                 authoritative project plan
  proposal_updated.md     FarmwiseAI submission
  scripts/                every number in every document regenerates from here
  docs/evidence/          generated artefacts (json + md)
  data/                   acquired data; each file needs a PROVENANCE.md entry

.claude/
  agents/                 14 phase-owning agents
  skills/                 9 skills encoding the project's rules
```

## Agents and skills

Phases are executed by agents in `.claude/agents/`. The human makes architecture
decisions; agents do the rest.

**Agents** — `gt-forensics` · `data-acquisition` · `parcel-delineation` ·
`embedding-engineer` · `leakage-auditor` · `mil-modeler` · `calibration-trust` ·
`verification-economics` · `api-engineer` · `agent-analyst-builder` ·
`frontend-engineer` · `validation-reporter` · `proposal-writer` · `reproducibility-guard`

**Skills** — `leakage-protocol` · `metrics-report` · `parcel-join` · `gee-export` ·
`audit-signals` · `data-provenance` · `fastapi-contract` · `react-map-ui` ·
`proposal-style`

The four rules that bind all of them:

1. `plan.md` is authoritative.
2. No number without a script.
3. No result without its split regime named.
4. Never claim >95% accuracy — if a run produces it, that is a bug report.

## Prior work

`../CropSight/CropSight_Task3_UPGRADED/` is superseded as a proposal and retained as
evidence. Its Earth Engine feature acquisition produced the GSE + seasonal Sentinel table
that made the leakage measurements possible. See `plan.md` §12.
