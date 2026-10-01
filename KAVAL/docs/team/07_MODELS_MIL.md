# 07 · Models & Multiple-Instance Learning

**Owner: M2 (ML & Validation) · Phase 5 · AI-3**

This phase contains the project's **methodological contribution** and its most instructive
**negative result**. Both matter.

---

## 1. The heads, and why MLP wins

Four heads on identical capture-event-grouped folds:

| Head | Accuracy | Macro F1 |
|---|---:|---:|
| **MLP** | **81.7%** | **0.564** |
| LogisticRegression | 80.6% | 0.537 |
| LightGBM | 81.2% | 0.528 |
| RandomForest | 79.1% | 0.469 |

**A small neural head beats gradient-boosted trees**, which is the opposite of the usual
result on tabular data.

The explanation is in the nature of the features. Trees split on individual columns, which
works when columns are independently meaningful. A GSE embedding is a **learned continuous
space** — its information lives in directions and distances, not in any single coordinate.
An MLP can form linear combinations across all 64 dimensions; a tree has to approximate
that with axis-aligned cuts.

*Useful thing to say in review:* this is a small piece of evidence that the embedding
really is an embedding, not just 64 convenient numbers.

## 2. The idea: a capture event is a bag

Phase 0 established that one photograph labels up to **43** parcels. Every other team
will treat those as 43 independent labelled examples. They are not.

**Multiple-Instance Learning** is the formalism for exactly this: labels attach to a *bag*
of instances rather than to each instance. A surveyor's photograph produced **one judgement
about one crop**, and that judgement was attributed to a group. So the bag — not the parcel
— is the unit the label describes.

Modelling it this way turns the dataset's central defect into the modelling framework,
which is the part of the project we would most defend as novel.

## 3. The architecture

`kaval/mil.py`, gated-attention MIL after Ilse, Tolstikhin & Welling (2018).

```
instances (parcels in one bag)
      │
      ▼  encoder: Linear → LayerNorm → ReLU → Dropout → Linear → LayerNorm → ReLU
      │
      ▼  gated attention:  a_i = w·( tanh(V·h_i) ⊙ σ(U·h_i) )
      │                    α = softmax(a)  over the bag
      │
      ▼  bag representation = Σ α_i · h_i
      │
      ▼  classifier → bag logits
```

**Why *gated* attention.** The `tanh` branch supplies magnitude; the `sigmoid` branch is a
gate. Without the gate the model can only down-weight everything uniformly; with it, the
model can **suppress one member while keeping the rest** — which is exactly the behaviour
we need if some bag members are passengers.

**Why the same classifier head is applied to instances at inference.** KAVAL ships
**per-parcel** predictions, but supervision is **per-bag**. Applying the shared head to
individual instance representations is what makes a bag-trained model usable for the
deliverable.

**Class weighting.** Rice is 63% of parcels. Without reweighting the bag loss the model
collapses onto it and the attention signal becomes uninformative.

## 4. `bag_support` — and why the normalisation is essential

Attention weights sum to 1 within a bag. So a member of a 43-parcel bag is *mechanically*
~43× smaller than a singleton's. **Raw attention would just be measuring bag size.**

So we divide by the uniform weight 1/n:

```
bag_support = α_i × n
```

- **1.0** = exactly average support within its bag
- **< 1** = the model treats this parcel as a passenger
- **> 1** = this parcel carries the bag

Now it is comparable across bags of any size, and it means *support*, not *size*.

## 5. The negative result

Regime 3-event, same five folds as Phase 4 (docs/evidence/p5_mil.json):

| Model | Parcel accuracy | Parcel macro F1 |
|---|---:|---:|
| Phase 4 baseline (per-parcel) | 81.7% | 0.566¹ |
| Attention-MIL | 78.7% | 0.509 |
| **Difference** | **-3.00 pp** | **-0.0565** |

