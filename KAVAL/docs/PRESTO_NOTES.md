# Presto input contract (for Phase 3)

Source: `github.com/nasaharvest/presto`, commit `11e207a668a34336ced1d8e492a1bd5849b96c4a`
(2026-06-10), MIT. Everything below was read from that commit's code, then checked by
running it. Items marked **UNVERIFIED** could not be confirmed from the code we hold.

Use `KAVAL/kaval/presto_io.py` (`load_presto`, `build_inputs`, `embed`). Do not re-derive
the normalisation by hand. Acquisition: `KAVAL/scripts/p1_acquire_presto.py`.
Checkpoint: `KAVAL/models/presto/default_model.pt` (3.3 MB; 822,682 params, encoder 404,160).

## Traps we hit (read these first)

1. `Presto.load_pretrained()` **fails** after a normal pip install: it reads
   `<venv>/lib/python3.12/data/default_model.pt`, which is never installed. `presto_io.load_presto()`
   loads from `KAVAL/models/presto/` instead, strict state-dict match.
2. `import presto` needs `ee`, `openmapflow`, `cropharvest`, `webdataset`... at import time,
   pinned upstream to `numpy==1.23.5`, `torch==2.0`. Installed `--no-deps`; `presto_io` puts inert
   stubs for those names LAST on `sys.meta_path`. Never `pip install presto` with deps in this venv.
3. **Do not use `single_file_presto.py`.** Its `mask_tokens` asserts every row in a batch has the
   same masked-token count (`AssertionError: 9344.0, 128.0`). Real cloud-gapped pixels have ragged
   masks. The package `Presto` handles ragged masks (verified: batched vs one-at-a-time max diff
   9.5e-7; identical to single-file when masks are uniform).
4. `construct_batch_presto_input` returns `dynamic_world` as **float** when none is given; the
   embedding lookup needs **long**. `build_inputs` casts it. Calling upstream directly raises
   `Expected ... Long, Int; but got torch.FloatTensor`.
5. In `mask`, **1 = MASKED (ignored)**, 0 = observed. Opposite of a validity mask.

## Model call

```python
from kaval import presto_io as P
model = P.load_presto()                       # eval mode, CPU
x, mask, dw = P.build_inputs(s1_db=..., s2_dn=..., era5_temp_k=..., era5_precip_m=...,
                             srtm_elev_m=..., srtm_slope_deg=...)
z = P.embed(model, x, mask, dw, latlons, start_month=10)   # -> float32 [N, 128]
# underlying call:
# model.encoder(x, dw, latlons, mask, month=start_month, eval_task=True)  # mean over unmasked tokens
```

Embedding = `Encoder(..., eval_task=True)`: mean over non-masked tokens, then LayerNorm. 128-d.
Config (default.json): embed 128, depth 2, 8 heads, mlp_ratio 4, max_sequence_length 24.

## Tensors

| arg | shape / dtype | meaning |
|---|---|---|
| `x` | `[B, T, 17]` float32 | NORMALISED values, band order below |
| `dynamic_world` | `[B, T]` **int64** | Dynamic World class 0-8 per step; **9 = missing** (ignored) |
| `latlons` | `[B, 2]` float32 | `(lat, lon)` in degrees, WGS84. Order is lat first |
| `mask` | `[B, T, 17]` float32 | **1 = masked**, 0 = observed. Masking is by band GROUP token, see below |
| `month` | int 0..11 (or `[B]` tensor) | calendar month of timestep 0. **0 = January**, so November = 10. Must be < 12 |

`T` may be any value 1..24. Pretraining used 12 steps (`NUM_TIMESTEPS = 12`); the model max is 24.
Steps are consecutive months from `month`, wrapping mod 12.

**Timestep cadence.** openmapflow (the pretraining exporter), `DAYS_PER_TIMESTEP = 30`. So one
step is a ~30-day composite. For Rabi 2024-25 the natural choice is 12 steps from
2024-06-01 (`month = 5`) or 2024-09-01 (`month = 8`) - decide once, in config, and keep it
identical for every parcel. **Our current SEASON_WINDOWS are 4 x 3-month windows; that is 4
timesteps at the wrong cadence.** Presto needs ~monthly composites from the Sentinel agent.

## Band order (17 channels, `PRESTO_BANDS`)

`VV, VH, B2, B3, B4, B5, B6, B7, B8, B8A, B11, B12, temperature_2m, total_precipitation,
elevation, slope, NDVI`

B1, B9, B10 are dropped. NDVI is recomputed inside `normalize` from the normalised B8/B4, so you
do not supply it.

## Raw units and normalisation (`x = (raw + shift) / div`, applied by `build_inputs`)

