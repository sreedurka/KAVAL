# 05 · Features & Embeddings

**Owner: M2 (ML & Validation) · Phase 3 · AI-2**

---

## 1. Why embeddings change the problem

The hardest part of remote sensing — turning raw imagery into numbers that mean something
— has already been solved by someone else. A **satellite embedding** is a fixed-length
vector summarising what a pixel looked like over time.

That converts a computer-vision problem into a **tabular ML problem** plus a spatial join.
It is why a four-person student team can attempt this at all, and it is exactly what the
brief intends when it says teams are "not expected to create the satellite embeddings".

## 2. Google Satellite Embedding (AlphaEarth)

Google/DeepMind ran a foundation model over Landsat, Sentinel-1 and Sentinel-2 and
published, for **every 10 m pixel on Earth** and every year 2017–2025, a **64-dimensional
unit-length vector**.

**Three properties that dictate how we use it:**

1. **Unit-length.** The vectors are L2-normalised by construction. Do **not** re-normalise
   them, and do not standardise per-feature without saying so — that destroys the geometry
   the embedding encodes. Our `gee-export` skill states this as a rule.
2. **Annual.** It summarises a *year*, not a season. So it cannot by itself distinguish a
   parcel that grew rice in Rabi from one that grew it in Kharif. This is a real
   limitation and the reason seasonal features were worth testing at all.
3. **Dense and continuous.** Not a set of independent tabular columns but a learned
   continuous space — which turns out to matter for model choice (see doc 07).

## 3. Presto — the second arm

Presto (NASA Harvest, MIT) is a **transformer over remote-sensing time series**. It reads a
sequence of monthly per-pixel observations and returns a 128-d vector.

**Why the comparison is informative rather than ceremonial:** GSE sees a *year*; Presto
sees **phenology** — the shape of the growing season, when the crop greened up, how fast,
when it senesced. Those are genuinely different inductive biases, so whichever wins tells
you something about the task.

**Status: run.** The checkpoint loads with a strict state-dict match (822,682 parameters),
its input contract is in `docs/PRESTO_NOTES.md`, and `scripts/p3b_presto_embeddings.py`
produced a 128-d embedding for all 14,611 parcels from monthly Sentinel-1/2 series,
Copernicus DEM GLO-30 terrain (substituted for SRTM), CHIRPS rainfall and NASA POWER
temperature (substituted for ERA5-Land). Evidence: `docs/evidence/p3b_presto.json`.

### The result

Regime `3-event`, MLP head, identical rows and folds for every source, 14,310 parcels,
5-fold (`docs/evidence/p4_results.json` → `sources`, `source_comparisons`):

| Source | Features | Accuracy | Macro F1 | Δ macro F1 vs GSE (paired) | SD of Δ | Folds favouring | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| GSE only | 64 | 81.5% | 0.563 | — | — | — | reference |
| GSE + seasonal | 76 | 81.7% | 0.564 | +0.0008 | 0.008 | 2/5 | underpowered |
| Seasonal only | 12 | 73.7% | 0.399 | −0.165 | 0.033 | 0/5 | worse |
| Presto only | 128 | 74.2% | 0.452 | −0.111 | 0.011 | 0/5 | worse |
| GSE + Presto | 192 | 81.3% | 0.559 | −0.004 | 0.006 | 1/5 | underpowered |

**How to say it.** The brief asked for GSE vs Presto; we ran it. GSE wins clearly as a
standalone source: the gap is ten times the spread of the paired deltas and every fold
agrees. Combining the two adds nothing measurable. That is **not** a verdict that Presto is
the worse model — the caveats below limit it, and we name them before anyone asks.

**The monsoon finding.** Sentinel-2 was observed for 92.2% of parcel-months overall but
only 38.1% in 2024-11, the survey month itself, because of north-east monsoon cloud
(`p3b_presto.json` → `s2_observed_fraction`, `s2_worst_month`). Any optical time-series
model is short of evidence exactly when the survey is taken. GSE's annual multi-sensor
summary is less exposed to that, which is a useful thing for FarmwiseAI to know on its own.

### Four things that qualify the comparison

- **Domain shift.** Presto was pretrained on Sentinel-2 **L1C** (top-of-atmosphere). We
  feed **L2A** (surface reflectance), because that is what the STAC endpoints serve and
  what the rest of the pipeline uses. A small systematic shift, reported rather than
  silently corrected.
- **Coarse meteorology.** Presto expects temperature and precipitation per pixel. Ours are
  reanalysis at 0.05° (CHIRPS) and ~0.5° (MERRA-2): **taluk-scale**. Every parcel in a
  month gets the same value. They carry seasonality, which is what Presto reads them for,
  but no within-taluk spatial signal.
