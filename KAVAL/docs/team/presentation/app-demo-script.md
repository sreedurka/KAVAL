# KAVAL live website demo: spoken script (8 to 10 minutes)

**For:** the student team (M1 to M4), including non-technical presenters, walking
FarmwiseAI reviewers through the live site. Pair it with
`docs/team/website/page-guide.md` (what every element means) and
`docs/team/14_REVIEW_PREP.md` (the long question list).

**Order.** It follows `docs/DEMO_WALKTHROUGH.md`: **Leakage Ladder first** (the credential),
then the audit map, then the worklist, auto-clear, village audit and the analyst. Tab names
below are the on-screen names (the walkthrough calls two of them "Validation" and
"Worklist").

**Where the numbers come from.** Every figure in quotes was read on 2026-10-01 from the
live API at `http://127.0.0.1:8077` (the same one the page calls) or from
`docs/evidence/*.json`; the source is named where it matters. **If the screen differs from
this script, the screen is right. Say what the screen says.** Do not quote this file from
memory.

## Rules of speech (the reviewers will be listening for these)

1. **Never say a parcel or a surveyor is "wrong".** Say "the survey and the satellite
   disagree; a field visit decides which one is right". The worklist column is headed
   P(correction); say "the chance the record needs correcting".
2. **Every accuracy figure carries its regime.** Say "81.7% accuracy, MLP head, capture-event
   grouped" (the on-screen chip says `split: 3-event`). Never say "81.7%" alone.
3. **Never claim 95%.** We report 81.7% under capture-event grouping and explain why a
   95% figure would require a split the brief itself calls invalid.
4. **Volunteer the weakness first.** Each page has one. Say it before they ask.

## Timing at a glance

| # | Page | Time | One-line job |
|---|---|---|---|
| 0 | Frame | 0:30 | the thesis |
| 1 | Leakage Ladder | 2:00 | why 81.7% (3-event) and not 95% |
| 2 | Audit map | 1:45 | the status-coloured map and the audit trail |
| 3 | Field worklist | 2:00 | N visits, expected corrections, versus random |
| 4 | Auto-clear | 1:00 | the surveyor-days saved, and what we do not claim |
| 5 | Village audit | 1:00 | satellite versus the published registry |
| 6 | Analyst | 1:15 | ask it in words, check the tool calls |
| 7 | Close | 0:30 | the one-sentence answer |

Total about 10 minutes. To cut to 8, trim the village audit to one sentence and ask only
one analyst question.

## Before anyone arrives (3-minute pre-flight)

```bash
# from the repository root (the folder that contains KAVAL/)
.venv/bin/uvicorn KAVAL.api.main:app --port 8077        # API (not 8000: an unrelated app owns it)
cd KAVAL/frontend && npm run dev                         # site on http://127.0.0.1:5173
```

- Open `http://127.0.0.1:5173/#validation`. Check the **top-right chip says "API ok"** (not
  "API unreachable" or "not the KAVAL API") and that **no striped "MOCK DATA" banner** is
  showing. A mock banner means every figure is synthetic: stop and restart without
  `VITE_USE_MOCK`.
- Rail sliders are at the API defaults: `confidence_high` 0.80, `trust_floor` 0.35,
  `trust_high` 0.65. If the "Reset to API defaults" button is clickable, click it.
- Browser at desktop width (1440 px wide shows everything best), **light theme**, zoom 100%.
- One quick check that the analyst is alive: Analyst tab shows an "Active planner" chip.
- Backup if the API dies mid-demo: open `docs/evidence/` (every number exists there as a
  file) and `docs/e2e/*.png` (screenshots of each page). The argument does not depend on the
  live server.

---

## 0. The frame (0:30)

**Say:**
> "The brief asks for a crop classifier at 95% accuracy. We measured the data first, and what
> we found changed what we think should be built. The classifier is the instrument; the
> product is the audit. We'll show you the evidence for that in the order a sceptic would ask
> for it: first why the number is what it is, then what the audit does with it."

