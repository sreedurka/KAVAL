"""
KAVAL — AI-5, the agentic analyst.

An LLM that answers questions about the audit by PLANNING OVER TOOLS, never by
computing anything itself. Two rules follow from the product being an audit:

  * the agent never does arithmetic — model arithmetic is not evidence, so every
    number in an answer came out of a tool call
  * every answer carries citations — an audit system whose analyst asserts numbers
    without provenance defeats its own purpose

The tools wrap the Phase 7a endpoints, so the agent and the frontend read exactly
the same data through the same code path.

Planning is done by an LLM when ANTHROPIC_API_KEY is set and the SDK is
installed. Without them the endpoint falls back to an OFFLINE PLANNER: a
deterministic keyword router over the same TOOLS and the same dispatch(), whose
answers are composed only from tool payloads and are labelled `planner="offline"`
on every response. It is not LLM planning and never claims to be. Set
KAVAL_ANALYST_PLANNER=offline to force it even with a key (for testing), or
=llm to force the LLM path (which then returns 503 without a key).

If the key is org-level rather than workspace-scoped, also set
ANTHROPIC_WORKSPACE_ID (`wrkspc_...`, visible in the Console URL); the API refuses
an unscoped key that does not name a workspace.
"""

import json
import os
import sys
from pathlib import Path
import re
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kaval.config import HEADLINE_REGIME, KEY_PARCEL, THRESHOLDS  # noqa: E402
from . import llm as LLM  # noqa: E402

router = APIRouter()

MODEL = "claude-sonnet-5-5"

SYSTEM = f"""You are KAVAL's analyst. KAVAL audits India's Digital Crop Survey using \
satellite foundation-model embeddings.

The central idea: the crop classifier is an instrument, not the product. The product is \
deciding which surveyor-submitted crop records to trust, which to re-verify, and which \
parcels never need visiting again.

Vocabulary you must use precisely:
- CONFIRMED   satellite agrees with the survey at high calibrated confidence on a \
trusted record. Safe to skip next season.
- DISPUTED    satellite disagrees at high confidence. Top of the field worklist.
- UNCERTAIN   the model cannot separate the classes here.
- UNVERIFIABLE the RECORD is too weak to test - a huge capture-event bag, a distant \
photograph, a mixed-crop declaration. The problem is the evidence, not the field.
- UNSEEN      no survey record exists; satellite-only prediction.

Rules you must not break:

1. NEVER compute a number yourself. Call a tool. If no tool provides it, say so.
2. EVERY number you state must come from a tool result in this conversation.
3. When you state a model metric, state the validation split regime with it. The \
headline regime is '{HEADLINE_REGIME}' (grouped by survey capture event). A bare \
accuracy figure is wrong.
4. NEVER say a parcel or record is "wrong" (and not "wrongly cleared": say "cleared in \
error"). The survey record and the satellite DISAGREE; which is right is what a field \
visit determines.
5. Accuracy on this data is about 82% under the headline regime, not the 95% the \
challenge brief targets. If asked, explain that 95% is only reachable with validation \
leakage, and offer the ladder tool.
6. The crop registry is the published aggregate of the SAME Digital Crop Survey we \
audit. Never present a registry comparison as independent validation; say what it is.
7. Per-class metrics rest on INDEPENDENT capture events, not record counts. Banana has \
653 records but only 64 capture events. Mention effective n when discussing per-class \
performance.
8. When a tool marks a comparison "underpowered", say there is NO measurable \
difference. Never call it slightly better or slightly worse.
9. Corrections from the worklist are MODEL ESTIMATES (a sum of probabilities), never a \
count: say "estimated". Targeting efficiency is capped at 1 / base rate by \
construction; never present it as proof that the ranking works.
10. A difference between two percentages is in percentage POINTS, not percent.
11. The auto-clear residual error rate is a rough proxy, not a bound or a guarantee.
12. Answer only from tools. If no tool covers the question, say so plainly rather than \
assembling an answer from unrelated tools. Questions about one named parcel: get_parcel. \
About calibration: calibration_report. Crop area for a named village: \
crop_area_summary with `village`.
13. Read percentiles correctly: p75 = 2,436 m means 75% of values are AT OR BELOW \
2,436 m (25% above). A parcel below the confidence threshold is UNCERTAIN, never \
DISPUTED. The worklist ranks by P(label needs correction) x area, not by confidence.
14. To export or download data, call export_layer and give the user its URL; never say \
exporting is impossible.
15. Plain text and simple Markdown only: no LaTeX, no $...$ math. Write "P(label \
needs correction) = 0.82", not a formula. Say "needs correction", not "label wrong".

Answer concisely and in plain language. A district agriculture officer is reading."""