| band | raw unit you must supply | shift | div |
|---|---|---|---|
| VV, VH | Sentinel-1 backscatter in **dB** (GEE `COPERNICUS/S1_GRD` native; range about -50..1) | +25 | 25 |
| B2..B12 (10 bands) | reflectance **x 10000** (i.e. the raw DN, 0..10000+, NOT 0..1) | 0 | 10000 |
| temperature_2m | **kelvin** | -272.15 | 35 |
| total_precipitation | **metres** accumulated over the 30-day step | 0 | 0.03 |
| elevation | metres | 0 | 2000 |
| slope | degrees | 0 | 50 |
| NDVI | computed = (B8-B4)/(B8+B4), 0 if denominator <= 0 | - | - |

There is no clipping. Values outside the training range are passed through as-is.

## What Presto was pretrained on (domain-shift risks for us)

From `openmapflow` main (the exporter behind the pretraining data; **UNVERIFIED** against the
pinned openmapflow 0.2.2 that the repo's setup.py names):

- S2: `COPERNICUS/S2_HARMONIZED` - **L1C top-of-atmosphere**, not L2A surface reflectance. A
  cloud-score-ranked mosaic per 30-day step. We are feeding L2A SR: a small systematic shift, most
  visible in B2/B3 and B11/B12. Report it. Do not silently "fix" it.
- S1: `COPERNICUS/S1_GRD`, IW mode, one orbit direction (first image's), per-step median VV / VH.
  Fix one orbit as our gee-export rule already requires.
- ERA5: `ECMWF/ERA5_LAND/MONTHLY_AGGR`, `temperature_2m` (K, mean) and `total_precipitation_sum`
  (m, monthly sum), mean over the step window.
- SRTM elevation and slope (static, repeated over all steps).
- Dynamic World is optional: pass all 9 (missing) and it is ignored. We have no DW, so do that.
- Pretraining years 2020-2021 (mask strategy + Dynamic World as auxiliary target).

## Missing data

Any NaN in a raw array becomes mask = 1 in `build_inputs` (per band). A band that is entirely
absent (e.g. no ERA5 supplied) is masked for all steps. If you drop S2 for a step (cloud), NDVI
for that step is masked too. Ragged per-row masks are fine.

## What has and has not been verified

- Verified by running: checkpoint loads strict; forward pass finite; normalisation of VV, B4,
  temperature, precipitation and NDVI matches hand computation; NaN and ragged masks handled;
  batched == single.
- Done since: Presto has been run on all 14,611 parcels over 12 monthly steps (2024-06 to
  2025-05). See Result below.
- Not verified: the pretraining-exporter details marked UNVERIFIED above; whether L2A vs L1C
  matters for this AOI (test it: it is one ablation once L1C is available from the STAC route).
- Presto pretraining licence: repo is MIT; no separate weights licence is stated. Keep
  `KAVAL/models/presto/LICENSE` alongside the checkpoint.

## Result

Run by `scripts/p3b_presto_embeddings.py` (inputs and caveats: `docs/evidence/p3b_presto.json`)
and compared by `scripts/p4_ladder_and_baselines.py` section C (`docs/evidence/p4_results.json` → `sources`,
`source_comparisons`). Regime `3-event`, MLP head, identical rows and folds, 14,310 parcels,
5-fold:

| Source | Accuracy | Macro F1 | Δ macro F1 vs GSE (paired) | SD of Δ | Folds favouring |
|---|---:|---:|---:|---:|---:|
| GSE only (64-d) | 81.5% | 0.563 | — | — | — |
| Presto (128-d) | 74.2% | 0.452 | −0.111 | 0.011 | 0/5 |
| GSE + Presto (192) | 81.3% | 0.559 | −0.004 | 0.006 | 1/5 (underpowered) |

GSE wins clearly as a standalone source; combining adds nothing measurable. This is not a
verdict on Presto as a model. Four caveats limit it, all recorded in `p3b_presto.json`: L2A
input where Presto was pretrained on L1C (`domain_shift_note`); taluk-scale meteorology
(`meteorology_caveat`); one parcel-mean series per parcel where Presto was pretrained per
pixel (`input_granularity`); frozen encoder, no fine-tuning (`usage`). Terrain is Copernicus
DEM GLO-30 in the SRTM slot (`terrain_source`); temperature is NASA POWER in place of
ERA5-Land (`temperature_source`).

Sentinel-2 was observed for 92.2% of parcel-months overall but only 38.1% in 2024-11, the
survey month, because of north-east monsoon cloud (`s2_observed_fraction`,
`s2_worst_month`). That is a structural handicap for any optical time-series model on this
survey. The L1C ablation listed under "Not verified" above remains the cleanest next test.
