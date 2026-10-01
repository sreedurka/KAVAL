# Data Request to FarmwiseAI

**Project:** KAVAL — Task 3, Satellite-Embedding-Based Crop Classification
**Status:** no item blocks the prototype; each makes the result materially stronger

We have built the pipeline on the supplied reference sample and on data we sourced
independently. Three items held by FarmwiseAI would each unlock a specific result we cannot
produce otherwise. We have designed around the absence of all three.

---

## 1. Cadastral / FMB parcel geometry for Sivagiri taluk

**Why we are asking.** Task 3 asks for parcel-level classification, but the supplied
package contains ground-truth *points* and village boundaries — no parcel polygons.
Without polygons there is no parcel-level area statistic, no zonal aggregation of
embeddings, and no map. Task 2's resource list mentions FMB or equivalent survey reference
maps, so this geometry appears to exist within FarmwiseAI.

**What we have done instead.** Two paths, both built:

- *Primary (AI-1):* satellite field-boundary delineation using the pretrained Fields of
  The World U-Net over bi-temporal Sentinel-2. It has run: 73.3% of survey points fall
  inside exactly one delineated field, below our 80% gate, and only 20.4% of points
  have a field to themselves (the rest share a field with another point).
- *Fallback:* village-constrained Voronoi tessellation of the survey points, clipped to a
  30 m radius. Built and verified — 14,611 parcels, zero double-counted area, median
  parcel 1,953 m².

**What your geometry would add.** A measured IoU between satellite-delineated fields and
real cadastral boundaries for this taluk. That number answers a question we think is
valuable to FarmwiseAI independently of this challenge: *how far can satellite delineation
substitute for survey geometry in Tamil Nadu smallholder systems?* We would report it
whichever way it comes out.

**Format:** shapefile or GeoJSON, parcel polygons keyed by village code, survey number and
subdivision so they join to `parcel_id`. EPSG:4326 or any stated CRS.

---

## 2. The survey photographs behind `image_path`

**Why we are asking.** The ground-truth CSV carries an `image_path` per record, but not the
images. Phase 0 established that these 14,643 records trace to only 3,204 photographs, and
that each photograph sits a median 1,436 m from the parcel it documents. Those two facts
are the foundation of our audit. The images themselves would let us close the loop.

**What they would unlock (AI-6).** A vision-language model checking each photograph against
the declared crop and stage — independent multimodal evidence for or against the survey
record, rather than satellite-only inference. It would also let us test directly whether
the photo-to-parcel distance we measured reflects a geotagging artefact or something about
how the survey was conducted, which we currently cannot distinguish.

**What we have done instead.** AI-6 is marked conditional throughout `plan.md`. The Record
Trust Score works without it, using capture-event bag size, photo distance, MIL attention,
stage plausibility, mixed-crop declarations, geometry source and within-parcel
heterogeneity.

**Format:** the image files, keyed by the `image_path` values already in the CSV. A sample
of a few hundred across crops and villages would be enough to validate the approach; the
full set would let us run it at scale.

---

## 3. Confirmation of the 911/912 (Viswanathaperi) village boundary

**Why we are asking.** 1,930 of 14,611 survey records fall inside a different village
polygon than the village code they carry (`docs/evidence/p7_registry.json` →
`attribution_test.pair_geometry`). The mismatch is concentrated in one pair of polygons,
Viswanathaperi Part-1 (911) and Part-2 (912):

| Recorded code | Inside polygon 911 | Inside polygon 912 |
|---|---:|---:|
| 911 | 398 | 720 |
| 912 | 1,175 | 0 |

Every record coded 912 lies inside polygon 911, and polygon 912 contains none of them.

**What we can and cannot say.** The geometry suggests a boundary or labelling error in the
supplied village layer. It does not prove it. We first argued that
the Agrisnet registry settled the question because it agrees with the recorded codes; that
argument was circular, since the registry is compiled from those same recorded codes, and
we have retracted it (correction #22 in `docs/team/13_CORRECTIONS.md`). Neither the survey
records nor the boundary layer is shown to be wrong. Mismatches like this are inherent when
boundary layers and field records are produced separately at national scale, and nothing
downstream flags them today; flagging them is what the audit is for.

**What we have done instead.** We report the discrepancy as an open question, with the
counts above, and keep the pair figures separate from the taluk-wide ones: across all 21
villages, registry-versus-satellite mean |Δ share| is 0.0569 by recorded code against 0.0655
by polygon (`attribution_test`), so the gap is a two-village effect.

**What would settle it.** Cadastral records for the two parts (FMB sheets or the authoritative revenue
village boundary), or a field check of
a small sample of the 1,175 records coded 912. Either would tell us which attribution is
correct, and whether the fix belongs in the layer or in the records.

**Format:** the authoritative polygons for revenue villages 911 and 912 in any stated CRS,
or a yes/no on a list of sample `parcel_id`s we would supply.

---

## Handling

We treat all three as `SUPPLIED` under our provenance scheme (`KAVAL/data/PROVENANCE.md`):
recorded, never redistributed, and clearly distinguished in all outputs from data we
sourced ourselves — as the challenge brief requires. None would be published in any
repository or demo artefact.

## Also useful, lower priority

- **Village-level crop registry figures** for Sivagiri, if FarmwiseAI holds them in a form
  more current than the TN Department of Economics & Statistics *Season & Crop Report*. The
  brief's "compare against the supplied registry" query is easier to answer well with an
  authoritative source.
- **Actual surveyor productivity figures** (parcels visited per surveyor-day). Our
  cost-saving estimate currently assumes 25 parcels/day, inferred from 3,204 capture events
  across an 8-day survey window in 21 villages. The assumption is stated wherever the
  saving is reported, but your real figure would replace a guess with a number.