TOOLS = [
    {
        "name": "query_parcels",
        "description": "List parcels filtered by village, crop, agreement status, "
                       "confidence range or trust range. `crop` is the SATELLITE-"
                       "PREDICTED crop; `declared_crop` is the crop the surveyor "
                       "recorded (use both for a confusion pair, e.g. declared Banana "
                       "predicted Coconut). Use for questions about specific parcels or "
                       "counts of parcels meeting a condition. Returns a page of "
                       "parcels plus the total count.",
        "input_schema": {
            "type": "object",
            "properties": {
                "village": {"type": "string",
                            "description": "exact village name, e.g. 'Rayagiri - Part-2'"},
                "crop": {"type": "string", "description": "satellite-predicted crop"},
                "declared_crop": {"type": "string",
                                  "description": "crop the surveyor declared"},
                "status": {"type": "string",
                           "enum": ["CONFIRMED", "DISPUTED", "UNCERTAIN",
                                    "UNVERIFIABLE", "UNSEEN"]},
                "min_confidence": {"type": "number"},
                "max_confidence": {"type": "number",
                                   "description": "e.g. 0.8 for 'below 80% confidence'"},
                "min_trust": {"type": "number"},
                "limit": {"type": "integer", "default": 20},
            },
        },
    },
    {
        "name": "crop_area_summary",
        "description": "Crop-wise cultivated area and parcel counts, by village or for "
                       "the whole taluk, from either the satellite prediction or the "
                       "surveyor's declaration. For ONE village, pass `village` (exact "
                       "name) so its rows are returned in full; without it the "
                       "village table is long and may be truncated.",
        "input_schema": {
            "type": "object",
            "properties": {
                "group_by": {"type": "string", "enum": ["village", "taluk"]},
                "village": {"type": "string",
                            "description": "exact village name; implies group_by=village"},
                "source": {"type": "string", "enum": ["predicted", "declared"]},
            },
        },
    },
    {
        "name": "compare_to_registry",
        "description": "Per-village comparison of the satellite-predicted crop mix "
                       "against the Tamil Nadu Agrisnet village-wise Digital Crop "
                       "Survey report for Rabi 2024, sorted by divergence. Compared as "
                       "crop SHARE, not absolute hectares, because our parcel sample "
                       "covers only part of each village. The response carries an "
                       "independence caveat you must repeat: the registry is the "
                       "published aggregate of the same survey, so this is not "
                       "validation against an independent second source.",
        "input_schema": {
            "type": "object",
            "properties": {"min_registry_ha": {"type": "number", "default": 1.0},
                           "village": {"type": "string"},
                           "crop": {"type": "string"}},
        },
    },
    {
        "name": "confusion_report",
        "description": "Per-class precision/recall/F1 with effective sample size "
                       "(independent capture events), the confusion matrix, and the "
                       "most-confused class pairs. Use for 'which crops confuse most' "
                       "or any per-class performance question.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "leakage_ladder",
        "description": "Accuracy and macro F1 for the same model under four validation "
                       "splits, plus the model-head and embedding-source comparisons. "
                       "Use for any question about validation, why accuracy is what it "
                       "is, whether 95% is reachable, or which embedding source is best.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "route_verification_budget",
        "description": "Given a budget of N field visits, return the N parcels that "
                       "maximise expected label corrections, with the random-visit "
                       "counterfactual and the lift. Use for 'where should we send "
                       "surveyors' or 'what would N visits buy'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "budget": {"type": "integer"},
                "village": {"type": "string"},
            },
            "required": ["budget"],
        },
    },
    {
        "name": "auto_clear_summary",
        "description": "Parcels that need not be revisited next season, the surveyor-day "
                       "saving, and the cost assumptions behind it.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "status_summary",
        "description": "Counts and area by agreement status across the taluk. Use for "
                       "'how many parcels are disputed' or an overview.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "ground_truth_forensics",
        "description": "What the supplied survey records actually contain: capture-event "
                       "structure, label inflation, photo-to-parcel distance, effective "
                       "sample size per crop. Use for questions about data quality or "
                       "why the audit exists.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_parcel",
        "description": "The full audit trail of ONE parcel by its parcel_id (e.g. "
                       "'152_399_1'): declared vs predicted crop, calibrated and raw "
                       "confidence, P(label needs correction), trust score and its "
                       "components, capture event, bag size, photo distance, geometry "
                       "source. Use when the user names a parcel.",
        "input_schema": {"type": "object",
                         "properties": {"parcel_id": {"type": "string"}},
                         "required": ["parcel_id"]},
    },
    {
        "name": "calibration_report",
        "description": "How trustworthy the model's confidence is: expected calibration "
                       "error before and after isotonic calibration, mean raw vs "
                       "calibrated confidence against actual accuracy. Use for any "
                       "question about calibration or whether confidence can be trusted.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        # plan.md §3 AI-5 names this tool. The download itself streams from
        # GET /export; the tool prepares it: the exact URL, the row count and
        # columns it will contain, so the answer can hand the user a real file.
        "name": "export_layer",
        "description": "Prepare a download of the classified parcel layer (crop "
                       "prediction, calibrated confidence, trust score, agreement "
                       "status, area) as CSV or GeoJSON, optionally filtered by "
                       "village or agreement status, or as the routed field worklist "
                       "for a visit budget. Returns the download URL, row count and "
                       "columns. Use whenever the user asks to export or download.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fmt": {"type": "string", "enum": ["csv", "geojson"]},
                "village": {"type": "string"},
                "status": {"type": "string",
                           "enum": ["CONFIRMED", "DISPUTED", "UNCERTAIN",
                                    "UNVERIFIABLE", "UNSEEN"]},
                "budget": {"type": "integer",
                           "description": "export the routed worklist for this many "
                                          "field visits instead of the whole layer"},
            },
        },
    },
]


def _truncate(payload: Any, max_rows: int = 40) -> Any:
    """Keep tool results small enough to stay in context without losing the shape."""
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        rows = payload["data"]
        if len(rows) > max_rows:
            payload = dict(payload)
            payload["data"] = rows[:max_rows]
            payload["_truncated"] = f"showing {max_rows} of {len(rows)} rows"
    return payload


def dispatch(name: str, args: dict) -> Any:
    """
    Route a tool call to the same endpoint functions the frontend uses.

    Every parameter that carries a `Query(...)` default must be passed
    EXPLICITLY. FastAPI only resolves those defaults when a request goes through
    the HTTP layer; called directly, the function receives the `Query` object
    itself and fails on the first comparison. That bug would have crashed the
    analyst on five of the brief's six queries in production, so the values are
    threaded through here rather than relying on signature defaults.
    """
    from . import main as M

    t = dict(confidence_high=THRESHOLDS["confidence_high"],
             trust_floor=THRESHOLDS["trust_floor"],
             trust_high=THRESHOLDS["trust_high"])

    if name == "query_parcels":
        return _truncate(M.parcels(
            village=args.get("village"), crop=args.get("crop"), declared_crop=args.get("declared_crop"),
            status=args.get("status"),
            min_confidence=float(args.get("min_confidence", 0.0)),
            max_confidence=float(args.get("max_confidence", 1.0)),
            min_trust=float(args.get("min_trust", 0.0)),
            limit=int(min(args.get("limit", 20), 50)), offset=0, **t))
    if name == "crop_area_summary":
        if args.get("village"):
            args = dict(args, group_by="village")
        out = M.crop_area(group_by=args.get("group_by", "village"),
                          source=args.get("source", "predicted"))
        # Village filter applied BEFORE truncation, so a named village is never cut
        # off the page. Exposed in the tool schema since live testing showed the LLM
        # failing on 12 of 21 villages when it only saw a truncated taluk table.
        if args.get("village") and isinstance(out.get("data"), list):
            want = {v.lower() for v in (args["village"] if isinstance(args["village"], list)
                                        else [args["village"]])}
            out = dict(out)
            out["data"] = [r for r in out["data"]
                           if str(r.get("village_name", "")).lower() in want]
            out["meta"] = dict(out["meta"], n=len(out["data"]))
        return _truncate(out)
    if name == "compare_to_registry":
        return _truncate(M.registry_delta(
            min_registry_ha=float(args.get("min_registry_ha", 1.0)),
            village=args.get("village"), crop=args.get("crop"), limit=200))
    if name == "confusion_report":
        return M.confusion(regime=HEADLINE_REGIME)
    if name == "leakage_ladder":
        return M.ladder()
    if name == "route_verification_budget":
        r = M.worklist(budget=int(args["budget"]), village=args.get("village"), **t)
        # The economics is the answer; the full worklist would flood the context.
        r["data"]["worklist"] = r["data"]["worklist"][:15]
        return r
    if name == "auto_clear_summary":
        return M.auto_clear(**t)
    if name == "status_summary":
        return M.status_summary(**t)
    if name == "ground_truth_forensics":
        return M.forensics()
    if name == "get_parcel":
        return M.parcel_detail(str(args.get("parcel_id", "")).strip())
    if name == "calibration_report":
        return M.calibration()
    if name == "export_layer":
        return _export_layer(M, args, t)
    raise ValueError(f"unknown tool {name}")