**Do:** have the browser on the Leakage Ladder tab. Point at the header line "The classifier
is the instrument. The product is the audit."

---

## 1. Leakage Ladder (2:00)

**Do:** click the **Leakage Ladder** tab (or open `#validation`).

**Say (point at the three tiles):**
> "Headline accuracy: 81.7%, with our best head, an MLP, validated so that every parcel that
> shares a photograph stays on the same side of the split. That is the chip you see here:
> split three-event. We never show an accuracy without its split."

**Do:** point at the bar chart, top to bottom, then at the table.

**Say:**
> "This is the Leakage Ladder. One model, same features, same settings. Only the way we split
> the data changes. Shuffle the rows: 89.7%. Group by parcel, which is the obvious fix and the
> one the brief's wording suggests: 89.5%. It moves nothing. Group by capture event, meaning
> by photograph: 81.2%. Group by village, which is the test of an area the model has never
> seen: 70.8%, though with 21 villages that has a wide fold-to-fold swing of about 9.5 points.
> These four rungs hold LightGBM fixed so that only the split changes; our best head, the
> MLP, reaches 81.7% on the capture-event rung."

**Why (do: scroll to the forensics cards at the bottom, point at the three tiles):**
> "The reason is in the data. 14,643 survey records trace back to only 3,204 photographs.
> One photograph supplies the crop label to up to 43 parcels, and across the whole data set
> no photograph shows more than one crop; the label is copied. The median photograph was taken
> 1,436 metres from the parcel it documents, and 62.3% were taken more than a kilometre away.
> That is not an accusation; it is a measurement. It means the photo cannot serve as
> per-parcel evidence, and it means a random split lets near-identical parcels sit on both
> sides, so the model memorises instead of generalising."

**Component to explain (1 to 2 sentences):** the **Cost of honesty** tile (18.9 points) is the
difference between the loosest and strictest rung, same model. The **per-class table** puts
independent capture events ("Effective n") next to record count: Banana has 653 records but
only 64 independent observations (F1 0.322, 3-event). Optionally scroll to **Calibration**:
"the raw model claims 94.2% confidence and delivers 81.7% (3-event); after calibration, mean
confidence is 81.7%, and the calibration error drops from 0.1247 to 0.0046. You cannot spend
a budget on a number that overstates itself."

**Weakness to volunteer:**
> "Two honest caveats. First, the ladder holds LightGBM fixed, and the headline is the MLP,
> so 81.2% in the table and 81.7% in the tile are two heads on the same capture-event
> regime, not an inconsistency. Second, we have not tested outside this one taluk; the
> village-grouped rung is our nearest proxy and it is noisy."

**Transition:** "So 95% is only reachable by validating in a way the brief itself says
invalidates the result. What we do with the honest number is the product. Let's look at the
map."

**Likely questions (answers from `14_REVIEW_PREP.md`)**

- *"Why can't you hit 95%?"* "Not without leaking. One photograph labels up to 43 parcels, so
  under a random split near-identical parcels land on both sides. The same LightGBM model
  scores 89.7% under a random split and 81.2% under capture-event grouping; only the split
  changed."
- *"Isn't 81.7% just a weak model?"* "It is our best head under a strict regime. The proof is
  that one fixed model drops from 89.7% to 81.2% purely because of the split. And macro F1 is
  the harder number: 0.564 here (MLP, 3-event), because 63% of parcels are rice and a model that
  always says rice scores 63% and is useless."
- *"Is capture-event grouping too strict?"* "It is the unit at which the label was actually
  observed. A photograph produced one judgement about one crop. Village grouping is stricter
  still, and we show it."
