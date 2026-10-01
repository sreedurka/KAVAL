"""
KAVAL API — behavioural tests for every route.

Not "does it return 200": each test checks the route does what the product claims,
against the evidence files the documents quote. Run from the project root:

    .venv/bin/python -m pytest KAVAL/tests -q
"""

import csv
import io
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "KAVAL"))
os.environ["KAVAL_LLM_PROVIDER"] = "offline"   # analyst tests must not need a model

from fastapi.testclient import TestClient  # noqa: E402

from KAVAL.api.main import app  # noqa: E402
from kaval.config import EVIDENCE, HEADLINE_REGIME  # noqa: E402

C = TestClient(app)
P4 = json.loads((EVIDENCE / "p4_results.json").read_text())
P6 = json.loads((EVIDENCE / "p6_audit.json").read_text())
STATUSES = ["CONFIRMED", "DISPUTED", "UNCERTAIN", "UNVERIFIABLE", "UNSEEN"]
N_AUDITED = sum(P6["agreement_status_counts"].values())


def get(path, **params):
    r = C.get(path, params=params)
    assert r.status_code == 200, f"{path} {params} -> {r.status_code} {r.text[:200]}"
    return r.json() if "json" in r.headers.get("content-type", "") else r


# ------------------------------------------------------------ contract ----
METRIC_ROUTES = ["/parcels", "/summary/crop-area", "/summary/registry-delta",
                 "/audit/worklist", "/audit/auto-clear", "/audit/status-summary",
                 "/validation/ladder", "/validation/confusion",
                 "/validation/calibration", "/geo/parcels"]


@pytest.mark.parametrize("path", METRIC_ROUTES)
def test_every_metric_route_names_its_split_regime(path):
    j = get(path)
    assert j["meta"]["split_regime"], f"{path} served a metric without a regime"
    assert j["meta"]["sources"], f"{path} has no sources to cite"


def test_openapi_lists_every_route():
    paths = C.get("/openapi.json").json()["paths"]
    for p in METRIC_ROUTES + ["/health", "/export", "/evidence/forensics",
                              "/geo/villages", "/analyst/tools", "/analyst/query",
                              "/parcels/{parcel_id}"]:
        assert p in paths, p


def test_health():
    assert get("/health")


# ------------------------------------------------------------- parcels ----
def test_parcels_filter_by_status_returns_only_that_status():
    for s in ("DISPUTED", "CONFIRMED"):
        rows = get("/parcels", status=s, limit=500)["data"]
        assert rows and {r["agreement_status"] for r in rows} == {s}


def test_parcels_confidence_range_is_respected():
    rows = get("/parcels", max_confidence=0.5, limit=1000)["data"]
    assert rows and max(r["confidence_calibrated"] for r in rows) <= 0.5


def test_parcels_paging_is_disjoint():
    a = {r["parcel_id"] for r in get("/parcels", limit=50, offset=0)["data"]}
    b = {r["parcel_id"] for r in get("/parcels", limit=50, offset=50)["data"]}
    assert len(a) == len(b) == 50 and not a & b


def test_parcel_detail_and_404():
    pid = get("/parcels", limit=1)["data"][0]["parcel_id"]
    d = get(f"/parcels/{pid}")
    assert json.dumps(d).count(pid) >= 1
    assert C.get("/parcels/NO_SUCH_PARCEL").status_code == 404


def test_thresholds_move_statuses_server_side():
    lo = get("/audit/status-summary", confidence_high=0.5)
    hi = get("/audit/status-summary", confidence_high=0.99)
    count = lambda j, s: sum(r.get("parcels", r.get("n", 0)) for r in j["data"]  # noqa: E731
                             if r.get("agreement_status") == s)
    assert count(lo, "CONFIRMED") > count(hi, "CONFIRMED")


# ------------------------------------------------------------- summary ----
def test_status_summary_matches_evidence():
    j = get("/audit/status-summary")
    got = {r["agreement_status"]: r.get("parcels", r.get("n")) for r in j["data"]}
    for s, n in P6["agreement_status_counts"].items():
        assert got.get(s) == n, (s, got.get(s), n)


@pytest.mark.parametrize("group_by", ["village", "taluk"])
@pytest.mark.parametrize("source", ["predicted", "declared"])
def test_crop_area_totals_are_the_audited_area(group_by, source):
    j = get("/summary/crop-area", group_by=group_by, source=source)
    total = sum(r["area_ha"] for r in j["data"])
    audited = sum(P6["agreement_status_area_ha"].values())
    assert abs(total - audited) < 0.5, (total, audited)
    assert all("conflicted_area_ha" in r for r in j["data"])
    assert sum(r["parcels"] for r in j["data"]) == N_AUDITED


