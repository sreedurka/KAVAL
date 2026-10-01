"""
KAVAL / Phase 7b — verification harness for the agentic analyst.

plan.md §6 Phase 7 gate: "all six brief queries answered end-to-end; each answer
traceable to tool calls."

That gate has two halves:

  (a) the TOOL LAYER can actually answer each of the challenge brief's analysis
      requests, and every answer carries provenance;
  (b) the LLM correctly PLANS over those tools.

This script verifies (a) exhaustively and offline, by dispatching the tools with
the arguments an agent would choose and asserting the returned payloads contain
what the question asks for. It cannot verify (b) — that needs a live model call
and ANTHROPIC_API_KEY, which is not set in this environment. The evidence artefact
says so explicitly rather than letting the gate look closed.

Section 3 runs the OFFLINE PLANNER (analyst.offline_answer, the keyword-routed
fallback used when no key is set) end to end on all nine questions, both as a
function and through POST /analyst/query, and checks routing, provenance, split
regimes and the language rules. The offline planner is not LLM planning, so it
does not close (b) either.

Run:  .venv/bin/python KAVAL/scripts/p7_verify_analyst.py
Out:  docs/evidence/p7_analyst_verification.json
"""

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from KAVAL.api import analyst as A  # noqa: E402
from kaval.config import EVIDENCE, HEADLINE_REGIME  # noqa: E402

# The six analysis requests the challenge brief lists, each mapped to the tool
# calls an analyst must make and the facts the answer has to contain.
BRIEF_QUERIES = [
    {
        "question": "Using the supplied satellite embeddings, classify all agricultural "
                    "parcels in the selected study area. Show crop-wise cultivated area "
                    "and confidence, and highlight low-confidence parcels that require "
                    "field verification.",
        "calls": [("crop_area_summary", {"group_by": "taluk"}),
                  ("query_parcels", {"status": "UNCERTAIN", "limit": 5}),
                  ("status_summary", {})],
        "requires": ["area_ha", "agreement_status"],
    },
    {
        "question": "Show crop-wise area for the selected village and highlight parcels "
                    "below 80% confidence.",
        "calls": [("crop_area_summary", {"group_by": "village"}),
                  ("query_parcels", {"max_confidence": 0.8, "limit": 5})],
        "requires": ["area_ha", "confidence_calibrated"],
    },
    {
        "question": "Compare the performance obtained from Google Satellite Embeddings "
                    "and Presto embeddings where both are supplied.",
        "calls": [("leakage_ladder", {})],
        # A `sources` key alone once passed this with no Presto row in it. The answer
        # needs the Presto result itself, the paired comparison that says whether
        # the gap is real, and the caveats that qualify it.
        "requires": ["sources", "source_comparisons", "presto_caveats"],
        "requires_text": ["Presto ("],
    },
    {
        "question": "Show villages where predicted crop area differs significantly from "
                    "the supplied registry.",
        "calls": [("compare_to_registry", {"min_registry_ha": 1.0})],
        "requires": ["delta_share", "independence_caveat"],
    },
    {
        "question": "List the crop classes with the highest confusion and show "
                    "representative errors.",
        "calls": [("confusion_report", {}),
                  ("query_parcels", {"status": "DISPUTED", "limit": 5})],
        "requires": ["top_confusions", "per_class"],
    },
    {
        "question": "Export the classified parcel layer, confidence values and crop-area "
                    "summary.",
        # export_layer is the tool plan.md §3 names; an earlier run scored an LLM
        # that REFUSED to export as a pass, because no tool offered one.
        "calls": [("export_layer", {"fmt": "geojson"}),
                  ("crop_area_summary", {"group_by": "village"})],
        "requires": ["url", "area_ha"],
    },
]

# Beyond the brief: the questions this product exists to answer.
PRODUCT_QUERIES = [
    {"question": "Where should we send 500 surveyors next season?",
     "calls": [("route_verification_budget", {"budget": 500})],
     "requires": ["targeting_efficiency", "base_disagreement_rate"]},
    {"question": "Which parcels can we stop visiting?",
     "calls": [("auto_clear_summary", {})],
     "requires": ["surveyor_days_saved", "residual_note"]},
    {"question": "How trustworthy is the ground truth itself?",
     "calls": [("ground_truth_forensics", {})],
     "requires": ["label_inflation_factor", "photo_to_parcel_distance_m"]},
]