- *"Presto versus Google embeddings?"* "We ran it, same folds: Presto alone 74.2% accuracy,
  macro F1 0.452, against 81.5%, 0.563 for Google's embeddings (MLP, 3-event); Presto is behind in all 5 folds.
  Combining them, 81.3%, is within fold noise, so no gain can be claimed. That is not a verdict
  on Presto as a model: we fed it surface reflectance where it was pretrained on top-of-atmosphere,
  with a frozen encoder." (Live: the "Each source against GSE only" mini-table on this tab.)

---

## 2. Audit map (1:45)

**Do:** click **Audit map**. Leave "Colour by: agreement status".

**Say:**
> "A map coloured by crop looks like every classification demo. This is an audit, so it is
> coloured by what to do. Red parcels are DISPUTED: satellite and survey disagree at high
> confidence. They are the loudest thing on the screen on purpose. Blue is CONFIRMED and fades
> into the background; amber is UNCERTAIN; and the striped teal ones are UNVERIFIABLE, which
> is the interesting one. We did not use green and red because under the commonest form of
> red-green colour blindness our test measured them as nearly identical, and 'skip the visit'
> must not look like 'send someone tomorrow'."

**Do:** point at the card **"Agreement status across the taluk"** (scroll a little).

**Say:**
> "Across all 14,310 audited parcels: 4,825 confirmed, 784 disputed, 8,429 uncertain, 272
> unverifiable. These counts are re-calculated by the server, not by the page."

**Do (the story):** use the **Village** dropdown, pick **Rayagiri - Part-2**. The map zooms
and shows 975 parcels, 6 of them red. Hover the red parcels (the tooltip shows the id) and click `152_399_1` (survey
number 399, 1.72 ha).

**Say (point at the panel as you read it):**
> "Parcel 152_399_1, survey number 399, subdivision 1. The survey says Rice. The satellite says
> Sugarcane, at 97% calibrated confidence. Now look at the provenance, because that is what
> makes this an argument and not an assertion. The record trust score is 0.85, high. This
> photograph was shared by exactly one parcel, so it is direct evidence, and it was taken
> 743 metres away. The geometry is its own satellite-delineated field. So the survey and the
> satellite disagree, we can see the record is a good one, and a surveyor should go and look.
> That is the top row of our worklist."

**Do:** click the second red parcel `152_219_4` if time (declared Sugarcane, satellite Rice at
96.3%, trust 0.91, bag of 5, photograph **71 metres** away): "a mirror case, and here the
photographer stood 71 metres from the parcel".

**Do (UNVERIFIABLE, 20 seconds):** change Village to **Thenmalai - Part-2** (95 hatched
parcels), click a striped one such as `142_521_1`.

**Say:**
> "Here the survey says Maize and the satellite says Maize: they agree. And it is still
> UNVERIFIABLE. The trust score is 0.18: this label was shared by 25 parcels, the photograph
> was 3.4 kilometres away. The record cannot be tested, so the action is to re-survey the
> record, not to visit the field. Nothing downstream of the Digital Crop Survey reports that
> today."

**Do:** in the right-hand rail drag **confidence_high** from 0.80 to 0.90 and watch the map and the
table change (DISPUTED 784 becomes 405; CONFIRMED 4,825 becomes 3,761), then click **Reset to API defaults**.

**Say:** "These thresholds are visible and movable. An audit with invisible thresholds is not
auditable. The rule that turns a prediction into a status lives in exactly one file on the
server, so the map, the worklist and the savings can never disagree."

**Component to explain:** the **calibrated confidence** is the model's probability after
calibration, so "80%" really means about 80% right; the raw model said 100.0% for this
parcel. The panel shows both so the gap is visible.

**Weakness to volunteer:**
> "Two things. The default map draws a random 3,000 of the 14,310 parcels so it renders fast;
> the table counts are for all of them, and picking a village shows every parcel. And a
> satellite-only demo on the four unlabelled villages is not built: they are the four Reserve
> Forests, which have no survey records, so they appear as a dashed exclusion with no status,
> and we will not invent a crop for them."