def _export_layer(M, args: dict, t: dict) -> dict:
    """Describe the /export download these arguments produce, with its real row count."""
    from urllib.parse import urlencode

    from kaval.audit import routed_worklist
    fmt = args.get("fmt") if args.get("fmt") in ("csv", "geojson") else "csv"
    df = M.recompute_status(M.S.require_audit(), t["confidence_high"],
                            t["trust_floor"], t["trust_high"])
    village, status = args.get("village"), args.get("status")
    budget = int(args["budget"]) if args.get("budget") else None
    if village:
        df = df[df.village_name.astype(str).str.lower() == str(village).lower()]
    if budget:
        df = routed_worklist(df, budget)          # route first, as /export does
        cols = ["rank"] + M.WORKLIST_COLS
    else:
        cols = [KEY_PARCEL, "village_name", "survey_no", "subdivision", "y_true",
                "y_pred", "confidence_calibrated", "trust_score", "agreement_status",
                "p_label_wrong", "suggested_crop", "area_m2", "lat", "lon"]
    if status:
        df = df[df.agreement_status == str(status).upper()]
    q = {k: v for k, v in (("fmt", fmt), ("village", village), ("status", status),
                           ("budget", budget)) if v}
    return {"data": {"url": "/export?" + urlencode(q), "fmt": fmt, "rows": int(len(df)),
                     "columns": cols,
                     "what": ("the routed field worklist, highest priority first"
                              if budget else "the classified parcel layer")},
            "meta": {"n": int(len(df)), "split_regime": HEADLINE_REGIME,
                     "sources": ["data/derived/audit.parquet"]}}


class Query(BaseModel):
    question: str = Field(..., max_length=2000)
    max_turns: int = Field(8, ge=1, le=15)


class Citation(BaseModel):
    source: str
    n: int | None = None
    split_regime: str | None = None
    # The parcels the tool actually returned, so an answer about specific parcels
    # can be traced to them. Capped: a summary tool cites its source, not 14k ids.
    parcel_ids: list[str] = Field(default_factory=list)


def _cited_parcels(out: Any, cap: int = 50) -> list[str]:
    """parcel_id of every row a tool returned, wherever the rows sit in its payload."""
    data = out.get("data") if isinstance(out, dict) else None
    rows = data if isinstance(data, list) else (
        [r for v in data.values() if isinstance(v, list) for r in v]
        if isinstance(data, dict) else [])
    ids = [str(r[KEY_PARCEL]) for r in rows if isinstance(r, dict) and KEY_PARCEL in r]
    return list(dict.fromkeys(ids))[:cap]


def llm_note(p) -> str:
    base = (f"Planned by an LLM ({p.label}) choosing among KAVAL's typed tools; every "
            "figure comes from those tool results.")
    if p.name == "local":
        base += (" This is a small open-weight model running locally on CPU: slower, "
                 "and less reliable at planning than a frontier model.")
    return base


LLM_NOTE = llm_note(LLM.Provider("anthropic", "anthropic", MODEL))
OFFLINE_NOTE = (
    "Answered by KAVAL's offline rule-based planner: the question was routed by keyword "
    "to the same typed tools the LLM agent uses, and every figure comes from those tool "
    "results. This is not LLM planning. Set a free GEMINI_API_KEY (or GROQ_API_KEY / "
    "OPENROUTER_API_KEY), ANTHROPIC_API_KEY, or start the local model "
    "(scripts/serve_local_llm.sh) to use an LLM.")


class Answer(BaseModel):
    answer: str
    citations: list[Citation]
    tool_calls: list[dict]
    # Which planner produced this answer. Defaults describe the LLM path so its
    # code stays untouched; the offline planner sets both explicitly.
    planner: Literal["llm", "offline"] = "llm"
    planner_note: str = LLM_NOTE
    # Which LLM planned it (e.g. "gemini:gemini-flash-lite-latest", "local:qwen2.5-7b…");
    # None for the offline planner.
    provider: str | None = None


def planner_mode() -> Literal["llm", "offline"]:
    """Which planner /analyst/query will use right now."""
    return "offline" if LLM.resolve() is None else "llm"


def _executor(calls: list[dict], citations: list[Citation]):
    """One tool call -> JSON string for the model, recording the call and citation."""
    def run(name: str, args: dict) -> str:
        calls.append({"tool": name, "args": args})
        try:
            out = dispatch(name, dict(args))
            meta = out.get("meta", {}) if isinstance(out, dict) else {}
            citations.append(Citation(
                source=", ".join(meta.get("sources", [])) or name,
                n=meta.get("n"), split_regime=meta.get("split_regime"),
                parcel_ids=_cited_parcels(out)))
            return json.dumps(out, default=str)
        except HTTPException as exc:
            return json.dumps({"error": exc.detail})
        except Exception as exc:                                    # noqa: BLE001
            return json.dumps({"error": f"{type(exc).__name__}: {exc}"})
    return run


def _anthropic_loop(p, q, execute) -> str | None:
    import anthropic
    # An org-level key (one not scoped to a workspace) must name the workspace on
    # every request, or the API rejects it with a 400. Workspace-scoped keys do
    # not need this, so the header is only attached when the variable is set.
    workspace = os.environ.get("ANTHROPIC_WORKSPACE_ID")
    client = anthropic.Anthropic(
        default_headers={"anthropic-workspace-id": workspace} if workspace else None)
    messages = [{"role": "user", "content": q.question}]
    for _ in range(q.max_turns):
        try:
            resp = client.messages.create(
                model=p.model, max_tokens=2000, system=SYSTEM,
                tools=TOOLS, messages=messages)
        except anthropic.APIError as exc:
            raise LLM.ProviderError(f"{p.label}: {type(exc).__name__}") from exc
        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if b.type == "text").strip()
        messages.append({"role": "assistant", "content": resp.content})
        results = [{"type": "tool_result", "tool_use_id": b.id,
                    "content": execute(b.name, dict(b.input))[:20000]}
                   for b in resp.content if b.type == "tool_use"]
        messages.append({"role": "user", "content": results})
    return None


@router.post("/analyst/query", response_model=Answer,
             summary="Ask the agentic analyst a question")
def analyst_query(q: Query):
    chain = LLM.candidates()
    # Skip models cooling down after a quota/overload refusal (but if every model
    # is cooling, try them all anyway rather than give up).
    chain = [p for p in chain if not LLM.cooling_down(p)] or chain
    failed: list[str] = []
    for p in chain:
        # Each attempt starts clean, so a provider that failed mid-loop leaves no
        # half-recorded tool calls in the answer another provider produces.
        calls: list[dict] = []
        citations: list[Citation] = []
        execute = _executor(calls, citations)
        try:
            if p.kind == "anthropic":
                text = _anthropic_loop(p, q, execute)
            else:
                text = LLM.run_openai_compat(p, SYSTEM, q.question, TOOLS, execute,
                                             q.max_turns)
        except LLM.ProviderError as exc:
            failed.append(str(exc))
            continue
        if text is None:
            failed.append(f"{p.label}: did not converge within {q.max_turns} turns")
            continue
        note = llm_note(p)
        if failed:
            note += " Fell back to it after: " + "; ".join(failed) + "."
        return Answer(answer=text, citations=citations, tool_calls=calls,
                      planner="llm", planner_note=note, provider=p.label)

    # No LLM configured, or every one failed: the offline planner, saying why.
    a = offline_answer(q.question)
    if failed:
        a.planner_note = ("Every configured LLM failed (" + "; ".join(failed) + "), so "
                          "this was answered by the offline planner instead. "
                          + a.planner_note)
    return a


