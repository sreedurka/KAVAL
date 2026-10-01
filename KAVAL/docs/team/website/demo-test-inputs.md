# KAVAL live demo: tested inputs

**For:** M1–M4, demoing KAVAL live to FarmwiseAI reviewers.
**Purpose:** a script of inputs that were each run against the live system on **2026-10-01**
and kept only where the result was good. Nothing in this file is untested.

**How it was tested.** API on `127.0.0.1:8077`, UI on `127.0.0.1:5173`, default thresholds
(`confidence_high=0.80`, `trust_floor=0.35`, `trust_high=0.65`) unless a step says otherwise.
Every analyst question went through `POST /analyst/query`, at least 15 s apart. Each answer was
then graded by re-running the same tool calls through `KAVAL.api.analyst.dispatch()` and
checking every number in the answer against the tool payloads, using the number check from
`KAVAL/scripts/p7_verify_analyst.py`. Each kept question was also put to the offline
planner (`offline_answer()`).

**Which model answered.** Every live answer on test day came from
**`gemini:gemini-flash-lite-latest`**. `gemini-3.8-flash` and `gemini-3-flash-preview`
returned HTTP 429 (free-tier quota exhausted) on every request, so the fallback chain moved
on to flash-lite each time. On demo day, after the quota resets, the chip may read
`gemini-3.8-flash`. That model is listed first because it is expected to be better, but
**its wording was not tested today**. The tools and figures stay the same; the phrasing will
differ. The figures below come from the tool payloads, not from the model's wording, so they
hold whichever Gemini model answers.

**Revised after fixes (same day).** Live testing exposed analyst gaps. They were fixed:
`crop_area_summary` now takes `village` (no more truncated village tables), new tools
`get_parcel` and `calibration_report`, `query_parcels` gained `declared_crop`, and the system
prompt gained rules on percentiles, UNCERTAIN vs DISPUTED and the worklist ranking. Then 16
previously failing questions were re-run live (again on `gemini-flash-lite-latest`): **11 now
pass** and are listed as **#36–#46** (A.9); the 5 that still fail stay in A.8.

**How to read "split regime".** Model metrics (accuracy, F1, precision, recall) must state
their regime in the answer text, and every kept answer that quotes one does. Operational
counts (statuses, worklist, auto-clear) are derived from the `3-event` model, and their
regime travels on the citation chip under the answer. Point at the chip.

---

## Part A — Analyst page (`#analyst`)

**Tested: 70 phrasings (40 candidates, then 30 rephrasings and probes). Kept: 35.**
Typical response time: **3.4–6.7 s**, with one outlier at 8.1 s. Every number listed under
"expected figures" comes from the live API on 2026-10-01.

### A.0 How to phrase questions so they work

These rules come from the failures observed in testing.

1. **Ask for the output you want to see.** "Show the UNCERTAIN parcels in Cuddalor" got
   *"544 … (showing the first 20 above)"* and no parcel in the text. "List 10 UNCERTAIN
   parcels in Cuddalor with their declared crop, predicted crop and confidence" got a clean
   table.
2. **Name the village exactly as the dropdown lists it**, including ` - Part-1` / ` - Part-2`.
3. **Crop-wise area for a named village works for only eight villages:** Ariyur, Cuddalor,
   Dharugapuram, Inamkovilpatti, Naranapuram - Part-1, Naranapuram - Part-2,
   Nelkattumseval, Patakurichi. For every other village the model receives a truncated
   table and gets it wrong (see A.8). Parcel lists, budgets, registry comparisons and
   exports work for **any** village, because there the filter runs on the server.
4. **Say "below 80% confidence"** (or 50%, 60%, 70%). The model maps this correctly to
   `max_confidence`.
5. **Give budgets as "N field visits".** "Surveyors" also works; the tool counts visits.
6. **Ask "is the targeting efficiency evidence…?"** to get the "pinned by construction"
   caveat. If you ask only "where should we send N visits", the model may quote "5.5× random"
   with no caveat.
7. **Add "to one decimal place" for the ladder.** Without it, flash-lite twice printed
   89.546% as "89.54".
8. **"Coconut parcels" means parcels the satellite predicts as Coconut.** The tool filters on
   the predicted crop and cannot filter on the declared crop. To get representative errors,
   ask for "DISPUTED parcels the satellite predicts as Rice (Paddy)".
9. **Ask "export link" explicitly.** The answer gives a relative URL such as
   `/export?fmt=csv&budget=500`. To open it from the UI, prefix it with
   `http://127.0.0.1:5173/api` (tested: it streams `kaval_parcels.csv`).
10. **Ask one thing per question and leave 10 s between questions.** On the free tier each
    question costs 2–4 model calls. While the bigger models are over quota, each question
    also spends two failing calls before flash-lite answers.

### A.1 Brief requests (the six the challenge lists)

**1. Brief request 1: classify all parcels, area and confidence, low-confidence parcels**
```
Classify all parcels in the study area: show crop-wise cultivated area and mean confidence, and list parcels below 80% confidence that need field verification.
```
- Demonstrates: the first analysis request in the brief, end to end, with cited parcel IDs.
- Tools: `crop_area_summary(group_by=taluk, source=predicted)`, `query_parcels(max_confidence=0.8, limit=10)`
- Expected figures (from the live API on 2026-10-01): Rice (Paddy) 1,523.16 ha, 9,498 parcels,
  mean confidence 0.853 · Coconut 335.68 ha, 2,543, 0.769 · Maize 160.17 ha, 1,488, 0.749 ·
  Sugarcane 71.12 ha, 366, 0.776 · Banana 44.87 ha, 377, 0.586 · Other 2.63 ha, 38, 0.456 ·
  **4,433 parcels below 80%** · first IDs 3_10_1A, 3_10_1B, 3_10_1C …
- Time 6.7 s · **Offline backup: yes** (also adds the status breakdown)
- Do not use the brief's literal wording ("…in the selected study area…"). With that
  wording the model listed no parcels.