**Transition:** "That's one parcel. The department can't visit all of them, so the next
question is: if you can afford N visits, which N?"

**Likely questions**

- *"Why not colour by crop?"* "A crop map answers what a classifier already does. This one
  answers what to do next. Crop is one dropdown away as a secondary layer."
- *"How do I know the numbers on screen are real?"* "The page has one piece of network code; a
  failed call shows an error, not a placeholder; the grey footer under each panel prints
  sources, count, split and time; and the status counts equal `docs/evidence/p6_audit.json`."
- *"Is the reserve-forest thing encroachment?"* "No. There is no ground truth there. 734.7 ha
  reads as field-like, which is equally consistent with delineation error. It gives a ranked
  list of places worth a visit."
- *"What does 'DISPUTED' claim?"* "Only that the two sources disagree at high confidence.
  Which is right is what the visit determines."

---

## 3. Field worklist (2:00)

**Do:** click **Field worklist**. The slider is at 500.

**Say (say the weakness first, as the walkthrough requires):**
> "Before the numbers, one honesty point. You'll see a figure, 5.45 times, on the right tile.
> Do not be impressed by it. It equals one divided by the base disagreement rate, 18.3%, at
> any budget below the number of disagreements, so it measures coverage, not ranking skill.
> Any classifier can list its own disagreements. The page says so on the tile and the API
> flags it as pinned by construction."

**Do:** point at the two tiles on the left.

**Say:**
> "Now the figure that matters. With 500 visits, our routing is expected to turn up about
> 390 record corrections. Choosing 500 parcels at random would give about 54. That 390 is a
> sum of probabilities: a model estimate of how many of those records need correcting, not a
> count of confirmed corrections. Those are visits to 3.5% of the parcels, covering 143
> hectares."

**Do:** **drag the slider to about 120**: "94.5 versus 13.1" (routed mean confidence 0.759).
Then **drag to 1,000**: "764.5 versus 108.8".

**Say:** "Move the budget and both bars re-ask the server. The random bar has a whisker: it is
the average of 200 random draws and the spread between them."

**Do:** point at the third tile.

**Say:**
> "This is the number that does reflect ranking quality: the parcels we route first carry a
> mean calibrated confidence of 0.734, against 0.652 across all 2,617 disagreements. The
> better-evidenced cases go first. And notice it falls as the budget grows, 0.759 at 120
> visits, 0.716 at 1,000, because we dip into weaker cases."

**Do:** scroll to **The queue**. Point at row 1 (`152_399_1`, the parcel you just opened) and
the columns.

**Say:**
> "This is the table a field officer takes. Parcel, village, declared crop, satellite crop,
> the chance the record needs correcting, the satellite's confidence, the trust score, how many
> parcels shared the photograph, how far away it was taken, and the area. It is ranked by that
> chance times the parcel's area, so a visit to a larger parcel resolves more land. The Export
> CSV button downloads exactly this queue, same order, same thresholds. The field officer
> uses the file, not this screen."

**Component to explain:** the queue includes more than DISPUTED parcels. At 500 visits it
holds 216 DISPUTED, 275 UNCERTAIN and 9 UNVERIFIABLE, because it ranks by expected correction,
not by label. And you will see many "82%" in the P(correction) column: that is the ceiling, the
model's own accuracy (81.7%), since a model's claim that a record needs correcting cannot be
worth more than its chance of being right.

**Weakness to volunteer (already said): the pinned 5.45x.** Add: "The 390 is estimated;
whether a routed visit yields more true corrections than a random one cannot be measured
against labels the surveyor supplied. That needs a field audit."

**Transition:** "And the opposite question: which parcels do they never need to visit again?"

**Likely questions**