@router.get("/analyst/tools", summary="The tools the analyst can call")
def analyst_tools():
    p = LLM.resolve()
    mode = "offline" if p is None else "llm"
    return {"model": p.model if p else None, "provider": p.label if p else None,
            "fallback_chain": [c.label for c in LLM.candidates()] + ["offline"],
            "planner": mode,
            "planner_note": OFFLINE_NOTE if p is None else llm_note(p),
            "offline_intents": [i[0] for i in INTENTS],
            "tools": [
        {"name": t["name"], "description": t["description"]} for t in TOOLS]}


# ═══════════════════════════════════════════════════════════════════════════
# OFFLINE PLANNER
#
# Used when no ANTHROPIC_API_KEY (or no SDK) is available, or when forced with
# KAVAL_ANALYST_PLANNER=offline. It is deliberately dumb and deliberately
# labelled: keyword scoring picks an intent, the intent is a fixed plan of
# (tool, args) over the SAME TOOLS and dispatch() the LLM uses, and the answer is
# a template filled only from the tool payloads. It does no arithmetic beyond
# formatting (a fraction printed as a percentage), never reaches for a number a
# tool did not return, and when no intent matches it says so instead of guessing.
# ═══════════════════════════════════════════════════════════════════════════

_STATUSES = ("CONFIRMED", "DISPUTED", "UNCERTAIN", "UNVERIFIABLE", "UNSEEN")
_CROP_ALIASES = {"rice": "Rice (Paddy)", "paddy": "Rice (Paddy)"}
_DEFAULT_BUDGET = 500   # the API's own default for /audit/worklist?budget=


def _pct(x: Any) -> str:
    return "n/a" if x is None else f"{100 * float(x):.1f}%"


def _num(x: Any, d: int = 1) -> str:
    if x is None:
        return "n/a"
    return f"{float(x):,.{d}f}" if d else f"{int(round(float(x))):,}"


def _regime(out: Any) -> str:
    meta = out.get("meta", {}) if isinstance(out, dict) else {}
    return meta.get("split_regime") or "none - not a model metric"


def _norm(t: str) -> str:
    return re.sub(r"[\s\-_]+", " ", t.lower()).strip()


def _catalogue() -> tuple[list[str], list[str]]:
    """Village and crop names, used ONLY to recognise slots in the question text."""
    from . import main as M
    try:
        rows = M.crop_area(group_by="village", source="predicted")["data"]
    except Exception:                                               # noqa: BLE001
        return [], []
    villages = sorted({str(r["village_name"]) for r in rows if r.get("village_name")})
    crops = sorted({str(r["crop"]) for r in rows if r.get("crop")})
    return villages, crops


def parse_slots(question: str) -> dict:
    """Pull the simple slots a plan needs out of the question text."""
    q = question.lower()
    qn = _norm(question)
    villages, crops = _catalogue()
    s: dict[str, Any] = {"villages": [], "crop": None, "status": None,
                         "threshold": None, "budget": None}

    exact = [v for v in villages if re.search(rf"\b{re.escape(_norm(v))}\b", qn)]
    if exact:
        s["villages"] = exact
    else:
        def base(v: str) -> str:
            return re.sub(r"\s*-\s*part\s*-?\s*\d+\s*$", "", v, flags=re.I)
        s["villages"] = [v for v in villages
                         if re.search(rf"\b{re.escape(_norm(base(v)))}\b", qn)]

    for alias, crop in _CROP_ALIASES.items():
        if re.search(rf"\b{alias}\b", q) and crop in crops:
            s["crop"] = crop
    if not s["crop"]:
        for c in crops:
            if c.lower() == "other":
                continue        # "other" is ordinary English, not a crop mention
            if re.search(rf"\b{re.escape(re.sub(r'\s*\(.*\)', '', c).lower())}\b", q):
                s["crop"] = c
                break

    m = re.search(r"\b(confirmed|disputed|uncertain|unverifiable|unseen)\b", q)
    if m:
        s["status"] = m.group(1).upper()

    if "confiden" in q:
        m = (re.search(r"(\d{1,3}(?:\.\d+)?)\s*(?:%|percent)", q)
             or re.search(r"confiden\w*\s+(?:below|under|less than|<=?|of)\s*(0?\.\d+)", q))
        if m:
            v = float(m.group(1))
            v = v / 100 if v > 1 else v
            if 0 < v <= 1:
                s["threshold"] = v

    m = (re.search(r"(\d[\d,]*)\s+(?:field\s+)?(?:surveyors?|visits?|inspections?)\b", q)
         or re.search(r"\bbudget\s+(?:of\s+)?(\d[\d,]*)", q)
         or re.search(r"\b(\d[\d,]*)\s+parcels?\s+to\s+visit", q))
    if m:
        s["budget"] = int(m.group(1).replace(",", ""))
    return s


class _Run:
    """Executes a plan through dispatch() and records calls and citations exactly
    as the LLM loop does."""

    def __init__(self):
        self.calls: list[dict] = []
        self.citations: list[Citation] = []
        self.errors: list[str] = []

    def call(self, name: str, args: dict) -> Any:
        self.calls.append({"tool": name, "args": args})
        try:
            out = dispatch(name, dict(args))
        except HTTPException as exc:
            self.errors.append(f"{name} failed: {exc.detail}")
            return None
        except Exception as exc:                                    # noqa: BLE001
            self.errors.append(f"{name} failed: {type(exc).__name__}: {exc}")
            return None
        meta = out.get("meta", {}) if isinstance(out, dict) else {}
        self.citations.append(Citation(
            source=", ".join(meta.get("sources", [])) or name,
            n=meta.get("n"), split_regime=meta.get("split_regime"),
            parcel_ids=_cited_parcels(out)))
        return out


def _ids(rows: list[dict], k: int = 10) -> str:
    return ", ".join(str(r[KEY_PARCEL]) for r in rows[:k] if KEY_PARCEL in r) or "none returned"


def _thr(s: dict) -> float:
    return s["threshold"] if s["threshold"] is not None else THRESHOLDS["confidence_high"]


# ── intent handlers: each runs its plan and returns paragraphs of answer text ──

def _h_taluk_area(run: _Run, q: str, s: dict) -> list[str]:
    thr = _thr(s)
    ca = run.call("crop_area_summary", {"group_by": "taluk"})
    st = run.call("status_summary", {})
    qa = {"max_confidence": thr, "limit": 10}
    if s["crop"]:
        qa["crop"] = s["crop"]
    lo = run.call("query_parcels", qa)
    out = []
    if ca:
        rows = sorted(ca["data"], key=lambda r: -(r.get("area_ha") or 0))
        out.append(f"Satellite classification, crop-wise for the whole study area "
                   f"[split regime: {_regime(ca)}]:\n" + "\n".join(
            f"- {r['crop']}: {_num(r['parcels'], 0)} parcels, {_num(r['area_ha'])} ha, "
            f"mean calibrated confidence {_pct(r['mean_confidence'])}" for r in rows)
            + "\nArea is counted at field level where several records share one field "
              "(see the tool's area note).")
    if st:
        out.append(f"Agreement status [split regime: {_regime(st)}]: " + "; ".join(
            f"{r['agreement_status']} {_num(r['parcels'], 0)} parcels ({_num(r['area_ha'])} ha)"
            for r in st["data"]) + ".")
    if lo:
        crop = f" predicted as {s['crop']}" if s["crop"] else ""
        out.append(
            f"Low confidence: {_num(lo['meta']['n'], 0)} parcels{crop} have calibrated "
            f"confidence at or below {_pct(thr)} [split regime: {_regime(lo)}] and need "
            f"field verification before their prediction is relied on. First "
            f"{min(10, len(lo['data']))} returned: {_ids(lo['data'])}. For a ranked, "
            f"budgeted visit list ask 'Where should we send N surveyors?'.")
    return out


