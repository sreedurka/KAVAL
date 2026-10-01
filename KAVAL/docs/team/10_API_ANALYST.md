# 10 · API & Agentic Analyst

**Owner: M3 (Audit Logic & Backend) · Phase 7 · AI-5**

The tool layer, the offline planner and planning by Gemini are verified; planning by Claude is not. Be exact about which.

---

## 1. The API is a tool surface, not a data feed

A normal backend serves a web page. This one has a second, stricter consumer: an **LLM
agent that plans over it**. So every route is designed to be selected by a model reading
its description, not only called by a frontend.

That changes how you write it. **Descriptions are part of the contract** — the agent picks
tools by reading them, so each states what it returns and when to use it.

## 2. The 17 routes

| Purpose | Routes |
|---|---|
| **Health** | `GET /health` — reports which phases have run |
| **Parcels** | `GET /parcels` (filter by village, crop, status, confidence, trust) · `GET /parcels/{id}` (full audit trail) |
| **Summaries** | `GET /summary/crop-area` · `GET /summary/registry-delta` |
| **Audit — the product** | `GET /audit/worklist` · `GET /audit/auto-clear` · `GET /audit/status-summary` |
| **Validation** | `GET /validation/ladder` · `/validation/confusion` · `/validation/calibration` |
| **Evidence** | `GET /evidence/forensics` |
| **Geometry** | `GET /geo/villages` · `GET /geo/parcels` |
| **Export** | `GET /export` (CSV or GeoJSON, streamed) |
| **Analyst** | `POST /analyst/query` · `GET /analyst/tools` |

Read-only throughout. KAVAL audits; it never writes back to survey records.

**How `/summary/crop-area` counts area.** Area comes from the field-level aggregator
(`kaval/area.py`), not a per-parcel sum. Where several survey records share one delineated
field (`ftw_shared`), the field is assigned **one** crop — the label with the largest
apportioned area inside it — so one physical field is never split across crops. Totals are
unchanged. Each row carries `conflicted_area_ha`, the area of fields whose records disagree
on the label, so the majority rule does not hide the disagreement; the rule text travels in
the response `notes` (same text as `area_rule` in `p7_registry.json`). Parcel counts and
mean confidence stay per parcel, so a crop can list parcels yet carry 0 ha. The area is
**audited** area: 301 parcels (112.6 ha) without satellite features never reach the audit
(`p2d_shared_field_area.json`), so the taluk total is 2,137.6 ha, not the feature store's
2,250.2 ha.

## 3. The structural guarantees

Convention fails. Each of these is enforced in code.

### A metric cannot leave the process without its split regime

```python
def metric_response(data, *, split_regime, sources, **kw):
    if not split_regime:
        raise RuntimeError("a response containing a metric must name its split regime")
```

Every route that returns a number goes through `metric_response()`. An audit found eight
routes that used the plain `envelope()` instead and returned `split_regime: null`; they
were rerouted. The frontend can only label a regime it is told, so this was not cosmetic.

### The agreement-status rule exists in exactly one place

`/parcels`, `/audit/*` and `/geo/parcels` all accept `confidence_high`, `trust_floor` and
`trust_high`, and call `kaval.audit.agreement_status()`. The frontend originally
re-derived the rule in TypeScript; we deleted that file and added the parameters to the
API. A duplicated business rule drifts. An extra query parameter does not.

### Thread-safety

`recompute_status()` originally **mutated a module-level `THRESHOLDS` dict** and restored
it in a `finally`. FastAPI runs sync endpoints in a threadpool, so two concurrent requests
with different thresholds would have corrupted each other's results — a slider moved in
one browser tab changing another user's map. Thresholds are now passed as an **argument**.

### NaN is not JSON

`photo_distance_m` is legitimately null for the 13 records whose photo coordinate geocodes
outside the study area. Serialising NaN raised a 500 on `/parcels`. `envelope()` now
sanitises centrally via `_jsonable()`, so no individual route can reintroduce it.

### Names are the same everywhere

We briefly renamed the Phase 2 geometry fields in the API (`snapped_m`,
`legal_parcels_sharing_this_field`) while the parquet and the frontend used `snap_m` and
`parcels_sharing_field`. Because the client types them optional, nothing errored — three
panel rows silently never rendered, including the one that shows the "fields are not
parcels" finding. **One name per concept, everywhere.**

## 4. The agentic analyst

`api/analyst.py`. An LLM that answers questions by **planning over tools**.

**Two rules follow from the product being an audit:**

1. **The agent never does arithmetic.** Model arithmetic is not evidence. Every number in
   an answer came out of a tool call.
2. **Every answer carries citations.** An audit system whose analyst asserts numbers
   without provenance defeats its own purpose.

### The twelve tools

