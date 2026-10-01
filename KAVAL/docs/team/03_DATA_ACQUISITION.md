# 03 · Data Acquisition & Provenance

**Owner: M1 (Data & Geospatial) · Phase 1**
Others: read to outline depth. You will be asked "where did this data come from?"

---

## 1. Supplied versus acquired — and why the distinction is graded

The challenge brief requires that FarmwiseAI-provided resources be **clearly
distinguishable** from data we sourced ourselves. That is not bookkeeping; it is how they
judge whether we did independent work.

**Supplied (4 files):** 14,643 ground-truth points, 25 village polygons, the taluk
boundary, the district boundary.

**Everything else we acquired.** `data/PROVENANCE.md` classifies every file as
`SUPPLIED`, `ACQUIRED` or `DERIVED`, and `kaval/provenance.py` is the only way an entry
gets written, so the format cannot drift.

## 2. The blocker that wasn't

Phase 1 was originally recorded as **blocked on Google Earth Engine credentials**. That
was wrong, and correcting it unblocked most of the project.

**Sentinel-1 and Sentinel-2 are published as open cloud-optimised GeoTIFFs behind public
STAC APIs that need no account at all.**

> **STAC** = SpatioTemporal Asset Catalog. A standard JSON API for searching satellite
> imagery by space and time. You query it, it returns URLs to COGs (cloud-optimised
> GeoTIFFs), and you read only the byte ranges you need — no bulk download.

Two endpoints, both verified reachable and both anonymous:

- **Element84 Earth Search** on AWS Open Data — `sentinel-2-c1-l2a`
- **Microsoft Planetary Computer** — `sentinel-1-rtc` (terrain-corrected)

Only the **Google Satellite Embedding** is genuinely Earth-Engine-only, and we already
held it for all 14,643 parcels from prior work. **Phase 2's primary path was never
actually blocked.**

*In review:* this is worth volunteering. It shows we questioned our own assumption rather
than accepting a blocker.

## 3. Every source, and its limitation

| Source | What | Why this one | Limitation |
|---|---|---|---|
| **Google Satellite Embedding** | 64-d unit-length vector per 10 m pixel per year | The brief names it; the hard feature-extraction work is already done | **Annual**, not seasonal — summarises a year |
| **Sentinel-2 L2A** (Element84) | 10 m optical, ~5-day revisit | Anonymous, open, the FTW model's expected input | Cloud-blocked; TN's Oct–Dec monsoon is exactly our survey window |
| **Sentinel-1 RTC** (Planetary Computer) | C-band SAR, VV/VH | **Sees through cloud** | Only **descending** orbits exist for this AOI, so we fix descending rather than mix |
| **Fields of The World** | Pretrained U-Net, EfficientNet-B7 | Trained across 24 countries incl. Asian smallholders | CC-BY checkpoint is less accurate than the mixed-licence one — a deliberate licensing cost |
| **TN Agrisnet registry** | Village-wise DCS crop area, Rabi 2024 | The only village-level source we found | **Not independent** — see §5 |
| **CHIRPS** | Monthly rainfall, 0.05° | Public HTTP, no key | ~5.5 km cells — taluk-scale only |
| **NASA POWER** | Monthly T2M (MERRA-2) | **Keyless substitute for ERA5-Land** | ~0.5° (~55 × 70 km) — the whole taluk is 1–2 cells |
| **Presto** | Pretrained RS time-series transformer | The brief's second embedding arm | Pretrained on **L1C**; we feed **L2A** — a documented domain shift |

**Two substitutions to be able to name.** ERA5-Land needs a Copernicus CDS key we do not
hold, so temperature comes from NASA POWER instead — recorded as a *substitution*, not a
quiet fill of the ERA5-Land row. MODIS LST needs an Earthdata login and was not acquired;
it is not on the critical path.

## 4. Repairing the ground truth

`scripts/p1_repair_ground_truth.py` produces the canonical record table. Four defects:

| Defect | Count | Handling |
|---|---:|---|
| Two coordinates in one cell (`;`-joined) | 647 | Split, first value taken |
| Photo coordinate outside the study area | 13 | Nulled, **not** guessed — the trust signal degrades gracefully |
| Blank subdivision | 283 | Normalised to empty string, **never dropped** — a parcel with no subdivision is still a parcel |
| Duplicate parcel keys | 32 | First kept, counted |

### The defect worth telling people about