def _h_village_area(run: _Run, q: str, s: dict) -> list[str]:
    thr = _thr(s)
    villages = s["villages"][:3]
    out = []
    if not villages:
        ca = run.call("crop_area_summary", {"group_by": "village"})
        lo = run.call("query_parcels", {"max_confidence": thr, "limit": 10})
        names, _ = _catalogue()
        out.append("No village was named in the question, so the offline planner "
                   "cannot pick 'the selected village' for you. Ask again naming one "
                   f"of: {', '.join(names)}.")
        if ca:
            out.append(f"The village-wise crop-area table has {_num(ca['meta']['n'], 0)} "
                       f"village-by-crop rows [split regime: {_regime(ca)}] "
                       "(GET /summary/crop-area?group_by=village).")
        if lo:
            out.append(f"Across all villages, {_num(lo['meta']['n'], 0)} parcels are at or "
                       f"below {_pct(thr)} calibrated confidence [split regime: "
                       f"{_regime(lo)}]. First returned: {_ids(lo['data'])}.")
        return out

    ca = run.call("crop_area_summary", {"group_by": "village", "village": villages})
    for v in villages:
        lines = []
        if ca:
            rows = sorted([r for r in ca["data"] if r.get("village_name") == v],
                          key=lambda r: -(r.get("area_ha") or 0))
            lines.append(f"{v}, crop-wise (satellite prediction) [split regime: "
                         f"{_regime(ca)}]:\n" + ("\n".join(
                f"- {r['crop']}: {_num(r['parcels'], 0)} parcels, {_num(r['area_ha'], 2)} ha, "
                f"mean calibrated confidence {_pct(r['mean_confidence'])}" for r in rows)
                or "- no rows returned"))
        lo = run.call("query_parcels", {"village": v, "max_confidence": thr, "limit": 10})
        if lo:
            lines.append(
                f"Below {_pct(thr)} confidence in {v}: {_num(lo['meta']['n'], 0)} parcels "
                f"[split regime: {_regime(lo)}]. Highlighted (first "
                f"{min(10, len(lo['data']))}):\n" + ("\n".join(
                    f"- {r[KEY_PARCEL]}: satellite {r['y_pred']} at "
                    f"{_pct(r['confidence_calibrated'])}, survey says {r['y_true']}, "
                    f"status {r['agreement_status']}" for r in lo["data"])
                    or "- none"))
        out.append("\n".join(lines))
    return out


def _h_sources(run: _Run, q: str, s: dict) -> list[str]:
    lad = run.call("leakage_ladder", {})
    if not lad:
        return []
    d = lad["data"]
    out = ["Embedding sources compared on the same rows, each "
           "labelled with its split regime:\n" + "\n".join(
        f"- {r['source']}: accuracy {_pct(r['accuracy'])}, macro F1 {_num(r['macro_f1'], 3)} "
        f"[split regime: {r.get('regime')}]" for r in d.get("sources", []))]
    comps = [c for c in d.get("source_comparisons", []) if "presto" in c["source"].lower()]
    if comps:
        out.append("Paired fold-by-fold comparison against the reference:\n" + "\n".join(
            f"- {c['source']} vs {c['reference']} ({c['metric']}): mean paired difference "
            f"{float(c['mean_delta']):+.3f}, {c['folds_favouring_source']} of {c['folds']} "
            f"folds favour {c['source']} - "
            + ("underpowered: the gap is inside fold-to-fold noise, so no winner can be "
               "declared." if c.get("underpowered") else
               "not underpowered: the gap is larger than fold-to-fold noise.")
            for c in comps))
    cav = d.get("presto_caveats") or {}
    if cav:
        out.append("Caveats on the Presto run: " + " ".join(
            x for x in (cav.get("domain_shift_note"), cav.get("meteorology_caveat")) if x)
            + f" Sentinel-2 observed fraction {_pct(cav.get('s2_observed_fraction'))}, "
              f"Sentinel-1 {_pct(cav.get('s1_observed_fraction'))}.")
    if d.get("sources_pending"):
        out.append(f"Still pending: {d['sources_pending']}.")
    return out


def _h_registry(run: _Run, q: str, s: dict) -> list[str]:
    base = {"min_registry_ha": 1.0}
    if s["crop"]:
        base["crop"] = s["crop"]
    targets = s["villages"][:3] or [None]
    out = []
    for v in targets:
        args = dict(base, **({"village": v} if v else {}))
        reg = run.call("compare_to_registry", args)
        if not reg:
            continue
        d = reg["data"]
        rows = d.get("rows", [])[:8]
        seen = list(dict.fromkeys(r["village"] for r in d.get("rows", [])))[:5]
        scope = f" for {v}" if v else ""
        out.append(
            f"Satellite crop share versus the Agrisnet {d.get('season', '')} registry{scope}, "
            f"largest gaps first [split regime: {_regime(reg)}; {_num(reg['meta']['n'], 0)} "
            f"village-crop rows with at least 1 ha in the registry]:\n" + ("\n".join(
                f"- {r['village']} / {r['crop']}: registry {_pct(r['registry_share'])} of "
                f"village cropped area vs satellite {_pct(r['satellite_share'])} "
                f"(difference {100 * float(r['delta_share']):+.1f} points; "
                f"{_num(r['parcels'], 0)} parcels, mean confidence "
                f"{_pct(r['mean_confidence'])})" for r in rows) or "- no rows returned"))
        if not v and seen:
            out.append(f"Villages with the largest crop-share gaps: {', '.join(seen)}. The "
                       "tool ranks by the size of the share gap; it runs no significance "
                       "test, so 'significantly' here means 'largest gap', not a "
                       "statistical claim.")
        if d.get("systematic_bias_by_crop"):
            out.append("Taluk-wide bias by crop (satellite share minus registry share): "
                       + "; ".join(f"{b['crop']} {100 * float(b['bias']):+.1f} points"
                                   for b in d["systematic_bias_by_crop"]) + ".")
        if d.get("independence_caveat"):
            out.append("Not independent validation: " + d["independence_caveat"])
        if d.get("scale_caveat") and v is None:
            out.append(d["scale_caveat"])
    return out


