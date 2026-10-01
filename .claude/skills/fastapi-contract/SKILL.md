---
name: fastapi-contract
description: KAVAL's FastAPI backend conventions - endpoint shapes, the typed tool layer the agentic analyst calls, response envelopes and export formats. Load before writing or changing any backend endpoint, Pydantic model, or agent tool definition. Triggers: "FastAPI", "endpoint", "API", "Pydantic", "route", "backend", "tool definition", "export GeoJSON".
---

# Backend Contract

FastAPI + Pydantic v2. The API is not a data dump — it is the **tool surface the agentic
analyst (AI-5) plans over**, so every endpoint is designed to be callable by a model as
much as by the frontend.

## Endpoints

| Route | Returns |
|---|---|
| `GET /parcels` | paged parcels; filter by village, crop, agreement status, confidence range, trust range |
| `GET /parcels/{parcel_id}` | one parcel, full audit trail: prediction, calibrated confidence, survey label, trust components, bag id, bag size, photo distance |
| `GET /summary/crop-area` | crop-wise area; group by village or taluk; satellite vs declared |
| `GET /summary/registry-delta` | per-village declared vs satellite-estimated area, sorted by divergence |
| `GET /audit/worklist` | ranked field-verification queue; `budget=N` returns the top N with expected corrections |
| `GET /audit/auto-clear` | parcels safe to skip next season, with the surveyor-day saving |
| `GET /validation/ladder` | the Leakage Ladder, served from the evidence artefacts |
| `GET /validation/confusion` | confusion matrix + per-class metrics, `regime` parameter required |
| `GET /export` | CSV or GeoJSON of any filtered parcel set |

## Response envelope

Every response carries provenance, because the agent must cite its sources:

```json
{
  "data": [...],
  "meta": {
    "n": 1234,
    "split_regime": "3-capture-event",
    "model_version": "mil-attn-v2",
    "generated_at": "...",
    "sources": ["data/derived/feature_store.parquet"]
  }
}
```

## Rules

1. **`split_regime` is required** on any response containing a metric. A metric without
   its regime must be impossible to serve. See `leakage-protocol`.
2. **Thresholds are query parameters with config defaults**, never hard-coded — the
   frontend's threshold sliders depend on this.
3. **Every numeric field the frontend displays comes from here.** No computation in the
   browser beyond formatting.
4. **Tool descriptions are part of the contract.** The agent selects tools by reading
   them; write them for a model, stating what the tool returns and when to use it.
5. **Exports stream.** A taluk-scale GeoJSON will not fit comfortably in memory.
6. Read-only. KAVAL audits; it does not write back to survey records.
