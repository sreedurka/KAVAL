# 08 · Calibration, Confident Learning & Trust

**Owner: M3 (Audit Logic & Backend) · Phase 6a · AI-4**

This is the layer where the project most nearly overclaimed. Two metrics here were
circular or tautological before an audit caught them. Know which, and why.

---

## 1. Calibration — why raw confidence is not a probability

A model that says "90% confident" should be right 90% of the time. Ours was not:

| | Raw | Calibrated |
|---|---:|---:|
| Mean confidence | 0.942 | 0.817 |
| Actual accuracy | 0.817 | 0.817 |
| **ECE** | 0.1247 | **0.0046** |

Raw confidence claims 94.2% and delivers 81.7% (capture-event-grouped, regime 3-event) — **a twelve-point
overstatement**. You cannot allocate a field-verification budget on a number that lies by
twelve points, and the whole product is budget allocation.

After **isotonic regression** — a monotone, non-parametric map from raw score to observed
accuracy — mean confidence lands on 0.817: the accuracy itself.

### Why cross-fitted

**Fitting a calibrator is model fitting.** Fitting and evaluating it on the same capture
events would manufacture the calibration it claims to measure.

So: split the capture events in two, fit on half, apply to the other half, then swap.
Every parcel gets a calibrated confidence from a calibrator that **never saw its capture
event**, and the reported ECE is an out-of-fit measurement.

*Note the grouping is by capture event, not row.* The same leakage logic applies to
calibration as to training.

## 2. Confident learning — and what `p_label_wrong` is not

`kaval/audit.py::label_error_probability`, cleanlab-style, implemented directly.

**The construction.** For each class, the threshold is the mean self-confidence of parcels
carrying that label. A record is a candidate error when the model's confidence in the
**declared** class falls below that class's threshold while some other class exceeds its
own.

**Why per-class thresholds, not one global cut-off.** Rice is 63% of the data and carries
systematically higher confidence. A global threshold would set the bar at Rice's level and
flag half of Banana as suspect. Per-class thresholds ask "is this low *for its own
class*?"

**Result: 2,183 records (15.26%)** are candidate label errors.

### The overclaim we had to fix

The raw output is a **margin** — the difference between the model's preferred class and
the declared one. A margin is not a probability. It has no frequentist interpretation.

Our first version took it at face value, and the consequence was absurd on inspection: the
**top-500 routed parcels had mean `p_label_wrong` = 0.98**. An **82%-accurate model** (regime 3-event) was
asserting ~98% certainty that a surveyor was wrong.

**The fix, and the principle:** a model's claim that a label is wrong is only worth as much
as the model's own chance of being right.

```
P(label wrong) ≤ P(model correct)
```

The score is now discounted by measured model accuracy (0.817, regime 3-event), and
`label_error_probability()` **raises if you do not pass it**:

> *"model_accuracy is required: an undiscounted margin is not a probability and must not
> be routed on."*

That is deliberate. It makes the mistake we made impossible to repeat silently.

## 3. The Record Trust Score

Scores the **survey record's provenance** — how much we should trust the *evidence*,
largely separately from whether the model happens to agree with it.

| Component | Weight | Mean |
|---|---:|---:|
| `bag_size` | 0.250 | 0.595 |
| `photo_distance` | 0.200 | 0.491 |
| `bag_support` | 0.250 | 0.598 |
| `stage_plausibility` | 0.100 | 0.875 |
| `mixed_crop` | 0.100 | 0.973 |
| `geometry_source` | 0.050 | 0.733 |
| `heterogeneity` | 0.050 | 0.437 |

**How each is read:**

- **`bag_size`** — a singleton bag is direct evidence; a 20+ bag carries no per-parcel
  evidence at all. Decays to zero at 20.
- **`photo_distance`** — decays to zero at 3 km (the p90 of the measured distribution).
- **`bag_support`** — the MIL attention weight (doc 07). Low = the model treats this parcel
  as a passenger in its own bag.
- **`stage_plausibility`** — deliberately asks whether the stage is **rare for that crop**,
  not whether it is typical. Asking "typical?" would just re-encode the crop, since Coconut
  is ~99% `full_growth` and Marigold 100% `flowering`.
- **`mixed_crop`** — the record declares more than one crop category; single-label
  classification cannot express it.
- **`geometry_source`** — see §4.
- **`heterogeneity`** — the parcel's pixels disagreeing with each other.