def _h_confusion(run: _Run, q: str, s: dict) -> list[str]:
    cr = run.call("confusion_report", {})
    if not cr:
        return []
    d = cr["data"]
    top = d.get("top_confusions", [])[:5]
    per = {r["crop"]: r for r in d.get("per_class", [])}
    mv = cr["meta"].get("model_version")
    out = [f"Most-confused crop pairs, out-of-fold records [split regime: {_regime(cr)}"
           f"{'; model ' + mv if mv else ''}]:\n" + "\n".join(
        f"- survey says {t['true']}, satellite predicts {t['predicted']}: "
        f"{_num(t['n'], 0)} records" for t in top)]
    involved = list(dict.fromkeys([t["true"] for t in top] + [t["predicted"] for t in top]))
    out.append("Per-class performance, with effective sample size (independent capture "
               f"events, not records) [split regime: {_regime(cr)}]:\n" + "\n".join(
        f"- {c}: F1 {_num(per[c]['f1'], 2)}, precision {_num(per[c]['precision'], 2)}, "
        f"recall {_num(per[c]['recall'], 2)} on {_num(per[c]['records'], 0)} records but "
        f"only {_num(per[c]['capture_events'], 0)} capture events"
        for c in involved if c in per))
    if top:
        t0 = top[0]
        dp = run.call("query_parcels", {"status": "DISPUTED", "crop": t0["predicted"],
                                        "limit": 50})
        if dp:
            reps = [r for r in dp["data"] if r.get("y_true") == t0["true"]][:5] or dp["data"][:5]
            out.append(
                f"Representative disagreements for the top pair (DISPUTED parcels the "
                f"satellite calls {t0['predicted']}; {_num(dp['meta']['n'], 0)} in total) "
                f"[split regime: {_regime(dp)}]:\n" + ("\n".join(
                    f"- {r[KEY_PARCEL]} ({r['village_name']}): survey {r['y_true']}, "
                    f"satellite {r['y_pred']} at {_pct(r['confidence_calibrated'])}, "
                    f"record trust {_num(r['trust_score'], 2)}" for r in reps) or "- none")
                + "\nThe survey record and the satellite disagree on these; a field "
                  "visit decides which is right.")
    return out


def _h_export(run: _Run, q: str, s: dict) -> list[str]:
    filt = {}
    if s["villages"]:
        filt["village"] = s["villages"][0]
    if s["status"]:
        filt["status"] = s["status"]
    ex = {fmt: run.call("export_layer", dict(filt, fmt=fmt)) for fmt in ("geojson", "csv")}
    ca = run.call("crop_area_summary", {"group_by": "village"})
    budget = s["budget"] or _DEFAULT_BUDGET
    wl = run.call("export_layer", dict(filt, fmt="csv", budget=budget))
    out = ["Downloads, prepared by the export_layer tool (the files stream when these URLs "
           "are fetched, with the same rows and thresholds as the screens):"]
    lines = []
    for fmt, e in ex.items():
        if e:
            d = e["data"]
            lines.append(f"- Classified parcel layer with calibrated confidence, trust and "
                         f"agreement status ({fmt}): GET {d['url']} - {_num(d['rows'], 0)} "
                         f"parcels [split regime: {_regime(e)}]")
    lines.append("- Crop-area summary (JSON): GET /summary/crop-area?group_by=village"
                 + (f" - {_num(ca['meta']['n'], 0)} village-by-crop rows [split regime: "
                    f"{_regime(ca)}]" if ca else "")
                 + "; taluk totals: GET /summary/crop-area?group_by=taluk")
    if wl:
        lines.append(f"- Budget-routed field worklist: GET {wl['data']['url']} - "
                     f"{_num(wl['data']['rows'], 0)} visits, highest priority first "
                     "(change budget= to the number of visits you can afford)")
    out.append("\n".join(lines))
    return out


def _h_budget(run: _Run, q: str, s: dict) -> list[str]:
    budget = s["budget"] or _DEFAULT_BUDGET
    out = []
    if not s["budget"]:
        out.append(f"No visit count was given; using the API default budget of {budget}.")
    if not 1 <= budget <= 20000:
        return out + [f"A budget of {budget} is outside what the worklist tool accepts "
                      "(1 to 20,000 visits)."]
    args: dict[str, Any] = {"budget": budget}
    if s["villages"]:
        args["village"] = s["villages"][0]
    r = run.call("route_verification_budget", args)
    if not r:
        return out
    e, wl = r["data"]["economics"], r["data"]["worklist"]
    where = f" in {args['village']}" if "village" in args else ""
    if "surveyor" in q.lower():
        out.append(f"The tool budgets field VISITS, not surveyors, so {budget} is read as "
                   f"{budget} parcel visits.")
    out.append(
        f"Routing {_num(e['budget'], 0)} visits{where} by the chance the record needs "
        f"correction x area covers {_num(e['pct_of_parcels_visited'], 2)}% of parcels and "
        f"{_num(e['routed_area_ha'])} ha [split regime: {_regime(r)}]:\n"
        f"- expected label corrections: {_num(e['estimated_corrections_routed'])} routed vs "
        f"{_num(e['estimated_corrections_random'])} (sd {_num(e['estimated_corrections_random_std'])}) "
        f"for the same number of random visits\n"
        f"- survey/satellite disagreements reached: {_num(e['routed_disagreements_found'], 0)} "
        f"of {_num(e['total_disagreements_available'], 0)} available, against "
        f"{_num(e['random_disagreements_expected'])} expected at random (targeting "
        f"efficiency {_num(e['targeting_efficiency'], 2)}x)")
    if e.get("targeting_is_pinned_by_construction"):
        out.append(f"The targeting efficiency is at its ceiling by construction (1 / base "
                   f"disagreement rate of {_pct(e['base_disagreement_rate'])}), so read the "
                   "expected-corrections figures, not the efficiency.")
    out.append("Top of the queue:\n" + "\n".join(
        f"- {w[KEY_PARCEL]} ({w['village_name']}): survey {w['y_true']}, satellite "
        f"{w['y_pred']} at {_pct(w['confidence_calibrated'])}, "
        f"P(needs correction) {_num(w['p_label_wrong'], 2)}, {w['agreement_status']}"
        for w in wl[:5]) + f"\nFull list: GET /export?fmt=csv&budget={budget}"
        + (f"&village={args['village']}" if "village" in args else ""))
    return out


def _h_auto_clear(run: _Run, q: str, s: dict) -> list[str]:
    a = run.call("auto_clear_summary", {})
    c = run.call("query_parcels", {"status": "CONFIRMED", "limit": 10})
    out = []
    if a:
        d, th = a["data"], a["meta"].get("thresholds") or {}
        ca = d.get("cost_assumption") or {}
        out.append(
            f"{_num(d['parcels'], 0)} parcels ({_num(d['pct_of_parcels'])}% of the audited "
            f"set, {_num(d['area_ha'])} ha) are CONFIRMED: satellite agrees with the survey "
            f"at calibrated confidence of at least {_pct(th.get('confidence_high'))} on a "
            f"record with trust of at least {_num(th.get('trust_high'), 2)} [split regime: "
            f"{_regime(a)}]. Not revisiting them next season saves "
            f"{_num(d['surveyor_days_saved'])} of {_num(d['baseline_surveyor_days'])} "
            f"surveyor-days, assuming {ca.get('parcels_per_surveyor_day')} parcels per "
            f"surveyor-day ({ca.get('note', 'an assumption')}).")
        out.append(
            f"Residual risk: an expected {_pct(d['expected_residual_error_rate'])} of them "
            f"(about {_num(d['expected_parcels_wrongly_cleared'], 0)} parcels, from the "
            "calibrated confidence) could have satellite and surveyor agreeing on a crop "
            "that is not there. That cannot be measured against the surveyor's own label; "
            "settle it with an independent field audit of a CONFIRMED sample.")
    if c:
        out.append(f"Sample CONFIRMED parcels: {_ids(c['data'])}. Full list: "
                   "GET /export?fmt=csv&status=CONFIRMED")
    return out


