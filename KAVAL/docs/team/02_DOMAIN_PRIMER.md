# 02 · Domain Primer

**Audience:** everyone. The brief says domain knowledge is not a prerequisite *for the
proposal*. It absolutely is for the review — the people asking questions do this for a
living, and FarmwiseAI's customers are revenue and agriculture departments.

---

## 1. What the Digital Crop Survey actually is

India runs a **Digital Crop Survey (DCS)** as part of **AgriStack**, the national digital
public infrastructure for agriculture. AgriStack has three registries:

| Registry | Contents |
|---|---|
| Farmers' Registry | who farms |
| Geo-referenced village maps | where the land is |
| **Crop Sown Registry** | **what is growing — this is the DCS output** |

Every season, a surveyor physically visits agricultural parcels and records the crop, its
growth stage, and a geotagged photograph. Rabi 2024-25 covered 461 districts and over 23
crore plots.

**Our dataset is a DCS extract** — Sivagiri taluk, Tenkasi district, Tamil Nadu,
2024-11-06 to 2024-11-13. That is why the columns are village LGD code, survey
number, subdivision, crop, stage, and an image reference.

### Why anyone cares

DCS crop-area statistics are **load-bearing**. They feed:

- **PM Fasal Bima Yojana** — crop insurance settlement
- **MSP procurement planning** — how much the state expects to buy
- **Drought and flood compensation**
- Fertiliser and subsidy allocation

A wrong crop label on a parcel is not a metric. It is a payment. **That is the sentence to
use in review** when someone asks why an audit matters.

### The cost problem

A human must visit every parcel every season. Tamil Nadu alone has crores of parcels. This
is the recurring expense our product attacks — not by replacing the survey, but by telling
the department which visits are worth making.

---

## 2. Indian land records — the vocabulary

| Term | Meaning | Where you see it |
|---|---|---|
| **Survey number** | The primary land parcel identifier in a village | `survey_n_1` |
| **Subdivision** | A survey number split by inheritance or sale (1A, 2B) | `sub_divi_1` |
| **Village LGD code** | Local Government Directory code — the national key for a revenue village | `Village LG`, `village__1` |
| **Taluk** | Administrative unit below district (Sivagiri) | `taluk_co_1` |
| **FMB** | Field Measurement Book — the cadastral map holding parcel geometry | *not supplied to us* |
| **Adangal / Chitta** | Village land records listing ownership and crop | the DCS updates these |
| **Revenue village** | The administrative unit; not the same as a settlement | 21 of our 25 polygons |
| **Reserve Forest** | Protected land, not revenue land | the other 4 polygons |

**The critical distinction for our work:** a **survey number + subdivision is a *legal*
unit**, created by registration and inheritance. A **field is a *physical* unit**, defined
by what is actually farmed as one block. They are not the same thing, and our Phase 2
finding is precisely that satellite imagery can see the second but not the first.

### Crop calendar, Tamil Nadu

| Season | Roughly | Notes |
|---|---|---|
| **Kharif** | Jun–Sep | south-west monsoon |
| **Rabi** | Oct–Mar | **our survey window**; north-east monsoon is the main rain here |
| **Summer / Zaid** | Mar–Jun | irrigated |

Tamil Nadu is unusual in India: it depends on the **north-east monsoon (Oct–Dec)**, not the
south-west. That matters practically — it is why Sentinel-2 has cloud gaps exactly in the
months around our survey.

Our five evaluable crops: **Rice (paddy)** 63%, **Coconut** 18%, **Maize** 11%, **Banana**,
**Sugarcane**. Coconut and Banana are **perennials** — they are in the ground all year,
which is why they behave differently from annual crops in both the classifier and the
field delineation.

---

## 3. Remote sensing — only what you need

### Sentinel-2 (optical)

ESA satellites, **10 m** resolution for the visible and near-infrared bands, revisit every
~5 days. Sees colour and vegetation. **Blocked by cloud** — the central limitation.

- **L1C** = top-of-atmosphere reflectance. **L2A** = surface reflectance (atmospherically
  corrected). We use L2A. *Remember this: Presto was pretrained on L1C, which is a
  documented domain shift in our work.*
- **NDVI** = (NIR − Red) / (NIR + Red). Ranges roughly −1 to 1; healthy vegetation is high.
  The oldest and most common vegetation index.

### Sentinel-1 (radar, SAR)

**Sees through cloud** — which is why it matters in a monsoon region. Measures backscatter,
i.e. how much radar energy returns, which depends on surface roughness and moisture.