¹ MIL's comparison re-derives the baseline on MIL's own feature matrix (`baseline_parcel_macro_f1` = 0.5658), so it differs from the Phase 4 headline (0.5641, `p4_results.json` `headline.macro_f1`) in the third decimal. Both are regime 3-event.

**MIL is a worse classifier.** We report it, in the validation report and in the proposal,
as a negative result.

Bag-level accuracy — one prediction per capture event, the unit the label was actually
observed at — is **87.6%** ± 0.020, which is unsurprising and not a substitute
for the per-parcel number.

**Why it probably lost:** bag-level supervision gives the model strictly less information
per parameter than per-parcel supervision does, and with only 2,921 bags the effective
training set is small. The formalism is right about the *data*; it is not obviously right
about the *objective* when you ultimately need per-parcel output.

## 6. The attention signal — measured honestly

The claim Phase 6 depends on: parcels the model attends to least should be the ones the
satellite disagrees with. If not, `bag_support` is noise.

| Group (multi-parcel bags) | vs **independent** baseline | vs MIL's own prediction |
|---|---:|---:|
| Lowest-support quartile | 69.4% | 61.2% |
| Remaining three quartiles | 85.6% | 84.0% |
| **Gap** | **+16.18 pp** | +22.81 pp |

### The self-reference problem

The obvious way to measure this is against MIL's own prediction. **That is partly
circular**: `bag_support` *is* this model's attention weight, and attention is the
mechanism that produced the prediction. A gated-attention head down-weights instances
whose embeddings do not support the bag label, and those instances' argmax is then likely
a different class. The model would be partly agreeing with itself.

So we measure against the **independently trained Phase 4 baseline**, which never saw the
attention weights. That gives **+16.2 pp** rather than +22.8. We report both, so the
difference is visible.

**+16.2 points against a model that never saw the weights is a real, strong signal.** The
component earns its place as an *audit instrument* while failing at the job we designed it
for.

## 7. The negative result is wired into the product

This is the part worth emphasising. The finding is not merely narrated — it **gates**.

`scripts/p6_audit.py` reads Phase 5's evidence and includes `bag_support` in the Record
Trust Score **only if the independent gap exceeds 2 points**:

```python
use_support = bool(p5["attention_check"]["signal_is_informative"])
```

Had the separation been weak, the weight would have been dropped and redistributed
automatically, and `p6_audit.json` would record why. The gate uses the **independent**
figure, never the flattering one.

*In review:* "we report negative results" is cheap. "The negative result is wired into the
product as a gate" is the version that means something.

---

## Questions you must be able to answer

**"Your novel component didn't work. Why keep it?"**
> It failed at classification and succeeded at what we actually needed. The attention
> weights separate survey agreement by +16.2 points against an independently trained
> model — it identifies which parcels in a photo-bag are passengers, which is precisely
> the audit signal the product consumes. We would have dropped it if the separation had
> been under two points; that gate is in the code.

**"Why measure the attention gap against a different model?"**
> Because measuring against MIL's own prediction is partly self-referential — attention is
> what produced that prediction. That version reads +22.8 pp. The honest number is
> +16.2, and it is the one we gate on. We publish both so the inflation is visible.

**"Why does MLP beat LightGBM? That's unusual."**
> Because the features are an embedding, not tabular columns. Its information is in
> directions and distances across all 64 dimensions; a tree approximates that with
> axis-aligned splits on single coordinates. An MLP forms linear combinations directly.

**"Could you make MIL work with more tuning?"**
> Possibly. We did not pursue it, because the fair comparison requires identical folds and
> we were not going to tune one arm and not the other. Our honest position is that
> bag-level supervision gives less information per parameter, and with 2,921 bags that
> costs more than the correct formalism gains.

**"Isn't `bag_support` just measuring bag size?"**
> It would be without the normalisation — attention sums to 1 per bag, so a member of a
> 43-parcel bag is mechanically 43× smaller. We divide by the uniform weight 1/n, so 1.0
> means average support regardless of bag size. That normalisation is the difference
> between a signal and an artefact.
