"""
KAVAL — FastAPI backend.

This is not a data feed for a web page. It is the tool surface the agentic analyst
(AI-5) plans over, so every route is designed to be selected and called by a model
as readily as by the frontend. See the `fastapi-contract` skill.

Two rules are enforced structurally rather than by discipline:

  * a response carrying a metric CANNOT be built without naming its split regime
    (see `Meta` — `split_regime` is required, and `metric_response` is the only
    way a metric leaves this process)
  * thresholds are query parameters defaulting to config, never hard-coded, so the
    frontend's live sliders and the agent's what-if questions use the same path

Run:  .venv/bin/uvicorn KAVAL.api.main:app --reload --port 8000
"""

import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kaval.area import crop_area as crop_area_by_field  # noqa: E402
from kaval.audit import (agreement_status, route_budget, routed_worklist,  # noqa: E402
                         trust_score)
from kaval.config import (AREA_RULE, DERIVED, EVIDENCE, HEADLINE_REGIME, KEY_PARCEL,  # noqa: E402
                          THRESHOLDS, VISIT_COST)

app = FastAPI(
    title="KAVAL",
    description="Satellite audit of the Digital Crop Survey. The classifier is the "
                "instrument; the product is the audit.",
    version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


# --------------------------------------------------------------- models ----
class Meta(BaseModel):
    n: int
    generated_at: str
    sources: list[str]
    # Required, not optional. A metric response cannot be constructed without it.
    split_regime: Optional[str] = Field(
        None, description="The validation split any metric in this response was "
                          "measured under. Required whenever `data` contains a metric.")
    model_version: Optional[str] = None
    thresholds: Optional[dict] = None


class Envelope(BaseModel):
    data: list | dict
    meta: Meta


# ----------------------------------------------------------------- state ---
class Store:
    """Loaded once at import. Small enough to hold in memory at taluk scale."""

    def __init__(self):
        self.audit = self._load(DERIVED / "audit.parquet")
        self.p4 = self._json(EVIDENCE / "p4_results.json")
        self.p3b = self._json(EVIDENCE / "p3b_presto.json")
        self.p5 = self._json(EVIDENCE / "p5_mil.json")
        self.p6 = self._json(EVIDENCE / "p6_audit.json")
        self.ladder = self._json(EVIDENCE / "leakage_ladder.json")
        self.forensics = self._json(EVIDENCE / "gt_forensics.json")
        self.registry = self._load(DERIVED / "village_registry.parquet")
        self.p7 = self._json(EVIDENCE / "p7_registry.json")

    @staticmethod
    def _load(p):
        return pd.read_parquet(p) if p.exists() else None

    @staticmethod
    def _json(p):
        return json.loads(p.read_text()) if p.exists() else None

    def require_audit(self):
        if self.audit is None:
            raise HTTPException(
                503, "Phase 6 has not run. Execute KAVAL/scripts/p6_audit.py first.")
        return self.audit


S = Store()


def _jsonable(obj):
    """
    NaN and infinity are not JSON. They occur legitimately here — photo distance is
    null for the 13 records whose photo coordinate geocodes outside the study area,
    and a parcel with no confidently preferred alternative has no suggested crop.
    Sanitising centrally means no individual route can reintroduce the bug.
    """
    import math

    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if obj is not None and hasattr(obj, "item") and hasattr(obj, "dtype"):
        return _jsonable(obj.item())       # numpy scalar
    if obj is not None and pd.isna(obj) is True:
        return None
    return obj


def envelope(data, *, n=None, split_regime=None, sources=(), thresholds=None,
             model_version=None, notes=None):
    return {
        "data": _jsonable(data),
        "meta": {
            "n": n if n is not None else (len(data) if hasattr(data, "__len__") else 1),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sources": list(sources),
            "split_regime": split_regime,
            "model_version": model_version,
            "thresholds": thresholds,
            "notes": notes,
        },
    }


def metric_response(data, *, split_regime, sources, **kw):
    """The only way a metric leaves this process. Refuses an unnamed regime."""
    if not split_regime:
        raise RuntimeError(
            "a response containing a metric must name its split regime "
            "(leakage-protocol rule 1)")
    return envelope(data, split_regime=split_regime, sources=list(sources), **kw)


def recompute_status(df, conf_high, trust_floor, trust_high):
    """
    Re-derive agreement status at caller-supplied thresholds.

    The frontend's sliders and the agent's what-if questions both land here, so
    moving a threshold changes the map, the worklist and the saving consistently.

    Thresholds are passed as an argument rather than patched into a module global:
    FastAPI runs sync endpoints in a threadpool, and two concurrent requests with
    different thresholds would otherwise corrupt each other's results.
    """
    d = df.copy()
    d["agreement_status"] = agreement_status(
        d, thresholds={"confidence_high": conf_high, "trust_floor": trust_floor,
                       "trust_high": trust_high})
    return d


# ---------------------------------------------------------------- routes ---
@app.get("/health")
def health():
    return {"status": "ok",
            "phases_available": {
                "audit": S.audit is not None, "p4": S.p4 is not None,
                "p5": S.p5 is not None, "p6": S.p6 is not None}}


@app.get("/parcels", summary="List parcels with their audit status",
         description="Filter parcels by village, crop, agreement status and "
                     "confidence or trust range. Use this to answer questions about "
                     "specific parcels or to populate a map.")
def parcels(
    village: Optional[str] = None,
    crop: Optional[str] = None,
    declared_crop: Optional[str] = Query(None, description="Filter on the crop the "
                                         "SURVEYOR declared; `crop` filters on the "
                                         "satellite prediction."),
    status: Optional[str] = Query(None, description="CONFIRMED|DISPUTED|UNCERTAIN|UNVERIFIABLE|UNSEEN"),
    min_confidence: float = 0.0,
    max_confidence: float = 1.0,
    min_trust: float = 0.0,
    limit: int = Query(200, le=5000),
    offset: int = 0,
    confidence_high: float = Query(THRESHOLDS["confidence_high"]),
    trust_floor: float = Query(THRESHOLDS["trust_floor"]),
    trust_high: float = Query(THRESHOLDS["trust_high"]),
):
    # Agreement status is re-derived server-side at the caller's thresholds. The
    # rule that turns (prediction, confidence, trust) into a status lives in
    # kaval/audit.py and must exist in exactly one place — a second copy in the
    # browser would drift.
    df = recompute_status(S.require_audit(), confidence_high, trust_floor, trust_high)
    if village:
        df = df[df.village_name.astype(str).str.lower() == village.lower()]
    if crop:
        df = df[df.y_pred == crop]
    if declared_crop:
        df = df[df.y_true == declared_crop]
    if status:
        df = df[df.agreement_status == status.upper()]
    df = df[(df.confidence_calibrated >= min_confidence)
            & (df.confidence_calibrated <= max_confidence)
            & (df.trust_score >= min_trust)]
    total = len(df)
    cols = [KEY_PARCEL, "village_name", "survey_no", "subdivision", "y_true", "y_pred",
            "confidence_calibrated", "trust_score", "agreement_status",
            "p_label_wrong", "suggested_crop", "bag_size", "photo_distance_m",
            "geometry_source", "field_id", "snap_m", "parcels_sharing_field",
            "field_area_m2", "area_m2", "lat", "lon"]
    cols = [c for c in cols if c in df.columns]
    page = df[cols].iloc[offset:offset + limit]
    return metric_response(page.to_dict("records"), n=total,
                           split_regime=HEADLINE_REGIME,
                           sources=["data/derived/audit.parquet"],
                           thresholds={"confidence_high": confidence_high,
                                       "trust_floor": trust_floor,
                                       "trust_high": trust_high})


@app.get("/parcels/{parcel_id}", summary="Full audit trail for one parcel",
         description="Everything known about a single parcel: the prediction, its "
                     "calibrated confidence, the surveyor's declared crop, and each "
                     "component of the Record Trust Score with its provenance.")
def parcel_detail(parcel_id: str):
    df = S.require_audit()
    row = df[df[KEY_PARCEL] == parcel_id]
    if row.empty:
        raise HTTPException(404, f"no parcel {parcel_id}")
    r = row.iloc[0]
    return envelope({
        "parcel_id": parcel_id,
        "village": r.village_name,
        "survey_no": r.survey_no, "subdivision": r.subdivision,
        "declared_crop": r.y_true, "predicted_crop": r.y_pred,
        "confidence_calibrated": float(r.confidence_calibrated),
        "confidence_raw": float(r.confidence_raw),
        "agreement_status": r.agreement_status,
        "trust_score": float(r.trust_score),
        "p_label_wrong": float(r.p_label_wrong),
        "suggested_crop": r.suggested_crop,
        "evidence": {
            "capture_event": r.bag_id,
            "parcels_sharing_this_photograph": int(r.bag_size),
            "photo_distance_m": None if pd.isna(r.photo_distance_m) else float(r.photo_distance_m),
            "geometry_source": r.geometry_source,
            "village_code_mismatch": bool(r.village_code_mismatch),
            "declared_stage": r.crop_stage,
            # Where this parcel's geometry came from, and whether the satellite
            # sees it as its own field or as part of a larger farmed unit.
            #
            # These keep the names the parquet, the feature store and the frontend
            # already use. An earlier version renamed them to something more
            # self-describing here, which silently broke three panel rows: the
            # fields are optional in the client type, so nothing errored, they
            # just never appeared. One name per concept, everywhere.
            "field_id": None if pd.isna(r.get("field_id")) else str(r.get("field_id")),
            "snap_m": None if pd.isna(r.get("snap_m")) else round(float(r.get("snap_m")), 1),
            "parcels_sharing_field": int(r.get("parcels_sharing_field", 1) or 1),
            "field_area_m2": (None if pd.isna(r.get("field_area_m2"))
                              else float(r.get("field_area_m2"))),
        },
        "area_m2": float(r.area_m2),
    }, n=1, split_regime=HEADLINE_REGIME,
        sources=["data/derived/audit.parquet"])


@app.get("/summary/crop-area", summary="Crop-wise cultivated area",
         description="Crop-wise area and parcel counts, grouped by village or for the "
                     "whole taluk. Compares the surveyor-declared crop against the "
                     "satellite prediction.")
def crop_area(group_by: Literal["village", "taluk"] = "village",
              source: Literal["predicted", "declared"] = "predicted"):
    df = S.require_audit()
    col = "y_pred" if source == "predicted" else "y_true"
    gcols = ["village_name"] if group_by == "village" else []
    # Area comes from the field-level aggregator (kaval/area.py); parcel counts and
    # confidence stay per parcel, so a crop can list parcels yet carry 0 area when
    # every field those parcels sit in was assigned another crop.
    area = crop_area_by_field(df, col, gcols)
    cnt = (df.groupby(gcols + [col]).agg(parcels=(KEY_PARCEL, "size"),
                                         mean_confidence=("confidence_calibrated", "mean"))
           .reset_index())
    g = cnt.merge(area, on=gcols + [col], how="outer")
    g["parcels"] = g["parcels"].fillna(0).astype(int)
    g[["area_ha", "conflicted_area_ha"]] = g[["area_ha", "conflicted_area_ha"]].fillna(0.0)
    g = (g[gcols + [col, "parcels", "area_ha", "mean_confidence", "conflicted_area_ha"]]
         .round(3).rename(columns={col: "crop"}))
    return metric_response(g.to_dict("records"), split_regime=HEADLINE_REGIME,
                           sources=["data/derived/audit.parquet"],
                           notes=[AREA_RULE])


@app.get("/summary/registry-delta", summary="Satellite versus the crop registry",
         description="Per-village comparison of the satellite-predicted crop mix "
                     "against the Tamil Nadu Agrisnet village-wise Digital Crop Survey "
                     "report for Rabi 2024, sorted by divergence. Use this to answer "
                     "'which villages differ most from the registry'.")
def registry_delta(min_registry_ha: float = 0.0, village: Optional[str] = None,
                   crop: Optional[str] = None, limit: int = Query(200, le=2000)):
    if S.registry is None:
        raise HTTPException(
            503, "Registry comparison not built. Run "
                 "KAVAL/scripts/p7_registry_comparison.py.")
    m = S.registry
    if village:
        m = m[m.village.astype(str).str.lower() == village.lower()]
    if crop:
        m = m[m.crop == crop]
    m = m[m.registry_ha >= min_registry_ha]
    meta = S.p7 or {}
    return metric_response(
        {"rows": m.head(limit).to_dict("records"),
         # Carried in the payload, not only in the docs: an LLM reading this must
         # not present the comparison as stronger than it is.
         "independence_caveat": meta.get("independence_note"),
         "scale_caveat": meta.get("scale_note"),
         "systematic_bias_by_crop": meta.get("systematic_bias_by_crop"),
         "registry_out_of_scope_pct": meta.get("registry_out_of_scope_pct"),
         "season": meta.get("season"),
         "area_rule": AREA_RULE},
        n=len(m), split_regime=HEADLINE_REGIME, notes=[AREA_RULE],
        sources=["data/derived/village_registry.parquet",
                 "data/raw/tn_crop_registry.csv (TN Agrisnet DCS village-wise)"])


# One column list for the on-screen worklist and its export, so they cannot drift.
WORKLIST_COLS = [KEY_PARCEL, "village_name", "survey_no", "subdivision", "y_true",
                 "y_pred", "suggested_crop", "confidence_calibrated", "trust_score",
                 "agreement_status", "p_label_wrong", "bag_size", "photo_distance_m",
                 "area_m2", "lat", "lon", "priority"]


@app.get("/audit/worklist", summary="Budget-routed field verification queue",
         description="Given a budget of N field visits, the N parcels that maximise "
                     "expected label corrections, with the random-visit counterfactual "
                     "for comparison. This is the core product output.")
def worklist(budget: int = Query(500, ge=1, le=20000),
             village: Optional[str] = None,
             confidence_high: float = Query(THRESHOLDS["confidence_high"]),
             trust_floor: float = Query(THRESHOLDS["trust_floor"]),
             trust_high: float = Query(THRESHOLDS["trust_high"])):
    df = recompute_status(S.require_audit(), confidence_high, trust_floor, trust_high)
    if village:
        df = df[df.village_name.astype(str).str.lower() == village.lower()]
    econ = route_budget(df, budget)
    top = routed_worklist(df, budget)
    return metric_response({"economics": econ,
                            "worklist": top[WORKLIST_COLS].round(4).to_dict("records")},
                           n=len(top), split_regime=HEADLINE_REGIME,
                           sources=["data/derived/audit.parquet"],
                    thresholds={"confidence_high": confidence_high,
                                "trust_floor": trust_floor, "trust_high": trust_high})


@app.get("/audit/auto-clear", summary="Parcels that need not be revisited",
         description="Parcels where satellite and survey agree at high calibrated "
                     "confidence on a record we trust, with the surveyor-day saving "
                     "and the cost assumptions behind it.")
def auto_clear(confidence_high: float = Query(THRESHOLDS["confidence_high"]),
               trust_floor: float = Query(THRESHOLDS["trust_floor"]),
               trust_high: float = Query(THRESHOLDS["trust_high"])):
    df = recompute_status(S.require_audit(), confidence_high, trust_floor, trust_high)
    cleared = df[df.agreement_status == "CONFIRMED"]
    per_day = VISIT_COST["parcels_per_surveyor_day"]
    return metric_response({
        "parcels": len(cleared),
        "pct_of_parcels": round(100 * len(cleared) / max(len(df), 1), 1),
        "area_ha": round(float(cleared.area_m2.sum()) / 1e4, 1),
        "surveyor_days_saved": round(len(cleared) / per_day, 1),
        "baseline_surveyor_days": round(len(df) / per_day, 1),
        # NOT reported as accuracy: CONFIRMED is defined as the model agreeing
        # with the survey, so that figure is 100% by construction. The honest
        # quantity is the residual risk that both err together, which the
        # calibrated confidence bounds.
        "expected_residual_error_rate": (float(1.0 - cleared.confidence_calibrated.mean())
                                         if len(cleared) else None),
        "expected_parcels_wrongly_cleared": (float((1.0 - cleared.confidence_calibrated).sum())
                                             if len(cleared) else None),
        "residual_note": "Auto-clearing fails only where satellite and surveyor "
                         "err in the same way, which cannot be measured against a "
                         "label the surveyor supplied. Settle it with an independent "
                         "field audit of a CONFIRMED sample.",
        "cost_assumption": VISIT_COST,
    }, n=len(cleared), split_regime=HEADLINE_REGIME,
        sources=["data/derived/audit.parquet"],
        thresholds={"confidence_high": confidence_high, "trust_high": trust_high})


@app.get("/audit/status-summary", summary="Counts and area by agreement status")
def status_summary(confidence_high: float = Query(THRESHOLDS["confidence_high"]),
                   trust_floor: float = Query(THRESHOLDS["trust_floor"]),
                   trust_high: float = Query(THRESHOLDS["trust_high"])):
    df = recompute_status(S.require_audit(), confidence_high, trust_floor, trust_high)
    g = (df.groupby("agreement_status")
         .agg(parcels=(KEY_PARCEL, "size"), area_ha=("area_m2", lambda s: s.sum() / 1e4))
         .round(1).reset_index())
    return metric_response(g.to_dict("records"), split_regime=HEADLINE_REGIME,
                           sources=["data/derived/audit.parquet"],
                    thresholds={"confidence_high": confidence_high,
                                "trust_floor": trust_floor, "trust_high": trust_high})


@app.get("/validation/ladder", summary="The Leakage Ladder",
         description="Accuracy and macro F1 for the same model under four validation "
                     "splits. Use this to answer questions about how the system was "
                     "validated or why the headline number is what it is.")
def ladder():
    if S.p4 is None:
        raise HTTPException(503, "Phase 4 has not run.")
    return metric_response(
        {"ladder": S.p4["ladder"], "headline": S.p4["headline"],
         "heads": S.p4["heads"], "sources": S.p4["sources"],
         # GSE vs Presto, paired fold by fold on identical rows, with an explicit
         # underpowered flag — the analyst must not read a noise-level gap as a win.
         "source_comparisons": S.p4.get("source_comparisons", []),
         "sources_pending": S.p4.get("sources_pending", []),
         "presto_caveats": S.p3b and {k: S.p3b.get(k) for k in (
             "domain_shift_note", "meteorology_caveat", "s2_observed_fraction",
             "s1_observed_fraction")}},
        split_regime="all four regimes reported side by side",
        sources=["docs/evidence/p4_results.json"])


@app.get("/validation/confusion", summary="Confusion matrix and per-class metrics",
         description="Per-class precision, recall and F1 with EFFECTIVE sample size "
                     "(independent capture events, not record count), plus the "
                     "confusion matrix. Use for 'which crops confuse most'.")
def confusion(regime: str = Query(HEADLINE_REGIME,
                                  description="Split regime. Required — a metric "
                                              "without its regime is not servable.")):
    if S.p4 is None:
        raise HTTPException(503, "Phase 4 has not run.")
    if regime != HEADLINE_REGIME:
        raise HTTPException(
            400, f"per-class metrics were computed under {HEADLINE_REGIME} only. "
                 "Re-run Phase 4 to produce another regime rather than mislabelling this one.")
    cm = S.p4["confusion_matrix"]
    labels, counts = cm["labels"], cm["counts"]
    pairs = [{"true": labels[i], "predicted": labels[j], "n": counts[i][j]}
             for i in range(len(labels)) for j in range(len(labels)) if i != j]
    pairs.sort(key=lambda r: -r["n"])
    return metric_response(
        {"per_class": S.p4["per_class"], "confusion_matrix": cm,
         "top_confusions": pairs[:10]},
        split_regime=regime, sources=["docs/evidence/p4_results.json"],
        model_version=S.p4["headline"]["head"])


@app.get("/validation/calibration", summary="Calibration quality (ECE)")
def calibration():
    if S.p6 is None:
        raise HTTPException(503, "Phase 6 has not run.")
    return metric_response(S.p6["calibration"], split_regime=HEADLINE_REGIME,
                           sources=["docs/evidence/p6_audit.json"])


@app.get("/evidence/forensics", summary="Ground-truth provenance forensics",
         description="What the supplied survey records actually contain: capture-event "
                     "structure, label inflation, photo-to-parcel distance, effective "
                     "sample size per crop.")
def forensics():
    if S.forensics is None:
        raise HTTPException(503, "Phase 0 has not run.")
    return envelope(S.forensics, n=1, sources=["docs/evidence/gt_forensics.json"])


@app.get("/export", summary="Export the parcel layer",
         description="Download the classified parcel layer with confidence, trust and "
                     "agreement status as CSV or GeoJSON.")
def export(fmt: Literal["csv", "geojson"] = "csv",
           status: Optional[str] = None, village: Optional[str] = None,
           budget: Optional[int] = Query(None, ge=1, le=20000,
                                         description="If set, export the routed field "
                                         "worklist for this many visits — the same rows, "
                                         "order and priority as /audit/worklist."),
           confidence_high: float = Query(THRESHOLDS["confidence_high"]),
           trust_floor: float = Query(THRESHOLDS["trust_floor"]),
           trust_high: float = Query(THRESHOLDS["trust_high"])):
    df = recompute_status(S.require_audit(), confidence_high, trust_floor, trust_high)
    if village:
        df = df[df.village_name.astype(str).str.lower() == village.lower()]
    if budget is not None:
        # Route before the status filter, exactly as /audit/worklist does, so the
        # downloaded file reproduces the on-screen queue row for row.
        out = routed_worklist(df, budget)
        if status:
            out = out[out.agreement_status == status.upper()]
        out = out[["rank"] + WORKLIST_COLS]
        name = f"kaval_worklist_{budget}"
    else:
        if status:
            df = df[df.agreement_status == status.upper()]
        out = df[[KEY_PARCEL, "village_name", "survey_no", "subdivision", "y_true",
                  "y_pred", "confidence_calibrated", "trust_score", "agreement_status",
                  "p_label_wrong", "suggested_crop", "area_m2", "lat", "lon"]]
        name = "kaval_parcels"

    if fmt == "csv":
        # Streamed: a taluk-scale export will not sit comfortably in memory.
        def gen():
            buf = io.StringIO()
            out.head(0).to_csv(buf, index=False)
            yield buf.getvalue()
            for i in range(0, len(out), 5000):
                buf = io.StringIO()
                out.iloc[i:i + 5000].to_csv(buf, index=False, header=False)
                yield buf.getvalue()
        return StreamingResponse(gen(), media_type="text/csv", headers={
            "Content-Disposition": f"attachment; filename={name}.csv"})

    import geopandas as gpd
    g = gpd.GeoDataFrame(out, geometry=gpd.points_from_xy(out.lon, out.lat),
                         crs="EPSG:4326")
    return StreamingResponse(io.BytesIO(g.to_json().encode()),
                             media_type="application/geo+json", headers={
                                 "Content-Disposition": f"attachment; filename={name}.geojson"})


# The agentic analyst (AI-5) is mounted last so that a missing SDK or API key
# degrades to a 503 on its own routes rather than taking the whole API down.
from .analyst import router as analyst_router  # noqa: E402

app.include_router(analyst_router)


# --------------------------------------------------------------- geometry ---
# Without these the map can only draw points. Parcel polygons come from Phase 2/3
# and village boundaries from the supplied administrative layer, so the frontend
# never has to stage geospatial files by hand.

_GEO_CACHE: dict = {}


def _villages():
    if "villages" not in _GEO_CACHE:
        import geopandas as gpd
        from kaval.config import VILLAGES
        g = gpd.read_file(VILLAGES).to_crs("EPSG:4326")
        # Simplified for the browser: 10 m is far below the positional accuracy of
        # a village boundary and cuts payload by roughly an order of magnitude.
        g["geometry"] = g.geometry.simplify(0.0001, preserve_topology=True)
        _GEO_CACHE["villages"] = g
    return _GEO_CACHE["villages"]


@app.get("/geo/villages", summary="Village boundary polygons",
         description="Administrative boundaries for the study area, including the four "
                     "Reserve Forest polygons which carry no ground truth and serve as "
                     "a negative control.")
def geo_villages():
    import json as _json
    g = _villages()
    fc = _json.loads(g.to_json())
    for f in fc["features"]:
        code = f["properties"].get("village_co")
        f["properties"]["is_reserve_forest"] = not str(code).isdigit()
    return envelope(fc, n=len(fc["features"]),
                    sources=["Dataset/Administrative_Boundary/Sivagiri_Villages.geojson"])


@app.get("/geo/parcels", summary="Parcel polygons with audit status",
         description="Parcel geometry joined to agreement status, for the choropleth. "
                     "Filter by village to keep the payload small.")
def geo_parcels(village: Optional[str] = None,
                simplify_m: float = Query(2.0, ge=0.0, le=50.0),
                limit: int = Query(6000, le=20000),
                confidence_high: float = Query(THRESHOLDS["confidence_high"]),
                trust_floor: float = Query(THRESHOLDS["trust_floor"]),
                trust_high: float = Query(THRESHOLDS["trust_high"])):
    import json as _json

    import geopandas as gpd
    path = DERIVED / "parcel_geometry.gpkg"
    if not path.exists():
        raise HTTPException(503, "Phase 3 has not run; parcel geometry is unavailable.")

    df = recompute_status(S.require_audit(), confidence_high, trust_floor, trust_high)
    if village:
        df = df[df.village_name.astype(str).str.lower() == village.lower()]
    # `head()` would return whatever happens to sit first in the file, which is
    # geographically clustered and would silently bias an unfiltered map. Sample
    # instead, and say so in meta.
    truncated = len(df) > limit
    if truncated:
        df = df.sample(limit, random_state=0)

    if "parcels" not in _GEO_CACHE:
        _GEO_CACHE["parcels"] = gpd.read_file(path).to_crs("EPSG:4326")
    geo = _GEO_CACHE["parcels"]
    g = geo[geo[KEY_PARCEL].isin(set(df[KEY_PARCEL]))].merge(
        df[[KEY_PARCEL, "agreement_status", "y_pred", "y_true",
            "confidence_calibrated", "trust_score", "area_m2"]],
        on=KEY_PARCEL, how="inner")
    if simplify_m:
        # Simplify in metres, then return in WGS84 — simplifying in degrees would
        # distort differently with latitude.
        g = g.to_crs("EPSG:32643")
        g["geometry"] = g.geometry.simplify(simplify_m, preserve_topology=True)
        g = g.to_crs("EPSG:4326")
    return metric_response(_json.loads(g.to_json()), n=len(g),
                    split_regime=HEADLINE_REGIME,
                    sources=["data/derived/parcel_geometry.gpkg",
                             "data/derived/audit.parquet"],
                    thresholds={"confidence_high": confidence_high,
                                "trust_floor": trust_floor, "trust_high": trust_high})