**2. Brief request 2: crop-wise area for a village, parcels below 80%**
```
Show crop-wise area for Cuddalor, and list 10 parcels in Cuddalor below 80% confidence with parcel ID, predicted crop and confidence.
```
- Demonstrates: village-level area plus highlighted low-confidence parcels.
- Tools: `crop_area_summary(group_by=village)`, `query_parcels(village=Cuddalor, max_confidence=0.8)`
- Expected figures: Rice (Paddy) 460 parcels / 56.33 ha · Coconut 217 / 21.07 ha · Maize 69 /
  7.32 ha · Banana 24 / 3.13 ha · Sugarcane 9 / 0.65 ha · Other 1 / 0.21 ha · 453 parcels
  below 80% · first: 8_116_15 Coconut 73.6%, 8_118_4 Coconut 41.7%, 8_118_5 Rice 44.0%
- Time 5.8 s · **Offline backup: yes**
- Tested alternative (4.6 s, offline yes): the same sentence with **Nelkattumseval**: Maize
  952 / 106.75 ha · Rice 249 / 25.83 ha · Coconut 26 / 2.51 ha · Banana 21 / 2.48 ha · Other
  7 / 0.67 ha · 599 below 80% · first 9_177_1, 9_177_2, 9_177_5B.
- **Only use one of the eight villages in A.0 rule 3.**

**3. Brief request 3: GSE versus Presto**
```
Compare the performance obtained from Google Satellite Embeddings and Presto embeddings where both are supplied.
```
- Demonstrates: the embedding comparison with its regime, and the "underpowered" discipline.
- Tools: `leakage_ladder`
- Expected figures (regime 3-event): GSE only 81.5% accuracy / macro F1 0.563 · Presto
  74.2% / 0.452 · GSE + Presto 81.3% / 0.559, marked **underpowered (no measurable
  difference)** · caveat: Presto pretrained on L1C, fed L2A.
- Time 4.0 s · **Offline backup: yes.** The offline answer is fuller: it adds the paired
  comparison, Presto behind GSE in 0 of 5 folds.

**4. Brief request 4: villages that differ from the registry**
```
Show villages where predicted crop area differs significantly from the supplied registry.
```
- Demonstrates: registry divergence, and the independence caveat stated unprompted.
- Tools: `compare_to_registry`
- Expected figures: Rayagiri - Part-1 Sugarcane −34.6 points (registry 58.2% vs satellite
  23.6%), Rice +28.4 · Thenmalai - Part-2 Rice +32.6, Sugarcane −22.6 · Inamkovilpatti
  Coconut +23.1, Rice −22.2 · Ariyur Coconut −21.2 · Patakurichi Coconut −20.6 ·
  Dharugapuram Rice +20.6 · Ramanathapuram Sugarcane −20.3 · caveat: "the published
  aggregate of the same Digital Crop Survey … not an independent second survey".
- Time 4.2 s · **Offline backup: yes.** The offline answer adds that "significantly" means
  "largest gap": no significance test is run.

**5. Brief request 5: highest confusion, with representative errors**
```
List the crop classes with the highest confusion, and show DISPUTED parcels the satellite predicts as Rice (Paddy) as representative examples.
```
- Demonstrates: the confusion pairs plus real parcels, phrased as disagreement rather than
  error.
- Tools: `confusion_report`, `query_parcels(status=DISPUTED, crop=Rice (Paddy), limit=5)`
- Expected figures (regime 3-event): Coconut→Rice 457 records · Maize→Rice 388 · Rice→Maize
  320 · Rice→Coconut 280 · Banana→Rice 270 · examples 3_24_17A (surveyed Maize, satellite
  Rice 0.94, trust 0.37), 3_24_17B (0.87), 3_81_7 (0.85), 3_81_8 (0.92), 3_81_9 (0.92), all
  in Inamkovilpatti.
- Time 4.6 s · **Offline backup: yes.** Offline gives Coconut→Rice examples (3_92_3 …) and
  per-class F1 with capture events.
- Do not use the brief's literal wording here either. It produced the pairs and per-class
  metrics but no parcels.