- **Parcel means, not pixels.** Each parcel gets one monthly series, the mean over its
  pixels. Presto was pretrained on per-pixel series.
- **Frozen encoder.** No fine-tuning; the 128-d embedding goes to the same MLP head and
  folds as GSE.

One mismatch we did remove: our `SEASON_WINDOWS` are four three-month windows, but Presto
was pretrained at **12 steps of 30 days**, so a separate monthly series was acquired rather
than reusing the seasonal one.

**One implementation trap worth knowing:** in Presto's `mask`, **1 means masked and 0
means observed**. A cloud-gapped month is flagged missing, never interpolated — the model
handles ragged masks natively, and inventing a value would be worse than admitting the gap.

## 4. Zonal aggregation: mean *and* standard deviation

Several embedding pixels fall inside one parcel, so they must be reduced to one vector.

We keep **mean and standard deviation**, not just the mean. The mean is the parcel's
signature. The **standard deviation is an audit signal**: a parcel whose pixels disagree
with each other is either mixed-crop, mis-delineated, or partly something other than the
declared crop. It feeds the Record Trust Score as `heterogeneity`.

This is the general habit: *when a reduction throws information away, ask whether the
discarded part is itself informative.*

## 5. The feature store

`scripts/p3_feature_store.py` → `data/derived/feature_store.parquet`

**14,611 parcels × 76 features** (64 GSE + 12 seasonal Sentinel-1/2).

| Column group | Purpose |
|---|---|
| `parcel_id` | the land unit |
| **`bag_id`** | **capture event — the leakage group key** |
| `village_code`, `village_spatial` | recorded vs actual village |
| **`field_id`** | **delineated field — the second leakage key** |
| `A00`–`A63` | GSE embedding |
| `S1_*`–`S4_*` | seasonal NDVI/VV/VH |
| `crop`, `crop_stage` | labels |
| `photo_distance_m`, `bag_size`, `mixed_crop`, `stage_plausibility`, `heterogeneity`, `geometry_source` | trust signals, precomputed here because they come from the same join |

**The invariants, asserted every run:**

```python
assert df[KEY_PARCEL].notna().all()
assert df[KEY_BAG].notna().all()          # leakage key must survive
assert df.groupby(KEY_BAG)[LABEL].nunique().max() == 1   # bags are single-label
assert df[KEY_PARCEL].is_unique
```

If `bag_id` is lost in a groupby, Phase 4 silently becomes a random split. The assertion
is why that cannot happen quietly.

301 parcels (2.06%) have no feature row. They are **flagged
`has_features=False`, not dropped** — the count is reported, and downstream phases filter
explicitly rather than losing them silently.

## 6. Evaluable classes

A class with too few **independent capture events** cannot be evaluated, no matter how many
records it has. We collapse anything under 5 events into `Other`:

**Kept:** Banana, Coconut, Maize, Rice (Paddy), Sugarcane
**Collapsed:** Cassava, Diploid Cotton (Paruththi), Fodder Sorghum, Groundnut, Mango, Marigold, Sorghum

Those seven crops have between 1 and 4 capture events each. Mango has 6 records and **one**
observation. Reporting an F1 for it would be arithmetic, not measurement.

---

## Questions you must be able to answer

**"Why not just train on the raw imagery?"**
> We could, and it would be a worse use of the time. The embeddings encode what a
> pixel-level model would have to learn, from far more data than we have. The brief
> explicitly says teams are not expected to build them. Our contribution is in what you do
> *with* them — the validation protocol and the audit layer.

**"Which embedding is better, GSE or Presto?"**
> On this data, as we could feed it, GSE: 0.563 against 0.452 macro F1 under
> capture-event grouping, behind on all five folds. Combining them adds nothing we can
> measure. We would not generalise that to "Presto is worse": we fed it L2A where it was
> pretrained on L1C, parcel means where it was pretrained per pixel, taluk-scale
> meteorology, and a frozen encoder. And in the survey month only 38.1% of parcel-months
> had a cloud-free Sentinel-2 view, which hurts any optical time-series model.

**"Why keep the standard deviation? Isn't the mean enough for classification?"**
> For classification, largely yes. We keep it because a parcel whose pixels disagree with
> each other is telling you something about the *record*, not the crop — mixed cropping,
> bad delineation, a parcel that is partly something else. It is a trust signal, and the
> product is an audit.

**"What happens if `bag_id` gets dropped somewhere?"**
> It cannot happen silently. `p3_feature_store.py` asserts it is present and non-null, and
> `kaval/splits.py` raises if the group key is missing. If it were lost, the headline
> regime would quietly degrade into a random split and we would report ~90% — the exact
> failure the project exists to prevent.