- **VV / VH** = polarisation combinations. VH is more sensitive to vegetation volume.
- Measured in **dB** (logarithmic). *Averaging in dB and averaging in linear power give
  different answers* — we average in linear and convert after.
- **Orbit direction** (ascending/descending) changes the viewing geometry, so mixing them
  in a time series introduces a step change that is not real. We fix one.

### Google Satellite Embedding (AlphaEarth)

This is what the brief means by "satellite embeddings". Google/DeepMind ran a foundation
model over Landsat, Sentinel-1 and Sentinel-2 and published, for every 10 m pixel on Earth
and every year 2017–2025, a **64-dimensional unit-length vector** summarising that pixel's
year.

**Why it matters:** the hard part — turning raw imagery into meaningful numbers — is
already done. It turns a remote-sensing problem into a tabular ML problem.

**Two things to know:** the vectors are **unit-length**, so do not re-normalise them; and
they are **annual**, so they summarise a year, not a season.

### Presto

NASA Harvest's pretrained transformer for remote-sensing **time series**. Reads a sequence
of monthly observations per pixel and returns a 128-d vector. Where GSE sees a year, Presto
sees **phenology** — the shape of the growing season. That difference is why comparing them
is informative rather than ceremonial.

### Fields of The World (FTW)

A benchmark and pretrained model for **field-boundary segmentation** — a U-Net that takes
bi-temporal Sentinel-2 and outputs three classes: field interior, field boundary,
background. Trained across 24 countries. We use the CC-BY EfficientNet-B7 checkpoint.

---

## 4. The concepts our argument rests on

### Spatial autocorrelation

Nearby things are similar. Two adjacent parcels have nearly identical satellite signatures.
If one is in training and the other in test, the model can *retrieve* rather than
*generalise*, and the reported accuracy is inflated.

**This is the root of everything in Phase 4.** Standard machine-learning practice — shuffle
and split — is simply wrong on spatial data, and the brief itself warns that leakage
"will invalidate the claimed result".

### Effective sample size

If 14,643 records come from 3,204 independent observations, your statistical power
is 3,204, not 14,643. Per-class metrics for minority crops rest on a handful of
real observations — Marigold's 36 records are 3.

**Always quote capture events alongside record counts.** It is the single habit that most
distinguishes our reporting.

### Calibration

A model saying "90% confident" should be right 90% of the time. Most are not — ours
overstated by twelve points before correction. **Expected Calibration Error (ECE)**
measures the gap. It matters because we route a budget on confidence, and a number that
lies cannot allocate money.

### Multiple-Instance Learning (MIL)

A framework for when labels attach to a *bag* of instances rather than each instance. Our
situation exactly: one photograph labels up to 43 parcels, so the label belongs to the
capture event, not to any individual parcel.

### Confident learning

Finding label errors by looking at where a model confidently disagrees with the given
label. The subtlety: a disagreement is evidence about the *label*, not proof — the model
is only ~82% accurate itself (capture-event-grouped), which is why our estimate is discounted by that accuracy.

---

## 5. Domain facts specific to *our* data

These are the things a reviewer might test you on.

- **14,643 records, 3,204 capture events.** One photograph, up to 43 parcels, and
  **0** events with more than one crop — the label is attached to the event and copied.
- **The photograph sits a median 1,436 m from the parcel it documents** (62.3% over 1 km).
  It cannot serve as per-parcel visual evidence.
- **The same row stores one date in two formats.** `timestamp` is MM-DD-YYYY,
  `image_timestamp` is DD-MM-YYYY. Parse naively and an 8-day survey appears to span June
  to December.
- **1,930 records (13%) sit in a different village polygon than their code claims**, 1,895
  of them in the Viswanathaperi 911/912 pair. All 1,175 records coded 912 fall inside
  polygon 911, which *suggests* a boundary or labelling error in the supplied layer. Do not
  say the registry confirms it: the registry is compiled from the same recorded codes, so it
  agrees with them by construction (correction #22). It is a question for FarmwiseAI.
- **Reserve Forests are not farmland.** Four of the 25 polygons are protected forest with
  `village_co = 'YYY'`. An earlier draft of our own proposal got this wrong.

---

## 6. FarmwiseAI — who we are pitching to

A Chennai GeoAI company selling to **government**: revenue departments, agriculture
departments, district collectors. Their work is land records, cadastral mapping and
parcel-level intelligence.

**What follows for our framing:** they do not buy model F1 scores. They buy defensible
statistics and lower operating cost. That is why the product is an audit with a
surveyor-day saving attached, and it is why our accidental finding about their **boundary
layer** may be the most commercially interesting thing we produced.