**The weights are published.** A trust score nobody can interrogate is not an audit.

### One precision point — be accurate about this

The proposal says the trust score works *"independently of whether the model agrees with
it"*. **That is not strictly true**, and M3 must be able to say so: `bag_support` is
derived from a model trained on those labels.

The dependence is weak — correlation between trust and agreement is **r ≈ 0.124**, and
removing `bag_support` only drops it to 0.077 (`p6_audit.json` `trust_vs_agreement_r`) — but "independently" is too strong a word.
The accurate phrasing is *"largely independently of, though `bag_support` is
model-derived."*

## 4. `GEOMETRY_TRUST`, and a bug worth knowing

```python
GEOMETRY_TRUST = {"ftw": 1.0, "ftw_shared": 0.75, "ftw_ambiguous": 0.6,
                  "voronoi": 0.5, "buffer": 0.4, "buffer_no_boundary": 0.3}
```

**Why `ftw_shared` is 0.75 and not lower:** the boundary is *real satellite geometry* — the
model did delineate a field there. What is inferred is the **attribution of that field to
this particular legal parcel**, because 1.94 legal parcels share each physical field. Real
boundary, uncertain attribution.

**The bug:** `ftw_shared` was initially missing from this dict. It covers **7,724 parcels
(54% of the data)**, all of which silently fell through to the 0.4 default and had their
trust unfairly depressed. Nothing errored. It was found by checking that every value in
`geometry_source` had a mapping.

*Lesson worth stating:* a lookup with a default is a silent failure mode. Assert coverage.

## 5. Agreement status — order matters

```python
status = "UNCERTAIN"                                    # default
status[agrees & high_conf & high_trust]   = "CONFIRMED"
status[~agrees & high_conf]               = "DISPUTED"
status[trust < floor]                     = "UNVERIFIABLE"   # overrides both
status[~has_record]                       = "UNSEEN"
```

**`UNVERIFIABLE` deliberately overrides** whatever the model thinks. If the record's
provenance is too weak to test — a 40-parcel bag, a photograph 3 km away, a mixed-crop
declaration — then the finding is about the **evidence**, not the field, and no model
confidence should override that.

### The deliberate asymmetry

**`CONFIRMED` requires high trust. `DISPUTED` does not.**

So a mid-trust *agreement* becomes `UNCERTAIN`, while a mid-trust *disagreement* becomes
`DISPUTED`. We are **conservative about clearing a parcel and liberal about flagging one**,
because the costs are asymmetric: wrongly flagging costs one field visit, wrongly clearing
puts a bad record into a statistic that settles insurance.

This inflates `DISPUTED` relative to `CONFIRMED`, and we say so rather than letting it look
like a property of the data.

## 6. AI-6 — the conditional component

If FarmwiseAI supplies the photographs behind `image_path`, a vision-language model would
check each image against the declared crop and stage. That is **independent multimodal
evidence**, not another satellite inference, which is what makes it valuable.

We hold paths, not pixels, so it is marked conditional throughout and the audit works
without it. It would also let us test directly whether the median 1.4 km photo distance is
a geotagging artefact or something about how the survey was conducted.

---

## Questions you must be able to answer

**"Your model is 82% accurate but flags 15% of records as wrong. Isn't that just the model
being wrong?"**
> Partly, and that is why the score is capped by model accuracy. `p_label_wrong` can never
> exceed the probability that the model itself is right. It identifies **disagreement**,
> which is a reason to look, not a finding that the surveyor erred. Which side is correct
> is what the field visit determines.

**"Why isotonic and not Platt scaling?"**
> Platt assumes a sigmoid relationship between score and accuracy. Isotonic only assumes
> monotonicity, which is the weaker and safer assumption, and we have enough capture events
> to fit it. The cost is that it can overfit on small samples — which is exactly why it is
> cross-fitted.

**"Is the trust score independent of the model?"**
> Largely, but not entirely, and the proposal's wording is slightly too strong.
> `bag_support` is model-derived. Measured correlation between trust and model agreement is
> r ≈ 0.124; without `bag_support` it is 0.077. Weak, but not zero.

**"How did you choose the weights?"**
> They are judgement, informed by the forensics — bag size and photo distance carry the
> most weight because they are the two defects Phase 0 measured directly. They are
> published, they live in one config file, and the UI exposes the thresholds so anyone can
> see what moving them does. We would replace them with weights fitted against a real field
> audit the moment one existed.