# Two tools added after live testing (2026-10-01): kept OUT of the 6 brief + 3
# product core so the headline stays comparable, and reported separately.
EXTENDED_QUERIES = [
    {"question": "Tell me about parcel 152_399_1.",
     "calls": [("get_parcel", {"parcel_id": "152_399_1"})],
     "requires": ["parcel_id"]},
    {"question": "How well calibrated is the model's confidence?",
     "calls": [("calibration_report", {})],
     "requires": ["ece_calibrated"]},
]


def contains_key(obj, key):
    """Does this key appear anywhere in the payload?"""
    if isinstance(obj, dict):
        return key in obj or any(contains_key(v, key) for v in obj.values())
    if isinstance(obj, list):
        return any(contains_key(v, key) for v in obj)
    return False


def check(case):
    result = {"question": case["question"], "tool_calls": [], "passed": True,
              "failures": []}
    for tool, args in case["calls"]:
        rec = {"tool": tool, "args": args}
        try:
            out = A.dispatch(tool, dict(args))
            meta = out.get("meta", {}) if isinstance(out, dict) else {}
            rec["ok"] = True
            rec["rows"] = meta.get("n")
            rec["split_regime"] = meta.get("split_regime")
            rec["sources"] = meta.get("sources")
            # Provenance is the point: an answer nobody can trace is not an audit.
            if not meta.get("sources"):
                result["failures"].append(f"{tool}: no sources in meta")
                result["passed"] = False
            rec["payload_keys"] = (list(out.get("data", {}).keys())
                                   if isinstance(out.get("data"), dict)
                                   else f"list[{len(out.get('data', []))}]")
        except Exception as exc:                                   # noqa: BLE001
            rec["ok"] = False
            rec["error"] = f"{type(exc).__name__}: {exc}"
            result["failures"].append(f"{tool}: {rec['error']}")
            result["passed"] = False
        result["tool_calls"].append(rec)

    payloads = []
    for tool, args in case["calls"]:
        try:
            payloads.append(A.dispatch(tool, dict(args)))
        except Exception:                                          # noqa: BLE001
            pass
    for key in case["requires"]:
        if not any(contains_key(p, key) for p in payloads):
            result["failures"].append(f"no tool returned '{key}'")
            result["passed"] = False
    blob = json.dumps(payloads, default=str)
    for text in case.get("requires_text", []):
        if text not in blob:
            result["failures"].append(f"no tool returned content matching {text!r}")
            result["passed"] = False
    return result


# ── Section 3: the offline planner, end to end ─────────────────────────────────

NONSENSE = "What is the capital of France?"
# Every tool except the data-description one serves a model-derived figure, so its
# citation must name a split regime.
NON_METRIC_TOOLS = {"ground_truth_forensics"}
NUM = re.compile(r"(?<![\w.])[-+]?\d[\d,]*(?:\.\d+)?")