def test_registry_delta_carries_the_independence_caveat():
    j = get("/summary/registry-delta")
    assert j["data"]
    assert "area_rule" in json.dumps(j) or j["meta"].get("notes")


# --------------------------------------------------------------- audit ----
@pytest.mark.parametrize("budget", [1, 50, 500])
def test_worklist_is_budget_long_and_ranked(budget):
    j = get("/audit/worklist", budget=budget)
    wl = j["data"]["worklist"]
    assert len(wl) == budget == j["data"]["economics"]["budget"]
    pr = [r["priority"] for r in wl]
    assert pr == sorted(pr, reverse=True)


def test_worklist_targeting_efficiency_never_exceeds_its_cap():
    e = get("/audit/worklist", budget=500)["data"]["economics"]
    assert e["targeting_efficiency"] <= 1 / e["base_disagreement_rate"] + 1e-9


def test_worklist_rejects_nonsense_budget():
    assert C.get("/audit/worklist", params={"budget": 0}).status_code == 422


def test_auto_clear_is_the_confirmed_set():
    j = get("/audit/auto-clear")
    txt = json.dumps(j["data"])
    assert str(P6["agreement_status_counts"]["CONFIRMED"]) in txt


# ------------------------------------------------------------ validation --
def test_ladder_matches_evidence_and_never_claims_95():
    j = get("/validation/ladder")["data"]
    got = {r["regime"]: r["accuracy"] for r in j["ladder"]}
    for r in P4["ladder"]:
        assert abs(got[r["regime"]] - r["accuracy"]) < 1e-9
    assert all(r["accuracy"] < 0.95 for r in j["ladder"] if r["regime"] != "1-random")
    assert j["headline"]["regime"] == HEADLINE_REGIME
    assert any(s["source"].startswith("Presto") for s in j["sources"])
    assert any(c["underpowered"] for c in j["source_comparisons"])


def test_confusion_requires_a_known_regime():
    j = get("/validation/confusion", regime=HEADLINE_REGIME)
    assert j["meta"]["split_regime"] == HEADLINE_REGIME
    assert C.get("/validation/confusion", params={"regime": "bogus"}).status_code >= 400


def test_calibration_matches_evidence():
    j = get("/validation/calibration")
    txt = json.dumps(j)
    assert f"{P6['calibration']['ece_calibrated']:.4f}"[:5] in txt


def test_forensics():
    assert "3204" in json.dumps(get("/evidence/forensics")).replace(",", "")


# -------------------------------------------------------------- export ----
def test_export_csv_is_the_whole_audited_layer():
    r = get("/export")
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert len(rows) == N_AUDITED


def test_export_with_budget_reproduces_the_worklist():
    wl = [str(r["parcel_id"]) for r in get("/audit/worklist", budget=120)["data"]["worklist"]]
    rows = list(csv.DictReader(io.StringIO(get("/export", budget=120).text)))
    assert [r["parcel_id"] for r in rows] == wl
    assert [int(r["rank"]) for r in rows] == list(range(1, 121))


def test_export_geojson():
    r = C.get("/export", params={"fmt": "geojson", "budget": 25})
    assert r.status_code == 200 and len(r.json()["features"]) == 25


# ----------------------------------------------------------------- geo ----
def test_geo_villages_are_the_25_supplied_polygons():
    j = get("/geo/villages")
    feats = j["features"] if "features" in j else j["data"]["features"]
    assert len(feats) == 25


def test_geo_parcels_are_polygons_with_status():
    j = get("/geo/parcels", limit=200)
    feats = j["data"]["features"] if "data" in j else j["features"]
    assert feats and all(f["properties"]["agreement_status"] in STATUSES for f in feats)


# ------------------------------------------------------------- analyst ----
def test_analyst_tools_report_the_active_planner():
    j = get("/analyst/tools")
    assert j["planner"] == "offline" and len(j["tools"]) == 12


def test_analyst_offline_answer_is_labelled_and_cited():
    r = C.post("/analyst/query", json={"question": "Where should we send 200 surveyors?"})
    assert r.status_code == 200
    a = r.json()
    assert a["planner"] == "offline" and a["provider"] is None
    assert [t["tool"] for t in a["tool_calls"]] == ["route_verification_budget"]
    assert a["citations"][0]["split_regime"] == HEADLINE_REGIME
    assert "wrong" not in a["answer"].lower()


def test_analyst_rejects_oversized_question():
    assert C.post("/analyst/query", json={"question": "x" * 5000}).status_code == 422
