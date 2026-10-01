---
name: data-provenance
description: How KAVAL records the origin, licence and transformation of every acquired data file. Load whenever downloading, exporting, scraping, generating or transforming a dataset, or before using an acquired file in the feature store. Triggers: "download", "acquire", "export", "dataset", "provenance", "licence", "source", "GEE export", "data/".
---

# Data Provenance

The supplied files are a small reference sample. Everything else KAVAL uses is acquired
independently, so the chain of custody has to be explicit — this is what lets FarmwiseAI
distinguish their resources from ours, which the challenge brief requires.

## Rule

**An acquired file without a `data/PROVENANCE.md` entry does not exist.** Do not load it,
do not join it, do not feature-engineer from it.

## Entry format

Append to `data/PROVENANCE.md`:

```markdown
### data/raw/gse_annual_2024_sivagiri.tif
- **Source:** Google Earth Engine, `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`
- **Acquired:** 2026-10-04 by `data-acquisition` agent
- **Licence / terms:** Google Earth Engine terms; CC-BY-4.0 attribution to Google DeepMind
- **Spatial extent:** Sivagiri taluk AOI, derived from supplied Taluk_boundary.geojson
- **Temporal extent:** annual composite, calendar 2024
- **CRS:** EPSG:4326
- **Transform applied:** none (raw export)
- **Produced by:** scripts/acquire_gse.py
- **SHA256:** <hash>
- **Notes:** 64 bands, 10 m. Unit-length embeddings.
```

## Required fields

Source · Acquired (date + agent) · Licence · Spatial extent · Temporal extent · CRS ·
Transform applied · Produced by (script path) · SHA256 · Notes.

## Classification

Tag every entry as one of:

- `SUPPLIED` — given by FarmwiseAI. Never redistribute; never publish credentials.
- `ACQUIRED` — sourced independently from a public/permitted source.
- `DERIVED` — produced by our own scripts from the above. Record its inputs.

The final deliverable must be able to answer "where did this number come from" for any
cell on screen.

## Never

- Commit FarmwiseAI-supplied restricted data or credentials to a public repository.
- Use a source whose terms forbid the use. Check before acquiring, not after.
- Transform a file in place without recording the transform.