**The same row stores the same date in two different formats.** `timestamp` is
**MM-DD-YYYY**; `image_timestamp`, in the same row, is **DD-MM-YYYY**. The single value
`13-11-2024` is DD-MM in both, because month 13 is impossible and the collection app fell
back.

Parse `timestamp` naively with `dayfirst=True` and an **eight-day survey appears to span
June to December**. We take `image_timestamp` as authoritative and cross-check: zero
disagreement. The survey ran **2024-11-06 to 2024-11-13**, 8 days.

*Why this matters beyond tidiness:* any seasonal feature keyed on survey date would have
been silently wrong.

## 5. The registry caveat — know this cold

We acquired the **TN Agrisnet village-wise Digital Crop Survey report** — 12,097 ha across
21 villages for Rabi 2024. It is a real village-level registry and it makes the brief's
"compare against the supplied registry" query answerable.

**But it is not independent of what we audit.** Agrisnet publishes the *aggregate of the
same Digital Crop Survey* whose parcel-level sample FarmwiseAI supplied to us.

So a satellite-vs-registry delta **audits the survey's own published numbers against
satellite**. That is genuinely useful. It is **not** validation against a second,
independent survey, and we must never present it as one.

This caveat is carried **in the API response payload**, not only in documentation, so the
LLM analyst physically cannot overstate it.

## 6. Provenance: the rule and why it is strict

> **An acquired or derived file without a `PROVENANCE.md` entry does not exist.**

`provenance.require(path)` raises if a file is unrecorded, and it guards every load in
every phase script. Each entry records source, acquisition date and agent, licence,
spatial and temporal extent, CRS, transform applied, producing script, and SHA256.

Why so strict: three months from now nobody remembers which CSV came from where. More
immediately, the brief grades us on distinguishing supplied from acquired data, and a
provenance file with only `DERIVED` entries — which is what we had at one point — cannot
do the job its own header claims.

## 7. What is still missing

| Item | Blocker | Impact |
|---|---|---|
| Cadastral / FMB geometry | Request to FarmwiseAI | No IoU benchmark for AI-1 |
| Survey photographs | Request to FarmwiseAI | AI-6 vision check not possible |
| MODIS LST | Earthdata login | Not on critical path |

---

## Questions you must be able to answer

**"Why didn't you use Earth Engine for the imagery?"**
> We planned to, then found we did not need to. Sentinel-1 and Sentinel-2 are served
> through public STAC endpoints with no account. Only the Google Satellite Embedding is
> genuinely Earth-Engine-only, and we already held it. We had recorded Phase 1 as blocked
> on credentials, and that was our own mistaken assumption.

**"Is your registry comparison independent validation?"**
> No, and the caveat is in the API payload, not just the docs. Agrisnet publishes the
> aggregate of the same survey we audit. It audits the survey's published numbers against
> satellite — useful, but not a second independent source.

**"You substituted NASA POWER for ERA5-Land. Is that legitimate?"**
> Both are reanalysis products; POWER serves MERRA-2 without a key. We record it as a
> substitution rather than filling the ERA5-Land row, and we state the resolution
> consequence: ~0.5°, so the whole taluk sits in one or two cells. It carries seasonality,
> which is what Presto reads it for, but no within-taluk spatial signal.

**"How do you know your rainfall and temperature aren't adding noise?"**
> We do not claim they add signal. They are constant across the taluk within a month by
> construction. They are in the Presto input because Presto expects those channels; if
> they were absent the model would mask them. That is stated in the evidence artefact.

**"What if a data source disappears?"**
> Every acquisition is a committed re-runnable script, and every file carries a SHA256 in
> `PROVENANCE.md`, so we can detect silent change. We cannot guarantee a third party keeps
> serving; we can guarantee we would notice.


## A file we produce but do not use: `seasonal_s1_s2_stac.csv`

`p1_acquire_stac.py` writes per-parcel seasonal Sentinel-1/2 means (`S1..S4` × NDVI,
VV, VH) from the keyless STAC imagery. It is **deliberately not** fed to the feature
store. It carries only the 12 seasonal columns and none of the 64 Google Satellite
Embedding bands, so swapping it in would silently drop GSE. It also measures a
different thing from the GEE export's seasonal bands (the project's configured season
windows over parcel polygons, against calendar quarters over 30 m point buffers), and
the two agree only moderately.

Why keep it: it is the path to rebuilding the seasonal arm without Earth Engine
credentials. Using it is a deliberate Phase 3 → 4 re-run, not a file swap. An earlier
docstring said `--features` "accepts it"; that was true of the column names and false of
the result.