def _numeric_leaves(obj, out):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k != "generated_at":
                _numeric_leaves(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _numeric_leaves(v, out)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        out.append(float(obj))
    elif isinstance(obj, str):
        # Survey numbers, subdivisions and parcel ids are strings ("399", "152_399_1"),
        # and a model may quote them; they are grounded too.
        for tok in re.findall(r"\d+(?:\.\d+)?", obj):
            out.append(float(tok))
    return out


def _grounded_numbers(answer, payloads):
    """Numbers in the answer that equal a payload value (as printed: rounded to the
    answer's precision, directly or as a percentage). Trivial small integers are
    skipped so a stray '5' cannot pass the check on its own."""
    vals = _numeric_leaves(payloads, [])
    hits = []
    for tok in NUM.findall(answer):
        t = tok.replace(",", "")
        a = float(t)
        d = len(t.split(".")[1]) if "." in t else 0
        if d == 0 and abs(a) < 10:
            continue
        # Within half a unit of the stated precision: 23.65 -> "23.7" is correct
        # half-up rounding (Python's float round says 23.6), while 142.834 -> "142.84"
        # is a real mis-rounding and still fails.
        tol = 0.5 * 10 ** -d + 1e-9
        if any(abs(a - v) <= tol or abs(a - 100 * v) <= tol for v in vals):
            hits.append(tok)
    return hits


def _language_violations(answer):
    bad = []
    if re.search(r"\bwrong", answer, re.I):
        bad.append("uses the word 'wrong'")
    for line in answer.splitlines():
        if re.search(r"accura|\bf1\b|precision|recall", line, re.I):
            for m in re.finditer(r"(\d+(?:\.\d+)?)\s*%", line):
                if float(m.group(1)) > 95:
                    bad.append(f"metric line claims {m.group(0)}: {line.strip()[:80]}")
    return bad


def _check_offline(case, ans, via):
    r = {"question": case["question"], "via": via, "planner": ans["planner"],
         "tools_chosen": [c["tool"] for c in ans["tool_calls"]],
         "tool_calls": ans["tool_calls"], "failures": []}
    if ans["planner"] != "offline":
        r["failures"].append(f"planner is {ans['planner']!r}, expected 'offline'")
    if not ans.get("planner_note", "").startswith("Answered by KAVAL's offline"):
        r["failures"].append("planner_note missing or not the offline note")
    want = {t for t, _a in case["calls"]}
    missing = sorted(want - set(r["tools_chosen"]))
    if missing:
        r["failures"].append(f"did not call {missing}")
    if len(ans["citations"]) != len(ans["tool_calls"]):
        r["failures"].append("a tool call failed (citations != tool calls)")
    for call, cit in zip(ans["tool_calls"], ans["citations"]):
        if call["tool"] not in NON_METRIC_TOOLS and not cit.get("split_regime"):
            r["failures"].append(f"{call['tool']}: citation carries no split_regime")
        if not cit.get("source"):
            r["failures"].append(f"{call['tool']}: citation carries no source")
    payloads = [A.dispatch(c["tool"], dict(c["args"])) for c in ans["tool_calls"]]
    hits = _grounded_numbers(ans["answer"], payloads)
    r["grounded_numbers_sample"] = hits[:8]
    if not hits:
        r["failures"].append("no number in the answer matches a tool payload")
    r["language_violations"] = _language_violations(ans["answer"])
    r["failures"] += r["language_violations"]
    r["cited_parcel_ids"] = sum(len(c.get("parcel_ids") or []) for c in ans["citations"])
    r["answer_excerpt"] = ans["answer"].split("\n")[0][:220]
    r["passed"] = not r["failures"]
    return r


def _ungrounded_numbers(answer, payloads, question=""):
    """Numbers the answer states that no tool returned and the question did not
    contain: invented, or computed by the model (a difference, a unit conversion),
    which rule 1 of the system prompt forbids. Skips small integers."""
    grounded = set(_grounded_numbers(answer, payloads))
    grounded |= set(NUM.findall(question))
    out = []
    for tok in NUM.findall(answer):
        t = tok.replace(",", "")
        d = len(t.split(".")[1]) if "." in t else 0
        if tok in grounded or (d == 0 and abs(float(t)) < 10):
            continue
        out.append(tok)
    return out


def llm_section():
    """
    LLM PLANNING, measured: every brief and product question through whichever
    LLM the provider layer resolves (api/llm.py). Scored per question, so a
    partial result is visible as partial. This verifies planning BY THAT MODEL;
    a different model (Gemini, Claude) needs its own run.
    """
    import time
    from KAVAL.api import llm as LLM
    p = LLM.resolve()
    if p is None:
        return None
    rows = []
    tagged = [(c, "core") for c in BRIEF_QUERIES + PRODUCT_QUERIES] + \
             [(c, "extended") for c in EXTENDED_QUERIES]
    for c, kind in tagged:
        time.sleep(4)        # stay inside free-tier requests-per-minute
        t0 = time.time()
        try:
            a = A.analyst_query(A.Query(question=c["question"])).model_dump()
        except Exception as exc:                                    # noqa: BLE001
            rows.append({"question": c["question"], "passed": False,
                         "failures": [f"{type(exc).__name__}: {exc}"],
                         "seconds": round(time.time() - t0, 1)})
            continue
        r = {"question": c["question"], "seconds": round(time.time() - t0, 1),
             "planner": a["planner"], "provider": a.get("provider"),
             "tools_chosen": [t["tool"] for t in a["tool_calls"]],
             "tool_calls": a["tool_calls"], "failures": [], "warnings": []}
        r["set"] = kind
        if a["planner"] != "llm":
            note = a.get("planner_note", "")
            if "429" in note or "quota" in note.lower():
                # The provider refused for quota: planning was never tested. Not a
                # pass and not a planning failure; reported on its own.
                r["not_run"] = "provider quota exhausted (HTTP 429)"
                rows.append(r)
                print(f"  [SKIP] quota  {c['question'][:56]}", flush=True)
                continue
            r["failures"].append("fell back to the offline planner: " + note[:160])
        want = {t for t, _ in c["calls"]}
        got = set(r["tools_chosen"])
        r["tools_expected"] = sorted(want)
        r["tool_selection"] = ("all" if want <= got else "some" if want & got else "none")
        if r["tool_selection"] == "none":
            r["failures"].append(f"called none of the expected tools {sorted(want)}")
        elif r["tool_selection"] == "some":
            r["warnings"].append(f"missed {sorted(want - got)}")
        for call, cit in zip(a["tool_calls"], a["citations"]):
            if call["tool"] not in NON_METRIC_TOOLS and not cit.get("split_regime"):
                r["failures"].append(f"{call['tool']}: citation carries no split_regime")
        payloads = []
        for t in a["tool_calls"]:
            try:
                payloads.append(A.dispatch(t["tool"], dict(t["args"])))
            except Exception:                                       # noqa: BLE001
                pass
        r["grounded_numbers"] = _grounded_numbers(a["answer"], payloads)[:10]
        r["ungrounded_numbers"] = _ungrounded_numbers(a["answer"], payloads,
                                                      c["question"])[:10]
        if not r["grounded_numbers"]:
            r["failures"].append("no number in the answer matches a tool payload")
        if r["ungrounded_numbers"]:
            r["warnings"].append(f"numbers not found in any tool result: "
                                 f"{r['ungrounded_numbers'][:5]}")
        viol = _language_violations(a["answer"])
        r["language_violations"] = viol
        r["warnings"] += viol
        if re.search(r"(cannot|can't|unable to|do not have|don't have)[^.]{0,60}"
                     r"(export|download)", a["answer"], re.I):
            r["failures"].append("refused a capability the tools provide (export)")
        r["names_split_regime_in_text"] = bool(re.search(
            r"3-event|capture[- ]event|split regime|regime 3", a["answer"], re.I))
        r["answer"] = a["answer"]
        r["passed"] = not r["failures"]
        rows.append(r)
        print(f"  [{'PASS' if r['passed'] else 'FAIL'}] {r['seconds']:>6.1f}s "
              f"{c['question'][:56]:<56} -> {', '.join(r.get('tools_chosen', []))}",
              flush=True)
    skipped = [r for r in rows if r.get("not_run")]
    scored = [r for r in rows if not r.get("not_run")]
    core = [r for r in scored if r.get("set") == "core"]
    ext = [r for r in scored if r.get("set") == "extended"]
    rows_all, rows = rows, core
    n = len(core)
    answered = {}
    for r in rows:
        k = r.get("provider") or "none"
        answered[k] = answered.get(k, 0) + 1
    return {
        # Keyed by provider, not the chain head: the fallback may answer from any
        # model in the chain, and `answered_by` records which actually did.
        "provider": f"{p.name} (chain: {' -> '.join(c.model for c in LLM.candidates() if c.name == p.name)})",
        "answered_by": answered,
        "scope": "planning by THIS model only; not evidence about any other model",
        "questions": rows_all,
        "total": n, "core_total": len(BRIEF_QUERIES) + len(PRODUCT_QUERIES),
        "passing": sum(r["passed"] for r in core),
        "not_run_quota": len(skipped),
        "extended_passing": sum(r["passed"] for r in ext), "extended_total": len(ext),
        "tool_selection_all": sum(r.get("tool_selection") == "all" for r in rows),
        "with_ungrounded_numbers": sum(bool(r.get("ungrounded_numbers")) for r in rows),
        "with_language_violations": sum(bool(r.get("language_violations")) for r in rows),
        "naming_regime_in_text": sum(bool(r.get("names_split_regime_in_text")) for r in rows),
        "median_seconds": sorted(r["seconds"] for r in rows)[n // 2] if n else None,
    }


def offline_section():
    from fastapi.testclient import TestClient
    from KAVAL.api import main as M

    keys = ("ANTHROPIC_API_KEY", "KAVAL_ANALYST_PLANNER", "KAVAL_LLM_PROVIDER")
    saved = {k: os.environ.pop(k, None) for k in keys}
    # Pin the offline planner explicitly. "No Anthropic key" used to imply offline;
    # the provider layer now also auto-detects free-tier keys and a local model,
    # which once sent this section's nine questions to a CPU-hosted LLM.
    os.environ["KAVAL_LLM_PROVIDER"] = "offline"
    try:
        client = TestClient(M.app)
        cases = BRIEF_QUERIES + PRODUCT_QUERIES
        res = {"extended": [_check_offline(c, A.offline_answer(c["question"]).model_dump(),
                                           "function") for c in EXTENDED_QUERIES],
               "mode_with_key_unset": A.planner_mode(),
               "tools_endpoint_planner": client.get("/analyst/tools").json().get("planner"),
               "function": [], "http": []}
        for c in cases:
            res["function"].append(_check_offline(
                c, A.offline_answer(c["question"]).model_dump(), "function"))
            resp = client.post("/analyst/query", json={"question": c["question"]})
            if resp.status_code != 200:
                res["http"].append({"question": c["question"], "via": "http",
                                    "passed": False,
                                    "failures": [f"HTTP {resp.status_code}: {resp.text[:200]}"]})
            else:
                res["http"].append(_check_offline(c, resp.json(), "http"))

        # A question no intent covers: no tool calls, an honest refusal.
        resp = client.post("/analyst/query", json={"question": NONSENSE})
        body = resp.json() if resp.status_code == 200 else {}
        res["nonsense"] = {
            "question": NONSENSE, "status_code": resp.status_code,
            "planner": body.get("planner"), "tool_calls": body.get("tool_calls"),
            "answer_excerpt": (body.get("answer") or "")[:160],
            "passed": (resp.status_code == 200 and body.get("planner") == "offline"
                       and body.get("tool_calls") == [] and body.get("citations") == []
                       and "GEMINI_API_KEY" in body.get("answer", ""))}

        # The override: a key is present, but KAVAL_ANALYST_PLANNER=offline wins.
        # (A dummy key; no network call is made because the LLM path is never taken.)
        os.environ.pop("KAVAL_LLM_PROVIDER", None)
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test-dummy"
        os.environ["KAVAL_ANALYST_PLANNER"] = "offline"
        resp = client.post("/analyst/query", json={"question": cases[0]["question"]})
        res["override"] = {"env": "KAVAL_ANALYST_PLANNER=offline with a key set",
                           "planner": resp.json().get("planner") if resp.status_code == 200 else None,
                           "tools_endpoint_planner": client.get("/analyst/tools")
                           .json().get("planner"),
                           "passed": resp.status_code == 200 and resp.json().get("planner") == "offline"}
    finally:
        for k in keys:
            os.environ.pop(k, None)
            if saved[k] is not None:
                os.environ[k] = saved[k]

    allr = res["function"] + res["http"]
    res["function_passing"] = sum(r["passed"] for r in res["function"])
    res["http_passing"] = sum(r["passed"] for r in res["http"])
    res["total"] = len(res["function"])
    res["passes"] = (all(r["passed"] for r in allr) and res["nonsense"]["passed"]
                     and res["override"]["passed"]
                     and res["mode_with_key_unset"] == "offline"
                     and res["tools_endpoint_planner"] == "offline")
    res["what_this_shows"] = (
        "With no ANTHROPIC_API_KEY, /analyst/query answers all nine questions through the "
        "offline rule-based planner: keyword routing to the same typed tools, answers "
        "composed only from tool payloads, every metric-bearing citation carrying its split "
        "regime. It does NOT show that an LLM plans correctly over the tools.")
    return res


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true",
                    help="also run all nine questions through the active LLM provider "
                         "(slow on a CPU-hosted model). Results are kept per provider.")
    args = ap.parse_args()
    out_path = EVIDENCE / "p7_analyst_verification.json"
    prev = json.loads(out_path.read_text()) if out_path.exists() else {}
    ev = {
        "gate": "plan.md §6 Phase 7 — all six brief queries answered end-to-end, "
                "each traceable to tool calls",
        "headline_regime": HEADLINE_REGIME,
        "tools_available": [t["name"] for t in A.TOOLS],
        "verifies": "the TOOL LAYER; the offline keyword planner; and, per provider in "
                    "llm_planner, LLM planning by that specific model",
        "does_not_verify": (
            "Planning by any model not listed under llm_planner. In particular the "
            "project's intended model (Claude, ANTHROPIC_API_KEY) is not verified here; "
            "a small local open-weight model passing does not imply a frontier model "
            "would behave the same, or vice versa. The offline_planner section is "
            "keyword routing, not LLM planning."),
    }

    brief = [check(c) for c in BRIEF_QUERIES]
    product = [check(c) for c in PRODUCT_QUERIES]
    ev["extended_queries"] = [check(c) for c in EXTENDED_QUERIES]
    ev["brief_queries"] = brief
    ev["product_queries"] = product
    ev["brief_queries_passing"] = sum(r["passed"] for r in brief)
    ev["brief_queries_total"] = len(brief)
    ev["product_queries_passing"] = sum(r["passed"] for r in product)
    ev["all_tools_exercised"] = sorted(
        {c["tool"] for r in brief + product + ev["extended_queries"]
         for c in r["tool_calls"]})
    ev["tools_never_exercised"] = sorted(
        set(ev["tools_available"]) - set(ev["all_tools_exercised"]))
    ev["tool_layer_gate_passes"] = all(r["passed"] for r in brief + product)
    ev["offline_planner"] = offline_section()
    ev["llm_planner"] = dict(prev.get("llm_planner") or {})
    if args.llm:
        print("\nLLM planner (this takes a while on a CPU-hosted model):", flush=True)
        res = llm_section()
        if res is None:
            print("  no LLM provider available — nothing to run")
        else:
            name = res["provider"].split(" ")[0]
            # One entry per provider: drop earlier runs of it, including the old
            # "gemini:<model>" keys that named the chain head, not who answered.
            for k in [k for k in ev["llm_planner"] if k.split(" ")[0].split(":")[0] == name]:
                del ev["llm_planner"][k]
            ev["llm_planner"][res["provider"]] = res

    out_path.write_text(json.dumps(ev, indent=2, default=str))

    print(f"brief queries : {ev['brief_queries_passing']}/{ev['brief_queries_total']} pass")
    print(f"product queries: {ev['product_queries_passing']}/{len(product)} pass")
    print(f"tools exercised: {len(ev['all_tools_exercised'])}/{len(ev['tools_available'])}")
    if ev["tools_never_exercised"]:
        print(f"NOT exercised  : {ev['tools_never_exercised']}")
    for r in brief + product:
        mark = "PASS" if r["passed"] else "FAIL"
        print(f"  [{mark}] {r['question'][:72]}")
        for f in r["failures"]:
            print(f"         ! {f}")
    op = ev["offline_planner"]
    print(f"\noffline planner (function): {op['function_passing']}/{op['total']} pass")
    print(f"offline planner (HTTP POST): {op['http_passing']}/{op['total']} pass")
    for r in op["function"]:
        mark = "PASS" if r["passed"] else "FAIL"
        print(f"  [{mark}] {r['question'][:60]:<60} -> {', '.join(r.get('tools_chosen', []))}")
        for f in r["failures"]:
            print(f"         ! {f}")
    for r in op["http"]:
        for f in r["failures"]:
            print(f"  [HTTP FAIL] {r['question'][:50]}: {f}")
    print(f"  [{'PASS' if op['nonsense']['passed'] else 'FAIL'}] nonsense question -> "
          f"{len(op['nonsense']['tool_calls'] or [])} tool calls")
    print(f"  [{'PASS' if op['override']['passed'] else 'FAIL'}] KAVAL_ANALYST_PLANNER=offline "
          "overrides a set key")

    print(f"\nTOOL LAYER GATE     : {'PASS' if ev['tool_layer_gate_passes'] else 'FAIL'}")
    print(f"OFFLINE PLANNER     : {'PASS' if op['passes'] else 'FAIL'} (keyword routing, not LLM)")
    if not ev["llm_planner"]:
        print("LLM PLANNING        : UNVERIFIED (no LLM run recorded; use --llm)")
    ext = ev["extended_queries"]
    print(f"EXTENDED (tools)    : {sum(r['passed'] for r in ext)}/{len(ext)} tool layer, "
          f"{sum(r['passed'] for r in op['extended'])}/{len(op['extended'])} offline planner")
    for label, res in ev["llm_planner"].items():
        print(f"LLM PLANNING        : {label}: {res['passing']}/{res['total']} core pass"
              f" (+{res.get('not_run_quota', 0)} not run: quota), extended "
              f"{res.get('extended_passing')}/{res.get('extended_total')}, "
              f"all expected tools {res['tool_selection_all']}/{res['total']}, "
              f"ungrounded numbers in {res['with_ungrounded_numbers']}, "
              f"language issues in {res['with_language_violations']}, "
              f"median {res['median_seconds']}s")


if __name__ == "__main__":
    main()