**6. Brief request 6: export layer, confidence, crop-area summary**
```
Export the classified parcel layer, confidence values and crop-area summary.
```
- Demonstrates: export through a tool, not a refusal.
- Tools: `export_layer(fmt=csv)`, `crop_area_summary(group_by=taluk)`
- Expected figures: `/export?fmt=csv`, **14,310 parcels**, plus the six-crop taluk table
  (as in #1, with conflicted area, e.g. Rice 42.84 ha).
- Time 4.0 s · **Offline backup: yes.** Offline gives the CSV and GeoJSON URLs, the
  crop-area URL (90 village×crop rows) and a worklist URL.

### A.2 Worklist and budget

**7. 500 visits, top 5, export link**
```
Where should we send 500 field visits? List the top 5 parcels with declared crop, predicted crop and confidence, plus the export link.
```
- Tools: `route_verification_budget(budget=500)`, `export_layer(fmt=csv, budget=500)`
- Expected figures: 152_399_1 Rayagiri - Part-2, declared Rice (Paddy), predicted Sugarcane,
  0.9708, DISPUTED · 7_176_3 Ramanathapuram Other→Rice 0.8602 · 7_127_1 Ramanathapuram
  Other→Rice 0.9199 · 6_363_4A Thirumalapuram Banana→Rice 0.9222 · 15_137_2 Patakurichi
  Banana→Maize 0.3433 UNCERTAIN · `/export?fmt=csv&budget=500`. Behind it: 390.5 estimated
  corrections against 53.9 for random visits (sd 6.03).
- Time 6.3 s · **Offline backup: yes** (verbose: also lists the layer exports)
- The product question's own wording, "Where should we send 500 surveyors next season?",
  also works (4.7 s). In 1 of 2 runs it mis-rounded 142.834 ha to "142.84". Prefer the
  wording above.

**8. 100 visits against random**
```
Route 100 field visits: how many estimated corrections versus random visits, and which parcels come first?
```
- Tools: `route_verification_budget(budget=100)`
- Expected figures: 78.4 estimated corrections against 10.7 at random (sd 2.6) · the same
  top five as #7.
- Time 4.9 s · **Offline backup: yes**
- The answer says "Targeting efficiency: 5.5 times random" with no caveat. **Add it
  yourself:** the efficiency is capped at 1 ÷ 0.183 = 5.47× by construction, so read the
  corrections, not the multiple.

**9. Budget within one village**
```
Route 200 field visits within Nelkattumseval and list the top 5 parcels.
```
- Tools: `route_verification_budget(budget=200, village=Nelkattumseval)`
- Expected figures: 9_633_12B (priority 3.27, UNCERTAIN), 9_633_14 (3.26), 9_349_13 (3.24,
  DISPUTED), 9_465_2 (3.13), 9_361_1B (3.07). Behind it: 152.8 estimated corrections against
  33.0 at random; reaches 195 of the village's 376 disagreements.
- Time 5.7 s · **Offline backup: yes** (and it states the economics)

**10. 1,000 visits, and does efficiency prove anything**
```
Route 1000 field visits and explain whether the targeting efficiency proves anything.
```
- Tools: `route_verification_budget(budget=1000)`
- Expected figures: 6.99% of parcels, 207.87 ha · efficiency 5.31, "pinned by construction
  … measures coverage, not ranking quality". Behind it: 764.5 estimated corrections against
  108.8.
- Time 4.0 s · **Offline backup: yes**

**11. The honesty question about the lift**
```
At 500 visits, is the targeting efficiency evidence that the ranking is good?
```
- Tools: `route_verification_budget(budget=500)`
- Expected content: "No … measures coverage, not ranking quality … pinned by construction …
  capped at 1 divided by the base disagreement rate". Pair it with the worklist tile:
  routed mean confidence 0.734 against 0.652 across all disagreements.
- Time 4.7 s · **Offline backup: yes** (numbers plus "read the expected-corrections figures,
  not the efficiency")

**12. The walkthrough question (DEMO_WALKTHROUGH §7)**
```
Which villages differ most from the registry, and where should I send 200 surveyors?
```
- Tools: `compare_to_registry(min_registry_ha=1)`, `route_verification_budget(budget=200)`
- Expected figures: Rayagiri - Part-1 Sugarcane −34.6 points and Rice +28.4 · Thenmalai -
  Part-2 Rice +32.6 · independence caveat · about 157 estimated corrections against about 22
  at random (157.26 / 21.96).
- Time 6.0 s · **Offline backup: yes**
- One sentence reads awkwardly ("run the verification routing budget tool"). The figures are
  right.

### A.3 Auto-clear

**13. Product question: stop visiting**
```
Which parcels can we stop visiting?
```
- Tools: `auto_clear_summary`
- Expected figures: **4,825 parcels (33.7%, 870.8 ha)** CONFIRMED · **193.0 of 572.4
  surveyor-days** · assumes 25 parcels per surveyor-day · residual about 7.6% (about 365
  parcels cleared in error), "a rough proxy, not a bound", settle it with a field audit of
  a CONFIRMED sample.
- Time 4.1 s · **Offline backup: yes** (adds sample CONFIRMED IDs and the export URL)

**14.**
```
How many surveyor-days does auto-clearing save next season?
```
- Tools: `auto_clear_summary` · Expected: 193.0 surveyor-days, 4,825 parcels, 33.7%,
  870.8 ha, 25/day, residual 7.6% (about 365) · Time 3.5 s · **Offline: yes**

**15.**
```
What is the residual risk in the auto-cleared parcels?
```
- Tools: `auto_clear_summary` · Expected: 7.6%, about 365.3 parcels cleared in error, "rough
  proxy, not a bound or a guarantee", "cannot be measured against a label the surveyor
  supplied" · Time 3.4 s · **Offline: yes**

### A.4 Validation honesty

**16. Why not 95%**
```
Why is accuracy not 95%? Show the leakage ladder with accuracy to one decimal place.
```
- Tools: `leakage_ladder`
- Expected figures: 1-random 89.7% · 2-parcel 89.5% · **3-event 81.2% (headline regime)** ·
  4-village 70.8% · headline MLP head 81.7% · "95% is only reachable with validation
  leakage".
- Time 4.5 s · **Offline backup: yes**

**17.**
```
Which embedding source works best?
```
- Tools: `leakage_ladder` · Expected (3-event): GSE + seasonal 81.7% / 0.564 and GSE only
  81.5% / 0.563, "no measurable difference (underpowered)"; Presto 74.2% · Time 6.3 s ·
  **Offline: NO.** The offline planner does not recognise it. Use #3 offline instead.

**18.**
```
Which crops are most often confused with Rice (Paddy)?
```
- Tools: `confusion_report` · Expected (3-event): Rice→Maize 320, Rice→Coconut 280,
  Rice→Banana 97; Coconut→Rice 457, Maize→Rice 388, Banana→Rice 270, Sugarcane→Rice 97;
  Rice rests on 2,102 capture events / 8,970 records · Time 4.3 s · **Offline: partial**
  (gives the general top-5 confusion answer)

**19. Effective sample size**
```
How well does the model classify Banana, and how many independent capture events support that?
```
- Tools: `confusion_report` · Expected (3-event): precision 0.440, recall 0.254, F1
  0.322, **64 capture events out of 653 records** · Time 4.7 s · **Offline: NO.** It
  routes to forensics and gives 655 records / 66 events but no F1. The forensics table
  counts all supplied records, the confusion table only the evaluated ones, so both numbers
  are correct.

### A.5 Data quality (ground-truth forensics)

**20.**
```
What is the median photo-to-parcel distance, and what share of photographs were taken over 1 km from the parcel?
```
- Tools: `ground_truth_forensics` · Expected: **median 1,436 m; 62.3% over 1 km** · Time 6.6 s
  · **Offline: yes** (the full forensics paragraph). This is a data description, so no
  split regime applies, and the chip shows none.

**21.**
```
How many capture events are in the ground truth, and what is the label inflation factor?
```
- Tools: `ground_truth_forensics` · Expected: **3,204 capture events; inflation 4.57**
  (14,643 records) · Time 3.8 s · **Offline: yes**

### A.6 Status and villages

**22.**
```
Give me the agreement status breakdown for the taluk.
```
- Tools: `status_summary` · Expected: CONFIRMED 4,825 (870.8 ha) · DISPUTED 784 (100.8 ha) ·
  UNCERTAIN 8,429 (1,143.0 ha) · UNVERIFIABLE 272 (23.0 ha), each with its meaning ·
  Time 3.9 s · **Offline: yes**

**23. What UNVERIFIABLE means**
```
What does UNVERIFIABLE mean, and how many parcels are UNVERIFIABLE?
```
- Tools: `status_summary` · Expected: "the survey record itself is too weak to test … the
  problem lies in the evidence, not in the field"; **272 parcels, 23.0 ha** · Time 3.5 s ·
  **Offline: partial** (gives 272 and IDs but closes with the DISPUTED definition)

**24.**
```
How many DISPUTED parcels are there in Thenmalai - Part-1? List some of them.
```
- Tools: `query_parcels(status=DISPUTED, village=Thenmalai - Part-1)` · Expected: **60** ·
  141_22_1A surveyed Banana, satellite Rice 0.92, trust 0.62 · 141_22_1C 0.95 · 141_32_1
  0.99, trust 0.72 · 141_695_3B surveyed Coconut, satellite Rice 0.95 · Time 4.4 s ·
  **Offline: yes**

**25. Why records are UNVERIFIABLE**
```
Which parcels in Nelkattumseval are UNVERIFIABLE, and why?
```
- Tools: `query_parcels(status=UNVERIFIABLE, village=Nelkattumseval)` · Expected: **43
  parcels** · trust below the 0.35 floor · bags of up to 25 parcels per capture event ·
  photographs over 2 km away (the highest of the 20 returned is about 3.0 km) · Time 4.1 s
  · **Offline: NO** (it answers crop area instead)

**26. Ties to the map demo (B.1)**
```
Which DISPUTED parcels in Rayagiri - Part-2 have the highest confidence?
```
- Tools: `query_parcels(status=DISPUTED, village=Rayagiri - Part-2)` · Expected: **6**,
  ordered 399/1 0.97 (Rice→Sugarcane) · **219/4 0.96 (Sugarcane→Rice)** · 219/6A 0.92 ·
  112/2 0.86 · 144/3C2 0.82 · 224/4 0.82 · Time 4.9 s · **Offline: NO**

**27.**
```
How many parcels in Inamkovilpatti are below 50% confidence? List 5.
```
- Tools: `query_parcels(village=Inamkovilpatti, max_confidence=0.5, limit=5)` · Expected:
  **31** · 120/3 Coconut 42% UNCERTAIN · 24/1B 48% UNVERIFIABLE · 24/1C 46% · 24/5B 48%
  UNVERIFIABLE · 24/5C 15% · Time 4.8 s · **Offline: yes** (lists 10, plus the crop area)

**28. Registry, one village**
```
How does Rayagiri - Part-1 compare with the registry?
```
- Tools: `compare_to_registry(village=Rayagiri - Part-1)` · Expected: Rice registry 39.35%
  vs satellite 67.73% (+28.38 points) · Sugarcane 58.22% vs 23.65% (−34.57) · Coconut 2.43%
  vs 6.01% (+3.57) · independence caveat · Time 3.6 s · **Offline: yes** (adds the taluk
  bias by crop)

**29.**
```
Compare the crop mix of Patakurichi with the registry.
```
- Tools: `compare_to_registry(village=Patakurichi)` · Expected: Coconut 70.57% (237.9 ha) vs
  49.99% (−20.58 points) · Banana 12.76% vs 22.35% (+9.59) · Rice 16.67% vs 16.68% (+0.01) ·
  caveat · Time 3.8 s · **Offline: yes**

**30.**
```
Which crop covers the most area, and how confident is the satellite about it?
```
- Tools: `crop_area_summary(group_by=taluk)` · Expected: Rice (Paddy) 1,523.16 ha, 9,498
  parcels, mean calibrated confidence 0.853 · Time 5.8 s · **Offline: NO**

**31. Trust, not the model, can hold a parcel back**
```
List 10 UNCERTAIN parcels in Cuddalor with their declared crop, predicted crop and confidence.
```
- Tools: `query_parcels(village=Cuddalor, status=UNCERTAIN, limit=10)` · Expected: 8_116_1
  … 8_116_8B, all declared Coconut, predicted Coconut, confidence 0.82–0.95 (544 UNCERTAIN in
  total) · Time 5.8 s · **Offline: NO**
- **Say this, because the model will not:** these parcels agree at 92% and are still
  UNCERTAIN, because the record's trust is below `trust_high` 0.65 (8_116_1 has trust
  0.507). Agreement on a weak record cannot auto-clear.

**32.**
```
List 10 Coconut parcels below 60% confidence, with village and declared crop.
```
- Tools: `query_parcels(crop=Coconut, max_confidence=0.6, limit=10)` · Expected: 3_10_1E
  (declared Coconut, 56.2%), 3_120_3 (41.7%), 3_24_1D (declared Maize, 52.5%) … all
  Inamkovilpatti; 493 in total · Time 6.0 s · **Offline: NO**
- "Coconut" here means **predicted** Coconut. Rows whose declared crop is Maize are the
  disagreements.

### A.7 Export

**33.**
```
Export the DISPUTED parcels as CSV.
```
- Tools: `export_layer(fmt=csv, status=DISPUTED)` · Expected: `/export?fmt=csv&status=DISPUTED`,
  **784 rows** · Time 8.1 s · **Offline: yes**

**34.**
```
Download the routed field worklist for 300 visits.
```
- Tools: `export_layer(fmt=csv, budget=300)` · Expected: `/export?fmt=csv&budget=300`, **300
  rows**, ordered by priority · Time 3.7 s · **Offline: yes**

**35.**
```
Export Thirumalapuram's parcels as GeoJSON.
```
- Tools: `export_layer(fmt=geojson, village=Thirumalapuram)` · Expected:
  `/export?fmt=geojson&village=Thirumalapuram`, **1,355 parcels** · Time 4.3 s · **Offline: yes**

Export and summary URLs in an answer are rendered as **clickable links** (through the UI's
`/api` proxy), so clicking `/export?fmt=csv&budget=300` in the answer downloads the file. To
type one by hand: `http://127.0.0.1:5173/api` + the URL, e.g.
`http://127.0.0.1:5173/api/export?fmt=csv&budget=300`.

### A.8 Questions to AVOID live

Re-tested after the fixes (2026-10-01, `gemini-flash-lite-latest`). These still fail or are
weak; do not improvise them in front of reviewers.

| Question (as tested) | What went wrong | Use instead |
|---|---|---|
| "Where should we send 100 field visits?" | Figures correct and grounded (78.43 estimated vs 10.73 random), but it told the user to "call `export_layer`" instead of calling it and giving the link. | #7–#11, or add "and give me the download link" |
| "Route a budget of 200 visits within Thirumalapuram." | Quoted "targeting efficiency 4.28×" as a plain result, without the capped-by-construction caveat. | #9 |
| "List the crop classes with the highest confusion and show representative errors." (the brief's literal wording) | Accurate confusion counts and effective n, but **no representative parcels**. | #5, or #45 for one pair |
| "Is the registry comparison independent validation?" | Right answer, but it **called no tool**, so it carries no citation. | #28 (the caveat comes from the tool) |
| "Show crop-wise area for the selected village…" | The analyst has no "selected village"; name the village. | #36–#40 |

**Fixed by the changes above (now in A.9):** named-village crop area (it used to fail on most
villages, because the model saw a truncated table), parcel lookup ("not found" before),
calibration (improvised before), photo-distance percentiles (misread before), the headline
regime question (mixed up the LightGBM ladder and the MLP headline before), a confusion pair
by declared and predicted crop, and the DISPUTED question (misstated the ranking before).

### A.9 Re-verified after the fixes (2026-10-01)

Each was run live on `gemini-flash-lite-latest`; every figure below is from the tool
payloads. **All 11 also answer correctly offline** (Offline: yes).

**36.**
```
Show crop-wise area for Thirumalapuram and highlight parcels below 80% confidence.
```
- Tools: `crop_area_summary(village=Thirumalapuram)`, `query_parcels(village, max_confidence=0.8)`
  · Expected: Rice (Paddy) 210.56 ha / 1,083 parcels, Coconut 37.67 ha / 235, Sugarcane 3.92,
  Banana 2.99, Maize 0.10; **501 parcels below 80%**, correctly called UNCERTAIN (never
  DISPUTED) · Time ≈ 14 s · Offline: yes

**37.**
```
Show the crop-wise satellite-estimated area for Viswanathaperi - Part-1 village.
```
- Tools: `crop_area_summary(village=…)` · Expected: Rice (Paddy) 235.094 ha / 1,050 parcels,
  Coconut 96.724 ha / 497, Banana 2.914, Sugarcane 0.229, Other 0.000 · Time ≈ 3 s · Offline: yes

**38.**
```
Show the crop-wise satellite-estimated area for Rayagiri - Part-2 village.
```
- Expected: Rice (Paddy) 225.69 ha / 950 parcels, Sugarcane 9.64 ha / 19, Coconut 1.97 ha / 6
  · Time ≈ 2 s · Offline: yes

**39.**
```
Show the crop-wise satellite-estimated area for Ramanathapuram village.
```
- Expected: all **6** crops: Coconut 59.25 ha / 648, Rice (Paddy) 19.47 / 209, Banana 2.79 / 33,
  Sugarcane 1.55 / 20, Other 0.39 / 5, Maize 0.00 / 1 · Time ≈ 3 s · Offline: yes

**40.**
```
Show crop-wise area for Nelkattumseval and highlight parcels below 80% confidence.
```
- Expected: Maize 106.74 ha / 952 parcels, Rice (Paddy) 25.83 / 249, Coconut 2.51, Banana 2.48,
  Other 0.67, with conflicted area per crop; **599 parcels below 80%** (UNCERTAIN), examples
  9_177_1, 9_177_6B, 9_198_7 · Time ≈ 5 s · Offline: yes

**41.**
```
Tell me about parcel 9_440_2.
```
- Tools: `get_parcel` · Expected: Nelkattumseval 440/2; declared Rice (Paddy), predicted Maize;
  **DISPUTED** at 97.1% calibrated; trust 0.87; P(needs correction) 0.82; photo **12.8 m**
  away, 1 parcel on the photograph. The best "clean record, real disagreement" example ·
  Time ≈ 3 s · Offline: yes

**42.**
```
Tell me about parcel 152_399_1.
```
- Expected: Rayagiri - Part-2 399/1; declared Rice (Paddy), predicted Sugarcane; DISPUTED at
  97%; trust 0.85; 1.72 ha; photo 743 m away. Row 1 of the worklist. (Its answer once said
  "from the field edge"; the figure is the distance from the photograph to the parcel.) ·
  Time ≈ 3 s · Offline: yes

**43.**
```
How well calibrated is the model's confidence?
```
- Tools: `calibration_report` · Expected: raw mean confidence 94.2% vs actual accuracy 81.7%
  (regime 3-event), ECE 0.125 → 0.005 after isotonic calibration · Time ≈ 2 s · Offline: yes

**44.**
```
How far are the survey photographs from the parcels they document?
```
- Tools: `ground_truth_forensics` · Expected: median 1,436 m; p75 2,436 m read correctly ("75%
  at or below"); p90 3,808 m; max 8,559 m; 62.3% over 1 km · Time ≈ 3 s · Offline: yes

**45.**
```
Show representative parcels surveyed as Banana but predicted as Coconut.
```
- Tools: `query_parcels(declared_crop=Banana, crop=Coconut)` · Expected: **139** parcels;
  6_214_1 and 6_761_1 (Thirumalapuram, DISPUTED, 0.94) · Time ≈ 3 s · Offline: yes. Works for
  any pair, e.g. "declared Maize but predicted as Rice" → 388.

**46.**
```
What is the model's headline accuracy, and under which split regime?
```
- Tools: `leakage_ladder` · Expected: **81.71%** accuracy, macro F1 0.564, regime **3-event**
  (MLP) · Time ≈ 2 s · Offline: yes. (Also good: "How many parcels are DISPUTED, and what
  should we do with them?" → 784 parcels, 100.8 ha, top of the worklist.)

---

## Part B — Click paths for the other pages

All figures: live API, 2026-10-01, default thresholds unless stated. Status totals at the
defaults are **CONFIRMED 4,825 · DISPUTED 784 · UNCERTAIN 8,429 · UNVERIFIABLE 272**.

### B.1 Audit map (`#map`)

**Path 1: a disagreement beside an agreement (Rayagiri - Part-2)**
1. Open `#map`. Village → **Rayagiri - Part-2** (975 polygons: 537 CONFIRMED, 432 UNCERTAIN,
   6 DISPUTED). Colour by → **agreement status**.
2. In the **Legend** card, click **CONFIRMED** and **UNCERTAIN** to hide them. Six DISPUTED
   polygons remain.
3. Hover the pair on survey 219 (about 9.3096 N, 77.4146 E) and click **152_219_4**:
   - Declared **Sugarcane**, predicted **Rice (Paddy)**, calibrated confidence **96.3%**
     (raw 99.996%, which shows the calibration gap), P(declared label is wrong) 81.7%,
     suggested correction Rice (Paddy)
   - Trust **0.906** · 5 parcels shared this photograph · photo taken **71 m** away ·
     geometry `ftw`, its own field (1 legal parcel) · stage full_growth · 0.19 ha
4. Click CONFIRMED back on. Its neighbour **152_219_2** is CONFIRMED: declared and predicted
   Rice (Paddy), 97.1%, trust 0.923, photo 73 m. **152_219_6A** next door is also DISPUTED
   (Sugarcane→Rice, 0.92).
   **Say:** "Three subdivisions of one survey number. The surveyor recorded rice on one and
   sugarcane on two. The satellite sees rice on all three, and the record is a good one:
   high trust, photo 71 m away. That is a high-value visit, and a field visit decides which
   is right."

**Path 2: the best-documented disagreement (Nelkattumseval)**
1. Village → **Nelkattumseval** (1,255 parcels: 942 UNCERTAIN, 154 CONFIRMED, 116 DISPUTED,
   43 UNVERIFIABLE). Hide everything except DISPUTED.
2. Click **9_440_2** (about 9.2393 N, 77.4750 E): declared **Rice (Paddy)**, predicted
   **Maize** at **97.1%**, trust **0.874**, **1** parcel in its capture event, photograph
   **13 m** away, geometry `voronoi`, 0.28 ha.
   **Say:** "The photograph was taken on the spot and covers only this parcel. This is the
   strongest record we have, and the satellite still disagrees."
3. **CONFIRMED example**, same village: **9_478_1** (about 9.2337 N, 77.4691 E). Maize/Maize,
   88.4%, trust 0.858, bag 5, photo 58 m, own `ftw` field, P(wrong) 0%. → "Auto-clear next
   season."
4. **UNVERIFIABLE example**, same village: show only UNVERIFIABLE (43 hatched polygons). The
   9_580 cluster is one bag. Click **9_580_14A** (about 9.2163 N, 77.4774 E): declared Maize,
   predicted Rice (Paddy) at only 52.5%, **trust 0.231**, which is below the 0.35 floor. Why
   the record is too weak to test:
   **24 parcels** share this photograph, the photo is **2.01 km** away, the capture-event
   field holds **two** event IDs (a multivalued photo coordinate), and the geometry is a
   `voronoi` fallback. **Say:** "UNVERIFIABLE is about the evidence, not the field. The
   action is to re-survey the record."

**Path 3: one photograph labelling a bag (Ramanathapuram)**
1. Village → **Ramanathapuram** (916: 703 UNCERTAIN, 101 CONFIRMED, 91 DISPUTED, 21
   UNVERIFIABLE). Hide everything except DISPUTED.
2. Click **7_20_2A** (about 9.2935 N, 77.4203 E): declared **Banana**, predicted **Coconut**
   at **97.1%**, trust **0.864**, bag **3**, photo 236 m. Its bag-mates 7_20_2B (98.6%,
   trust 0.77) and 7_20_3 (97.1%, trust 0.71) sit next to it and are also DISPUTED
   Banana→Coconut.
   **Say:** "One photograph supplied the Banana label for all three parcels. Banana↔Coconut
   is a confusion pair we report (139 records), so this is a case to send someone to, not a
   verdict."

Other map controls: **Export GeoJSON / Export CSV** (top right) export the selected village,
e.g. Rayagiri - Part-2, 975 rows. **Colour by → crop class (secondary)** shows a warning chip
saying the audit reads off status. Deep link: `#map?village=Rayagiri%20-%20Part-2`.

### B.2 Village audit (`#villages`)

Defaults: Minimum registry area **1 ha**, all crops, all villages. Tiles: **Registry compared
"Rabi 2024"** · **Village x crop rows 76** (of 76; 90 at 0 ha) · **Registry area outside our
scope 8.8%**. Read the two caveat boxes aloud: not independent validation; share, not
hectares.

The three largest divergences (percentage points of village crop share):

| Village · crop | Registry | Satellite | Δ | Parcels | Mean conf. |
|---|---:|---:|---:|---:|---:|
| Rayagiri - Part-1 · Sugarcane | 58.2% | 23.6% | **−34.6** | 85 | 82.3% |
| Thenmalai - Part-2 · Rice (Paddy) | 19.8% | 52.3% | **+32.6** | 382 | 72.9% |
| Rayagiri - Part-1 · Rice (Paddy) | 39.4% | 67.7% | **+28.4** | 245 | 84.3% |

**Say:** "In Rayagiri - Part-1 the registry says 58% sugarcane. The satellite sees 24%
sugarcane and correspondingly more rice. The two bars mirror each other, so this looks like
sugarcane and rice being traded, not random noise. Neither side is assumed correct, and the
registry is compiled from the same survey."

Filters to set:
- **Crop → Sugarcane.** 11 of 13 rows are negative: Rayagiri - Part-1 −34.6, Thenmalai -
  Part-2 −22.6, Ramanathapuram −20.3, Dharugapuram −16.9. The exception is Sivagiri - Part-2
  at +9.5. The **Systematic bias by crop** card shows Sugarcane **−6.5 points** taluk-wide,
  Rice **+3.6**, Maize +2.1, Coconut −0.7, Banana −0.1.
- **Village → Thenmalai - Part-2:** Rice +32.6, Sugarcane −22.6, Coconut −10.4, Banana +0.7,
  Maize −0.2.

### B.3 Field worklist (`#worklist`)

Slider range 10–5,000, step 10. Tile values at default thresholds:

| N | Corrections, KAVAL | Random (sd) | % parcels · area | Ranking quality | Disagreements in queue | Targeting |
|---:|---:|---:|---|---|---:|---:|
| 100 | **78.4** | 10.7 (2.63) | 0.70% · 52.3 ha | 0.758 vs 0.652 | 100 / 100 | 5.47× |
| 500 (default) | **390.5** | 53.9 (6.03) | 3.49% · 142.8 ha | 0.734 vs 0.652 | 498 / 500 | 5.45× |
| 2,000 | **1,494.5** | 218.4 (10.49) | 13.98% · 264.8 ha | 0.708 vs 0.652 | 1,882 / 2,000 | 5.15× |
| 5,000 (max) | **1,569.7** | 547.9 (15.17) | 34.94% · 665.5 ha | 0.727 vs 0.652 | 2,300 / 5,000 | 2.52× |

The cap is 5.47× (1 ÷ 0.183) at every N. **Say:** "Targeting sits at its cap by construction,
so it is not a result. The informative numbers are the corrections against random and the
ranking-quality tile." Then drag from 2,000 to 5,000: corrections rise by only about 75,
because only 2,617 disagreements exist. That is where the budget stops paying.

**Top 3 at N = 500** (the queue table):
1. **152_399_1**, Rayagiri - Part-2, DISPUTED, declared Rice (Paddy), satellite Sugarcane,
   P(wrong) 82%, confidence 97%, trust 0.85, bag 1, photo 743 m, 1.72 ha
2. **7_176_3**, Ramanathapuram, DISPUTED, Other → Rice (Paddy), 82%, 86%, trust 0.68, bag 3,
   1.53 km, 1.08 ha
3. **7_127_1**, Ramanathapuram, DISPUTED, Other → Rice (Paddy), 82%, 92%, trust 0.53, bag 13,
   2.75 km, 0.70 ha

Many parcels share the same P(wrong): 176 of the 500 sit at 0.817, the calibrated ceiling.
Within that ceiling, the area weight sets the order. Say so if asked "why is this one first".

**Village filter demo:** Village → **Nelkattumseval**, N = **100**: 78.7 against 16.6 at
random (sd 2.74), 7.97% of the village's parcels, 20.7 ha, ranking quality 0.783 vs 0.667,
100 of 100 routed are disagreements (376 available), targeting 3.34×, because the village's
own base rate is 30%. Top 3: 9_633_12B (Maize declared, Banana predicted, 54.5%,
UNCERTAIN), 9_633_14 (same), 9_349_13 (Rice declared, Maize predicted, 81.8%, DISPUTED).

**Export buttons:** "Export CSV" and "Export GeoJSON" export exactly the queue on screen:
same N, same order, same thresholds, same village.

**Do not claim** the worklist tiles move with the threshold sliders. Tested: at N = 500 they
stay 390.5 / 53.9 / 0.734 at every threshold setting in B.6. Only the Status column of
the queue changes, because routing uses P(needs correction), not the status.

### B.4 Auto-clear (`#autoclear`)

At the defaults: **Parcels safe to skip 4,825** (33.7% of parcels, 870.8 ha) ·
**Surveyor-days saved 193.0**, against a baseline of 572.4 days · **Expected residual error
rate 7.6%**, with "≈365 of the 4,825 cleared parcels are expected to be cleared in error".
Cost assumption: 25 parcels per surveyor-day, an assumption to revise with FarmwiseAI's
actuals.

Moving the right-rail sliders (from `/audit/auto-clear` and `/audit/status-summary`):

| Setting | CONFIRMED (skip) | % | Surveyor-days | Residual |
|---|---:|---:|---:|---|
| Defaults 0.80 / 0.35 / 0.65 | 4,825 | 33.7% | 193.0 | 7.6% (≈365) |
| confidence_high → **0.90** | 3,761 | 26.3% | 150.4 | 5.2% (≈196) |
| confidence_high → **0.70** | 5,248 | 36.7% | 209.9 | 9.0% (≈474) |
| trust_high → **0.80** | 1,056 | 7.4% | 42.2 | 7.7% (≈81) |

**Say:** "Tightening confidence buys a lower residual rate at the cost of fewer days saved.
It is a policy dial, and the people who own the budget set it." Volunteer the weakness from
the page: accuracy within the cleared set is 100% by construction, so the residual is a
proxy only a field audit can settle.

### B.5 Leakage Ladder (`#validation`)

Tiles: **Headline accuracy 81.7%** (3-event, head MLP) · **Headline macro F1 0.564** ·
**Cost of honesty 18.9 pp** (1-random → 4-village).

| Split regime | Accuracy | Macro F1 | Log loss |
|---|---|---:|---:|
| 1-random | 89.7% ± 0.4% | 0.772 | 0.343 |
| 2-parcel | 89.5% ± 0.5% | 0.769 | 0.343 |
| **3-event ★** | **81.2% ± 2.2%** | **0.528** | 0.823 |
| 4-village | 70.8% ± 9.5% | 0.326 | 1.459 |

(The ★ row is the LightGBM ladder head; the headline tile is the MLP head on the same
3-event folds.)

- **Model heads (3-event):** LightGBM 81.2 / 0.528 · RandomForest 79.1 / 0.469 ·
  LogisticRegression 80.6 / 0.537 · MLP 81.7 / 0.564.
- **Feature sources (3-event):** GSE only 81.5 / 0.563 · Seasonal S1/S2 73.7 / 0.399 · GSE +
  seasonal 81.7 / 0.564 · Presto 74.2 / 0.452 · GSE + Presto 81.3 / 0.559. Against GSE
  (macro F1): Presto −0.111, 0 of 5 folds ahead · GSE + Presto −0.004, 1 of 5,
  **underpowered: within fold noise** · GSE + seasonal +0.001, 2 of 5, underpowered. (The
  table also lists the accuracy comparisons, although its caption says macro F1.)
- **Per-class (records / capture events, F1):** Rice 8,970 / 2,102, 0.89 · Coconut 2,566 /
  463, 0.77 · Sugarcane 429 / 117, 0.72 · Maize 1,560 / 159, 0.69 · Banana **653 / 64**, 0.32
  · Other 132 / 16, 0.00.
- **Calibration (3-event):** ece_raw 0.1247 → ece_calibrated **0.0046** · mean confidence
  raw 0.9418 → calibrated 0.8170 · actual accuracy 0.8171.
- **Forensics tiles:** 14,643 → 3,204 records → capture events (4.57× inflation; up to 43
  per photograph) · median photo distance **1,436 m** (p90 3,808 m; 62.3% over 1 km) ·
  capture events with a mixed crop label **0**.

### B.6 Threshold rail (right side; any tab)

The rail re-derives the map, the status table and auto-clear through one API call path.
Click **Reset to API defaults** between settings. A "moved from config" chip shows while you
are off the defaults.

| Setting | CONFIRMED | DISPUTED | UNCERTAIN | UNVERIFIABLE |
|---|---:|---:|---:|---:|
| Defaults (0.80 / 0.35 / 0.65) | 4,825 | 784 | 8,429 | 272 |
| **confidence_high 0.90** | 3,761 | **405** | 9,872 | 272 |
| **trust_floor 0.50** | 4,825 | 604 | 6,737 | **2,144** |
| confidence_high 0.95 | 1,465 | 122 | 12,451 | 272 |

Best two to show on the Audit map's status table:
1. **trust_floor 0.35 → 0.50.** UNVERIFIABLE jumps from 272 to 2,144 while CONFIRMED stays
   4,825. "How strict we are about evidence decides how many records we can even test."
2. **confidence_high 0.80 → 0.90.** DISPUTED halves (784 → 405) and auto-clear falls to
   3,761 / 150.4 days. "Fewer, surer disputes, and fewer days saved."

---

## Part C — Pre-demo checklist

### C.1 Start everything

**On the Windows demo laptop:** double-click `run.cmd` in the package folder and paste the
Gemini key when asked. It starts the API pinned to Gemini, then the offline planner, opens
the browser, and never writes the key to disk. See `WINDOWS_SETUP.md`. On Linux:

```bash
cd /home/user/Downloads/FM_AI

# API on 8077 (port 8000 belongs to another app; leave it alone)
GEMINI_API_KEY=<your key> KAVAL_LLM_PROVIDER=gemini \
  .venv/bin/uvicorn KAVAL.api.main:app --port 8077

# UI on 5173 (second terminal)
cd /home/user/Downloads/FM_AI/KAVAL/frontend && npm run dev

# Optional: local open-weight model on 8078 (slow: 1–3 min per question on this CPU)
/home/user/Downloads/FM_AI/KAVAL/scripts/serve_local_llm.sh
```

Never paste the key into a slide, a terminal that is being screen-shared, or a doc.

**Why `KAVAL_LLM_PROVIDER=gemini`?** Per `KAVAL/api/llm.py` `candidates()`, this pins the
chain to Gemini's three models and then the offline planner. Without it the chain also
contains the local Qwen model, which runs **before** offline. If Gemini fails mid-demo, every
question would then hang for 1–3 minutes on the CPU model. We checked this by reading the
code, not by restarting the API: the API was already running with its own key, and we did
not restart it.

**Do not burn the quota rehearsing.** On test day `gemini-3.8-flash` and
`gemini-3-flash-preview` were already over their free quota, and every answer came from
`gemini-flash-lite-latest`. Rehearse with the offline planner (C.3) and save the Gemini
quota for the demo.

### C.2 Confirm the analyst is on an LLM

1. Open `#analyst`. The tools card reads "planner: LLM · first in the fallback chain:
   gemini:gemini-3.8-flash". That is the **first** model in the chain, not necessarily the one
   that answers.
2. Ask #22. The chip **on the answer** names the model that actually answered. On test day it
   read `LLM · gemini:gemini-flash-lite-latest`. Either Gemini chip is fine.
3. Expand the tool-calls drawer: you should see `status_summary`, and a citation chip with
   `split_regime 3-event`.

### C.3 If it says "offline planner — not LLM"

That means no LLM was reachable. The answer's note says which providers failed. Say so
plainly ("this answer was routed by keywords to the same tools; it is not LLM planning") and
continue with the questions marked **Offline backup: yes**: #1–#16, #18 (partial), #20–#24,
#27–#29, #33–#46. Skip #17, #19, #25, #26, #30, #31, #32. Offline answers are longer and
templated, but every figure in them comes from the same tools.

To force offline deliberately (rehearsal, or Gemini down), restart the API with
`KAVAL_LLM_PROVIDER=offline` in place of `gemini`.

### C.4 60-second smoke test

This machine has no `curl`; use `wget`.

```bash
# 1. API is KAVAL and every phase is present
wget -qO- http://127.0.0.1:8077/health
#    expect {"status":"ok","phases_available":{"audit":true,"p4":true,"p5":true,"p6":true}}

# 2. Which planner and chain
wget -qO- http://127.0.0.1:8077/analyst/tools | .venv/bin/python -c \
  "import json,sys; d=json.load(sys.stdin); print(d['planner'], d['provider'], d['fallback_chain'])"
#    expect: llm gemini:gemini-3.8-flash [...gemini models..., 'offline']

# 3. One live question end to end
wget -qO- --header='Content-Type: application/json' \
  --post-data='{"question":"Give me the agreement status breakdown for the taluk."}' \
  http://127.0.0.1:8077/analyst/query | .venv/bin/python -c \
  "import json,sys; d=json.load(sys.stdin); print(d['planner'], d['provider'], [c['tool'] for c in d['tool_calls']]); print(d['answer'][:200])"
#    expect: llm gemini:... ['status_summary'] and CONFIRMED 4,825 ... UNVERIFIABLE 272
```

Then, in the browser (http://127.0.0.1:5173):
- The header chip reads **"API ok"**, not "API unreachable" or "not the KAVAL API".
- `#map`: the status table shows 4,825 / 784 / 8,429 / 272. If not, someone left a slider
  moved; click **Reset to API defaults**.
- `#worklist`: N = 500 shows 390.5 and 53.9.
- `#validation`: the headline tile shows 81.7%.
- Open `http://127.0.0.1:5173/api/export?fmt=csv&budget=10`. A CSV downloads.