def _h_forensics(run: _Run, q: str, s: dict) -> list[str]:
    f = run.call("ground_truth_forensics", {})
    if not f:
        return []
    d = f["data"]
    pd_ = d.get("photo_to_parcel_distance_m", {})
    eff = sorted(d.get("per_crop_effective_n", {}).items(), key=lambda kv: -kv[1]["records"])
    const = (d.get("capture_events_with_constant_field") or {}).get("final_crop_name")
    return [
        f"The supplied survey sample holds {_num(d['n_records'], 0)} records from only "
        f"{_num(d['n_capture_events'], 0)} capture events (photographs) across "
        f"{d['n_villages']} villages: a label inflation factor of {d['label_inflation_factor']}. "
        f"{d['pct_records_in_multi_parcel_events']}% of records share a photograph with other "
        f"parcels, up to {d['max_parcels_per_capture_event']} parcels per photograph"
        + (f", and the crop label is constant within all {_num(const, 0)} capture events"
           if const is not None else "") + ", so siblings are not independent evidence.",
        f"Photo-to-parcel distance: median {_num(pd_.get('median'), 0)} m, 90th percentile "
        f"{_num(pd_.get('p90'), 0)} m; {pd_.get('pct_over_1km')}% of photographs are over "
        f"1 km from the parcel and {pd_.get('pct_over_3km')}% over 3 km.",
        "Effective sample size per crop (records / independent capture events):\n"
        + "\n".join(f"- {k}: {_num(v['records'], 0)} / {_num(v['capture_events'], 0)}"
                    for k, v in eff[:6]),
        f"{_num(d.get('n_mixed_crop_declarations'), 0)} mixed-crop declarations; parcel "
        f"polygons supplied: {'yes' if d.get('parcel_polygons_supplied') else 'no'}. This is "
        "a description of the data, not a model metric, so no split regime applies. It is "
        "why KAVAL grades each record's trust before testing it.",
    ]


_PARCEL_ID = re.compile(r"\b\d{1,3}_\d{1,4}_[0-9A-Za-z]{1,6}\b")


def _h_parcel(run: _Run, q: str, s: dict) -> list[str]:
    m = _PARCEL_ID.search(q)
    if not m:
        return []
    r = run.call("get_parcel", {"parcel_id": m.group(0)})
    if not r:
        return [f"No parcel {m.group(0)} in the audited set."]
    d = r["data"]
    ev = d.get("evidence") or {}
    return [f"Parcel {d['parcel_id']} ({d.get('village')}, survey no {d.get('survey_no')}/"
            f"{d.get('subdivision')}): the surveyor declared {d.get('declared_crop')}; the "
            f"satellite predicts {d.get('predicted_crop')} at calibrated confidence "
            f"{_pct(d.get('confidence_calibrated'))}. Agreement status "
            f"{d.get('agreement_status')}; Record Trust Score {_num(d.get('trust_score'), 2)}; "
            f"P(label needs correction) {_pct(d.get('p_label_wrong'))} [split regime: "
            f"{_regime(r)}].",
            f"Evidence behind the record: its photograph is {_num(ev.get('photo_distance_m'), 0)} m "
            f"from the parcel and documents {_num(ev.get('parcels_sharing_this_photograph'), 0)} "
            f"parcel(s); geometry source {ev.get('geometry_source')}; area "
            f"{_num((d.get('area_m2') or 0) / 1e4, 2)} ha."]


def _h_pair(run: _Run, q: str, s: dict) -> list[str]:
    """'surveyed as X but predicted as Y': parcels for one declared/predicted pair."""
    _v, crops = _catalogue()
    ql = q.lower()
    found = sorted({c for c in crops if c.lower().split(" (")[0] in ql},
                   key=lambda c: ql.index(c.lower().split(" (")[0]))
    if len(found) < 2:
        return []
    declared, predicted = found[0], found[1]
    r = run.call("query_parcels", {"declared_crop": declared, "crop": predicted, "limit": 8})
    if not r:
        return []
    return [f"{_num(r['meta']['n'], 0)} parcels were declared {declared} by the surveyor and "
            f"predicted {predicted} from satellite [split regime: {_regime(r)}]. They "
            "disagree; a field visit decides which is right. Representative parcels:\n"
            + "\n".join(f"- {x['parcel_id']} ({x.get('village_name')}): {x.get('agreement_status')}, "
                        f"calibrated confidence {_pct(x.get('confidence_calibrated'))}"
                        for x in r["data"][:8])]


def _h_calibration(run: _Run, q: str, s: dict) -> list[str]:
    r = run.call("calibration_report", {})
    if not r:
        return []
    d = r["data"]
    return [f"Raw confidence averaged {_pct(d['mean_confidence_raw'])} against an actual "
            f"accuracy of {_pct(d['actual_accuracy'])}: expected calibration error "
            f"{d['ece_raw']:.4f}. After cross-fitted isotonic calibration it is "
            f"{d['ece_calibrated']:.4f}, with mean confidence {_pct(d['mean_confidence_calibrated'])} "
            f"[split regime: {_regime(r)}]."]


def _h_leakage(run: _Run, q: str, s: dict) -> list[str]:
    lad = run.call("leakage_ladder", {})
    if not lad:
        return []
    d = lad["data"]
    h = d.get("headline", {})
    return [
        f"Headline: {h.get('head')} under the '{h.get('regime')}' split regime (grouped by "
        f"survey capture event): accuracy {_pct(h.get('accuracy'))}, macro F1 "
        f"{_num(h.get('macro_f1'), 3)}.",
        "The Leakage Ladder, one reference head held fixed across four splits (so its "
        "3-event row can differ slightly from the headline head above):\n" + "\n".join(
            f"- {r['regime']}: accuracy {_pct(r['accuracy'])}, macro F1 "
            f"{_num(r['macro_f1'], 3)} - {r.get('description', '')}" for r in d.get("ladder", [])),
        "The easier splits put sibling parcels from one photograph on both sides of the "
        "split, so they reward memorising capture events rather than recognising crops. "
        "The brief's 95% target is not reached under the headline regime; a figure near it "
        "on this data would be evidence of leakage, not skill.",
    ]


def _h_status(run: _Run, q: str, s: dict) -> list[str]:
    st = run.call("status_summary", {})
    out = []
    if st:
        th = st["meta"].get("thresholds") or {}
        out.append(f"Agreement status across the taluk [split regime: {_regime(st)}; "
                   f"thresholds confidence_high={th.get('confidence_high')}, "
                   f"trust_floor={th.get('trust_floor')}, trust_high={th.get('trust_high')}]:\n"
                   + "\n".join(f"- {r['agreement_status']}: {_num(r['parcels'], 0)} parcels, "
                               f"{_num(r['area_ha'])} ha" for r in st["data"]))
    if s["status"]:
        args: dict[str, Any] = {"status": s["status"], "limit": 10}
        if s["villages"]:
            args["village"] = s["villages"][0]
        p = run.call("query_parcels", args)
        if p:
            where = f" in {args['village']}" if "village" in args else ""
            out.append(f"{s['status']}{where}: {_num(p['meta']['n'], 0)} parcels; first "
                       f"returned: {_ids(p['data'])}.")
    out.append("DISPUTED means the survey record and the satellite disagree at high "
               "confidence; a field visit decides which is right.")
    return out