| Tool | Exercised by harness |
|---|---|
| `query_parcels` | ✅ |
| `crop_area_summary` | ✅ |
| `compare_to_registry` | ✅ |
| `confusion_report` | ✅ |
| `leakage_ladder` | ✅ |
| `route_verification_budget` | ✅ |
| `auto_clear_summary` | ✅ |
| `status_summary` | ✅ |
| `ground_truth_forensics` | ✅ |
| `get_parcel` | ✅ |
| `calibration_report` | ✅ |
| `export_layer` | ✅ (row counts checked against what `/export` actually serves) |

### The system prompt's rules

The prompt is where the product's discipline is imposed on the model:

- Never compute a number yourself; call a tool
- Every number must come from a tool result in this conversation
- **Any metric is stated with its split regime**
- **Never say a parcel is "wrong"** — the survey and the satellite *disagree*; which is
  right is what a field visit determines
- Accuracy is ~82% under the headline regime; if asked about 95%, explain it is reachable
  only with leakage
- Per-class metrics rest on **independent capture events**, not record counts
- The registry is the aggregate of the same survey — never present it as independent
  validation

## 5. The bug the verification harness caught

`dispatch()` routes a tool call to the same endpoint functions the frontend uses — by
calling them **directly as Python functions**.

**FastAPI only resolves `Query(...)` defaults when a request arrives through the HTTP
layer.** Called directly, a parameter defaulting to `Query(0.8)` arrives as the `Query`
*object*, and the first comparison fails:

```
TypeError: '>=' not supported between instances of 'float' and 'Query'
```

**That would have crashed the analyst on five of the brief's six queries in production.**

It is invisible to type-checking and to any test that goes through HTTP — both work fine.
Only *executing the tool layer* exposed it. `dispatch()` now threads every parameter
explicitly.

*In review:* this is the answer to "how do you test an LLM integration?" — you test the
deterministic layer beneath it exhaustively, because that is where the crashes live.

## 6. The honest gate status

`plan.md` §6 requires *"all six brief queries answered end-to-end; each answer traceable
to tool calls."* That has two halves.

| Half | Status |
|---|---|
| **Tool layer** — every brief query answerable, every tool exercised, every answer carrying `meta.sources` | ✅ **6/6 brief queries, 3/3 product queries, 9/9 tools** — `scripts/p7_verify_analyst.py`, no key needed |
| **Offline planner** — keyword routing to the same tools, answer composed only from their results | ✅ **9/9 by function call, 9/9 over HTTP**; a nonsense question gets 0 tool calls — same script, `offline_planner` in `p7_analyst_verification.json` |
| **LLM planning, Gemini** — the model selects and composes the right tools | ✅ **9/9 core questions, 2/2 extended** (`llm_planner` in the same file); see "Measured: planning by Gemini" |
| **LLM planning, Claude** — the project's first-choice model | ❌ **Not verified**: no funded key |

Three API keys were supplied and tested. All authenticated; two returned `400 — credit
balance is too low` and one was org-scoped without a workspace header. The account cannot
be funded, so Claude's planning is still unverified. Gemini's free tier closed the gate
instead, measured per question.

**Say precisely what that means:** every tool returns what its question needs and refuses
to emit an unlabelled metric, and Gemini chooses and composes those tools correctly on all
nine questions. We have **not** shown that Claude does. That needs `ANTHROPIC_API_KEY`
(plus `ANTHROPIC_WORKSPACE_ID` for an org-scoped key) and a `--llm` run of the verifier.

**Do not** say "the analyst is verified" without naming the model.

### Which model plans: the provider layer

`api/llm.py` decides which LLM, if any, plans over the tools. It checks, in order, and
takes the first match:

| # | Condition | Provider | Cost |
|---|---|---|---|
| 1 | `KAVAL_LLM_PROVIDER` set | forces `anthropic`, `gemini`, `groq`, `openrouter`, `local` or `offline` | — |
| 2 | `ANTHROPIC_API_KEY` | Claude (Messages API) | paid |
| 3 | `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Gemini 3.8-flash → 3-flash-preview → flash-lite (2.5-flash is closed to new accounts), OpenAI-compatible endpoint | **free tier** (about 10 requests/min, 250/day) |
| 4 | `GROQ_API_KEY` | Llama 3.3 70B on Groq | free tier |
| 5 | `OPENROUTER_API_KEY` | a `:free` model on OpenRouter | free tier |
| 6 | `KAVAL_LLM_BASE_URL` | any OpenAI-compatible server | — |
| 7 | a server on `127.0.0.1:8078` | **local open-weight model**, no key (`scripts/serve_local_llm.sh`) | free |
| 8 | none of the above | the offline keyword planner | free |

Every provider except Anthropic speaks the same OpenAI-style tool-calling protocol, so
one loop serves them all, over the same twelve tools, the same `dispatch()` and the same
citations. If a provider fails (a free tier's rate limit, a stopped local server), the
answer falls back to the offline planner and its note says why. Keys are read from the
environment at call time and never stored or logged.

**The local model.** `scripts/serve_local_llm.sh` runs llama.cpp's `llama-server` with
Qwen2.5-7B-Instruct (Q4_K_M, Apache-2.0), using its native tool-call template. On this
project's laptop CPU (Core Ultra 7 255H, power-limited) it reads about 35 tokens/s and
writes 3–4, so a question takes one to three minutes. A GPU, or a free Gemini key, makes
it interactive. Whatever answers, the UI names it on every reply ("LLM · local:qwen…").

### Measured: planning by Gemini

`scripts/p7_verify_analyst.py --llm` puts the 6 brief and 3 product questions (the core
set), plus 2 extended questions (a parcel lookup and a calibration question), to the
active LLM and scores each one: did an LLM answer, did it call the expected tools, does
every number trace to a tool result, does every metric citation name its split regime,
and does it keep the language rules. On Gemini's free tier:

| Check | Result |
|---|---|
| Core questions (6 brief + 3 product) | **9 / 9** pass |
| Extended questions (parcel lookup, calibration) | **2 / 2** pass |
| Not run for quota | 0 |
| Per-question detail | `docs/evidence/p7_analyst_verification.json` → `llm_planner` |

The per-question record says which model in the fallback chain answered, the tools it
chose, its time, and any figure not traceable to a tool result. Those details change from
run to run (which model answers depends on Gemini's load that minute), so we quote the
stable result and point to the file. A typical answer takes a few seconds. The weakness
is stable too: the model sometimes skips a secondary tool call or states a figure no tool
returned (a mis-rounding, or a number it derived itself). The grounding check flags these,
and every answer shows its tool calls so they can be checked. **Scope:** this is evidence
about Gemini's planning, not Claude's, and the evidence file says so.

**Say this in a review:** the model picks the right tools and its figures are grounded,
but it sometimes skips a secondary call or states a figure no tool returned, so the
grounding check, the citations and the "tool calls" drawer are there to check it.

### What the panel does without a key

Rather than return a 503, `/analyst/query` falls back to an **offline planner** when no key
is set. It scores the question against thirteen intents (budget routing, auto-clear, GSE vs
Presto, registry delta, confusion, crop area, parcel lookup, calibration, and others), parses the obvious slots (a
budget N, a confidence threshold, a village, a crop, a status), calls the **same typed
tools** through the same `dispatch()`, and composes a templated answer from their payloads.
Citations, parcel IDs and split regimes come out exactly as they do on the LLM path. It
never guesses: a question it can't route gets zero tool calls and a list of what it can
answer.

Every answer carries `planner: "offline"` and a note saying it is keyword routing, not LLM
planning. The UI shows an "offline planner — not LLM" chip on each one. With a key set, the
LLM path takes over unchanged; `KAVAL_ANALYST_PLANNER=offline` forces the fallback for
testing.

So the panel **works**, and the claim stays narrow: routing by keyword proves the tool
layer answers the brief's questions end to end. It proves nothing about whether an LLM
would pick the same tools.

---

## Questions you must be able to answer

**"Does the analyst actually work?"**
> Yes, measured. On Gemini's free tier the analyst passes all nine brief and product
> questions and both extended ones (parcel lookup, calibration), planning its own tool
> calls. It sometimes skips a secondary tool call or states a figure no tool returned; the
> grounding check flags these, and every answer shows its tool calls.
> If Gemini is busy it falls back automatically to a smaller Gemini model, then a local
> model, then an offline keyword planner, and every answer says which one answered.
> Claude's planning is not verified; we had no funded key.

**"Isn't a keyword planner just a chatbot pretending?"**
> It would be if it didn't say so. Every answer is stamped `planner: offline`, the UI says
> "not LLM", and it only states numbers the tools returned. Its job is to keep the product
> usable and to prove the tool layer end to end; LLM planning is still the open half of the
> gate.

**"How do you test an LLM integration without an LLM?"**
> You test the deterministic layer beneath it exhaustively — that is where the crashes
> are. Our harness dispatches every tool with the arguments an agent would choose and
> asserts each payload contains what the question needs. It found a bug that would have
> crashed five of six queries. What it cannot show is tool *selection*, which needs a live
> call.

**"What stops the model making up a number?"**
> Two things. The system prompt forbids it, which is a request. And structurally, the
> model has no way to compute: it only receives tool results, and a metric cannot be
> served without its split regime. The prompt is the soft guard; the API is the hard one.

**"Why not just let the frontend do the threshold logic?"**
> Because the rule would then exist twice. The frontend originally did, and it would
> drift from the server. It is one extra query parameter to keep it in one place, and it
> means the map, the worklist, the saving and the LLM's answers all use the same rule.

**"What if two users move the sliders at once?"**
> That was a real bug. `recompute_status` originally patched a module global under
> FastAPI's threadpool, so one user's threshold could corrupt another's result. Thresholds
> are now passed as an argument, so requests cannot interact.