- *"Your routing ratio, is it real?"* "It is arithmetically real and analytically weak. It is
  capped at one over the base rate (5.47x) and reaches the cap whenever every routed parcel
  is a disagreement. We first published it as a 'lift', retracted that, and now show the
  confidence comparison instead (0.734 against 0.652 at 500)."
- *"What does the 390 mean?"* "It is the sum of the model's estimated chance that each routed
  record needs correcting. A model estimate, not a measured correction count."
- *"Why does the table show 82% for so many?"* "It is a ceiling, set to the model's measured
  accuracy 81.7% (3-event), because the raw gap between classes is not a real probability."
- *"Is the export really the worklist?"* "Yes: the export carries the budget, the village and
  the three thresholds, and reproduces the on-screen order, with a rank column."

---

## 4. Auto-clear (1:00)

**Do:** click **Auto-clear**.

**Say:**
> "4,825 parcels, 33.7% of the taluk and 871 hectares, are CONFIRMED: the satellite agrees with
> the survey at high calibrated confidence on a record we trust. Skipping them next season
> saves 193 surveyor-days out of a 572-day baseline for visiting everything. That uses an
> assumption that is on the page: 25 parcels per surveyor per day, which is an assumption,
> not a measurement, and the one number FarmwiseAI can replace with an actual."

**Do:** drag **trust_high** up to 0.80 (parcels 1,056, 42.2 days) to show saving and risk
move together, then **Reset**.

**Weakness to volunteer (point at "What this panel does not claim"):**
> "What you will not find here is an 'accuracy within the cleared set', because it is 100% by
> construction: a parcel is confirmed because the satellite agreed with the survey. That would
> look like a validation result and carry no information. What matters is how often satellite
> and surveyor err the same way, and that cannot be measured against labels the surveyor
> supplied. We show a proxy, 7.6% residual, about 365 of the 4,825, derived from calibrated
> confidence, and we say it is a proxy, not a bound. Only a field audit of a sample of
> confirmed parcels settles it."

**Component to explain:** the surveyor-days bar chart: 572 for visiting everything, 379 for
visiting only what we do not clear, 193 saved. The cost box shows the assumption and its
note: "Derived from 3,204 capture events over a roughly 7-day survey window across 21 villages".

**Transition:** "Next, the check against the published village figures."

**Likely questions**

- *"How do you know auto-clearing is safe?"* "We don't, fully, and we say so. The risk is
  satellite and surveyor wrong the same way. We offer 7.6% as a rough proxy and propose a
  field audit of a cleared sample."
- *"Where does 25 per day come from?"* "An assumption: 3,204 capture events over about 7 days
  in 21 villages. It is on the page and FarmwiseAI can replace it with their actual."
- *"Does 'cleared' mean permanently?"* "No. It removes the parcel from next season's list; it
  does not retire it from the survey."

---

## 5. Village audit (1:00)

**Do:** click **Village audit**.

**Say (weakness first; point at the two yellow boxes):**
> "Read the yellow boxes before the chart. The Agrisnet village report is the published
> aggregate of the same Digital Crop Survey that gave us our ground truth, so this is not
> independent validation; it is a consistency check of the survey's own published numbers
> against the satellite. And we compare each crop's share of the village, not hectares,
> because our parcels cover only part of each village."

**Do:** point at the top bar and the table row.

**Say:**
> "The longest bar: Rayagiri - Part-1, Sugarcane. The registry publishes 58.2% sugarcane for
> that village; the satellite sees 23.7%. That is 34.6 percentage points lower. Next, Thenmalai
> - Part-2, Rice: the registry says 19.8%, the satellite 52.3%, 32.6 points higher. Neither
> side is assumed correct. Across all villages, the satellite sees 6.5 points less sugarcane
> than the registry does, a consistent sign, so it is a model or registry habit and not a
> village finding. And it isn't always large: next door, Rayagiri - Part-2, rice is 99.3% in
> the registry and 95.2% by satellite, a gap of 4.1 points."