def _any(q: str, *pats: str) -> bool:
    return any(re.search(p, q) for p in pats)


# (name, what it answers, scorer(q_lower, slots) -> int, handler).
# List order is the tie-break priority.
INTENTS = [
    ("parcel", "the audit trail of one named parcel (by parcel_id)",
     lambda q, s: 9 if _PARCEL_ID.search(q) else 0, _h_parcel),
    ("pair", "parcels surveyed as one crop but predicted as another",
     lambda q, s: 8 if (_any(q, r"declared|surveyed|survey says|recorded")
                        and _any(q, r"predicted|satellite")) else 0, _h_pair),
    ("calibration", "how well calibrated the model's confidence is",
     lambda q, s: 6 if _any(q, r"calibrat", r"\bece\b", r"over-?confiden") else 0,
     _h_calibration),
    ("export", "export / download the classified layer, confidence and crop-area summary",
     lambda q, s: 6 if _any(q, r"\b(export|download)", r"\bcsv\b", r"geojson",
                            r"shapefile") else 0, _h_export),
    ("auto_clear", "which parcels can we stop visiting (auto-clear and surveyor-days saved)",
     lambda q, s: 6 if _any(q, r"stop visiting", r"no longer (need to )?visit",
                            r"need not be (re)?visit", r"\bskip", r"auto[- ]?clear",
                            r"never need", r"\brevisit") else 0, _h_auto_clear),
    ("sources", "Google Satellite Embeddings versus Presto (and other embedding sources)",
     lambda q, s: (4 * _any(q, r"presto") + 2 * _any(q, r"satellite embedding", r"\bgse\b",
                                                      r"google")
                   + 2 * (_any(q, r"embedding") and _any(q, r"compar", r"versus", r"\bvs\b",
                                                          r"better", r"best", r"source"))),
     _h_sources),
    ("registry", "villages whose predicted crop area differs from the registry",
     lambda q, s: (5 + _any(q, r"villages? where", r"differ", r"diverg"))
     if _any(q, r"registry", r"agrisnet", r"villages?\b.*\b(diverg|differ)",
             r"(diverg|differ)\w*.*\bdeclared") else 0, _h_registry),
    ("confusion", "the most-confused crop classes, with representative disagreements",
     lambda q, s: 5 if _any(q, r"confus", r"misclassif", r"mix(es|ed)? up",
                            r"representative errors?", r"mistak") else 0, _h_confusion),
    ("budget", "where to send N surveyors / what N field visits buy",
     lambda q, s: (3 + 2 * (s["budget"] is not None))
     if _any(q, r"surveyors?", r"field visits?", r"\bvisits?\b", r"where should (we|i) send",
             r"\bbudget\b", r"worklist") else 0, _h_budget),
    ("forensics", "how trustworthy the ground truth is (capture events, photo distance)",
     lambda q, s: 5 if _any(q, r"ground[- ]?truth", r"trustworth", r"data quality",
                            r"label inflation", r"capture events?", r"photo") else 0,
     _h_forensics),
    ("leakage", "why accuracy is not 95% / the Leakage Ladder",
     lambda q, s: (4 + _any(q, r"accura")) if _any(q, r"\b95\b", r"leak", r"why\b.*accura",
                                                   r"headline", r"validat", r"how accurate",
                                                   r"ladder", r"split regime") else 0,
     _h_leakage),
    ("status", "agreement-status breakdown (how many CONFIRMED / DISPUTED / ...)",
     lambda q, s: 5 if _any(q, r"status (breakdown|summary)", r"breakdown", r"overview",
                            r"how many\b.*\b(confirmed|disputed|uncertain|unverifiable|unseen)",
                            r"agreement status") else 0, _h_status),
    ("village_area", "crop-wise area for a named village, highlighting parcels below X% "
                     "confidence",
     lambda q, s: (4 + (s["threshold"] is not None))
     if ((s["villages"] or _any(q, r"selected village", r"this village", r"\bby village",
                                r"village[- ]wise", r"per village", r"each village"))
         and _any(q, r"crop", r"area", r"hectare", r"confiden", r"parcels?")) else 0,
     _h_village_area),
    ("taluk_area", "crop-wise area and confidence for all parcels, with low-confidence "
                   "parcels needing field verification",
     lambda q, s: (3 + _any(q, r"low[- ]confidence", r"field verification", r"confiden"))
     if _any(q, r"crop[- ]?wise", r"cultivated area", r"classif(y|ied) all",
             r"all (agricultural )?parcels", r"study area", r"taluk") else 0, _h_taluk_area),
]

# Secondary intents that would repeat or contradict the primary one.
_EXCLUDES = {"village_area": {"taluk_area"}, "registry": {"village_area", "taluk_area"},
             "export": {"village_area", "taluk_area"}, "auto_clear": {"budget"},
             "sources": {"leakage"}, "leakage": {"sources"}}


def route(question: str) -> tuple[list[str], dict]:
    """Intent names the offline planner will run for this question, and the slots."""
    s = parse_slots(question)
    q = question.lower()
    scored = [(sc(q, s), i, name) for i, (name, _d, sc, _h) in enumerate(INTENTS)]
    scored = sorted([x for x in scored if x[0] > 0], key=lambda x: (-x[0], x[1]))
    if not scored or scored[0][0] < 3:
        return [], s
    chosen = [scored[0][2]]
    for sc, _i, name in scored[1:]:
        if sc >= 5 and name not in _EXCLUDES.get(chosen[0], set()):
            chosen.append(name)
            break
    return chosen, s


def offline_answer(question: str) -> Answer:
    intents, slots = route(question)
    run = _Run()
    if not intents:
        caps = "\n".join(f"- {d}" for _n, d, _s, _h in INTENTS)
        return Answer(
            answer="The offline planner did not recognise this question, and it does not "
                   "guess. It can answer:\n" + caps + "\nThe LLM analyst, which can plan "
                   "over the tools for free-form questions, needs a model: a free "
                   "GEMINI_API_KEY (or GROQ_API_KEY / OPENROUTER_API_KEY), "
                   "ANTHROPIC_API_KEY, or the local model (scripts/serve_local_llm.sh).",
            citations=[], tool_calls=[], planner="offline", planner_note=OFFLINE_NOTE)

    handlers = {name: h for name, _d, _s, h in INTENTS}
    parts: list[str] = []
    for name in intents:
        try:
            parts.extend(handlers[name](run, question, slots))
        except Exception as exc:                                    # noqa: BLE001
            run.errors.append(f"could not compose the '{name}' answer from the tool "
                              f"payloads: {type(exc).__name__}: {exc}")
    if run.errors:
        parts.append("Not answered: " + "; ".join(run.errors))
    if not parts:
        parts = ["The tools returned nothing to answer from."]
    return Answer(answer="\n\n".join(parts), citations=run.citations,
                  tool_calls=run.calls, planner="offline", planner_note=OFFLINE_NOTE)