**Component to explain:** the table's **Delta share (pp)** is satellite share minus registry
share; **Implied ha delta** extrapolates the gap to the registry's village area, so it is not
measured (for the top row, -256 ha against the registry's 431 ha of sugarcane). Chart sorted by size of
gap because the question is where an officer should look first.

**Weakness to volunteer:** the one above, plus: "There is a related finding we withdrew:
1,930 records sit in a different village polygon from the one their code names, 1,895 of them
in the Viswanathaperi 911/912 pair. We first said the registry supported a boundary error;
the registry is compiled from the codes, so it agrees with them by construction, and we
retracted that. The geometry still suggests a boundary or labelling problem, and cadastral
records would settle it."

**Transition:** "Finally, the part that lets anyone on the team query all of this in plain
English."

**Likely questions**

- *"Isn't the registry comparison circular?"* "Partly, and the API payload says so itself. It
  audits the survey's own published numbers against satellite; it is not a second independent
  survey. We use share rather than hectares for the coverage reason."
- *"Why is Rayagiri - Part-1 so far off?"* "We don't claim to know. It is a place worth a
  look: either the satellite under-sees sugarcane, or the registry share is high. The
  systematic bias for sugarcane is -6.5 points pooled across villages."
- *"Would this work outside Sivagiri?"* "Untested. The village-grouped rung (70.8% accuracy,
  LightGBM, ±9.5 points across 21 villages) is our closest proxy, and it is too noisy to
  quote precisely."

---

## 6. Analyst (1:15)

**Do:** click **Analyst**. Point at the "Active planner" chip.

**Say:**
> "This is a conversational analyst over the same tools the screens read. It never computes a
> number itself; it chooses tools, and every figure in the answer came out of a tool call.
> Look at the chip: it names the model that produced the answer, or says 'offline planner, not
> LLM' if no model is reachable, so nobody can mistake keyword routing for AI planning."

**Do:** click the starter **"Where should we send 500 surveyors next season?"** (about 4
seconds). When the answer lands, open the **"1 tool call"** drawer and point at the
citation chips.

**Say:**
> "It called `route_verification_budget` with budget 500. These chips cite the file, the count
> and the split regime. Compare with the worklist: the same 390.5 expected corrections against
> 53.9 for random, because the agent and the screen share one code path."

**Do:** click **"Which parcels can we stop visiting?"**

**Say:** "Same again: 4,825 parcels, 193 surveyor-days, and note that it states the residual
error is a rough proxy, not a bound."

**Component to explain:** the **tool-calls drawer** and **citations** are the audit trail of
the analyst: if an answer has no citations the page shows an amber warning instead.

**Weakness to volunteer (say it, then show the drawer):**
> "Two honest limits. Planning is verified on Gemini's free tier, not on Claude; the
> Anthropic account could not be funded, so Claude's planning is not verified and we don't claim
> it. On Gemini, the six brief and three product questions pass 9 of 9, and the two extended
> questions, a parcel lookup and a calibration question, pass 2 of 2. The model sometimes
> skips a secondary tool call or writes a number no tool returned: a mis-rounding, or a
> figure it worked out itself. Our grounding check flags those, and that is exactly why the
> citations and tool-call drawer are on screen: check it."
> (Source: `docs/evidence/p7_analyst_verification.json` → `llm_planner`, which records per
> question which model answered, the tools it chose, its time, and any figure not traceable
> to a tool result.)

**More verified questions to use if time allows or if asked.** All come from
`scripts/p7_verify_analyst.py` (`PRODUCT_QUERIES` and `BRIEF_QUERIES`); the full tested list,
with expected answers, is kept by another agent in
`docs/team/website/demo-test-inputs.md`. Use that file for anything beyond these four:

1. **"Where should we send 500 surveyors next season?"** (calls `route_verification_budget`;
   expect 390.5 vs 53.9 and the pinned-ratio caveat.)
2. **"Which parcels can we stop visiting?"** (calls `auto_clear_summary`; expect 4,825, 193.0 days,
   the 7.6% proxy.)
3. **"How trustworthy is the ground truth itself?"** (calls `ground_truth_forensics`; expect
   4.57x inflation, 43 parcels per photograph, 1,436 m median distance.)
4. **"Show villages where predicted crop area differs significantly from the supplied
   registry."** (calls `compare_to_registry`; expect the independence caveat. In the
   verification run this answer contained two numbers not in the tool results, so check the
   drawer on this one.)

**Transition:** "That is the product: an audit, not a classifier with a map."

**Likely questions**

- *"Why Gemini and not Claude?"* "The Anthropic account could not be funded. The provider layer is
  model-agnostic: Claude first whenever a key exists, then Gemini's free tier, Groq or
  OpenRouter, a local Qwen2.5-7B, and finally the offline planner. Each model's planning is
  verified separately, and our Gemini result says nothing about Claude."
- *"What if the model makes up a number?"* "Every figure should come from a tool result;
  it sometimes states a figure no tool returned, our grounding check flags it, and the
  citations and tool-call drawer let you check. The tool layer itself is verified: 6 of 6 brief queries and 3 of 3
  product queries."
- *"How much of this actually runs?"* "All of it. The pipeline runs end to end on the supplied
  data and every document figure regenerates from `scripts/` into `docs/evidence/`."
- *"What if there is no LLM?"* "The offline planner answers by keyword routing to the same
  tools, and the page labels it 'not LLM'."

---

## 7. Close (0:30)

**Do:** go back to the Leakage Ladder tab (or stay on the worklist).

**Say:**
> "We report 81.7% accuracy, MLP head, capture-event grouped, not 95%. The honest number is
> lower and the product is better, because 18.3% of parcels, 2,617 of 14,310, carry a
> satellite-survey disagreement at all. Four in five need no attention, and knowing which
> fifth is worth more than another point of accuracy."

**If asked "what did you get wrong?":** open `docs/team/13_CORRECTIONS.md` (the logged
corrections, including a tautological lift metric we retracted, a double-counted area, and a
retracted registry argument). For a project whose thesis is validation honesty, that log is the
point.

**Questions that cut across pages**

- *"What do you need from us?"* "Cadastral geometry for a proper boundary benchmark,
  confirmation of the Viswanathaperi 911/912 village boundary, the survey photographs, and a
  field audit of a sample of CONFIRMED parcels. None blocks the demo; the last one settles the
  auto-clear residual (`docs/DATA_REQUEST.md`)."
- *"Why is a student project worried about colour blindness?"* "The two states that matter
  most are CONFIRMED and DISPUTED. Green against red measured as nearly identical to the most
  common form of red-green colour blindness, so we switched to blue and red and added a hatch
  to UNVERIFIABLE. In dark mode teal against red is in the tool's warning band, and the hatch
  covers it."
- *"Can a field officer use this on a phone?"* "The screens render at phone width, but the
  officer works from the exported worklist, not this screen."

---

## If something breaks

| Symptom | Do this |
|---|---|
| Header chip says "API unreachable" | restart the API (command above); refresh |
| Header chip says "not the KAVAL API" | something else is on the proxied port; check the API is on 8077 |
| Striped "MOCK DATA" banner | the site was started in mock mode; every number is synthetic; restart without it |
| Map is blank but the table below has counts | the OpenStreetMap tiles need internet; the parcels still draw; or open `docs/e2e/desktop-map.png` |
| Analyst takes too long or the chip says "offline planner" | say so: "this is the offline planner, labelled not LLM"; the same tools answer; or show `docs/e2e/flow-analyst.png` |
| A number differs from this script | trust the screen; the numbers here were read on 2026-10-01 and the API recomputes from files on disk |
| Anything else | `docs/evidence/` holds every figure as a file independent of the server |
