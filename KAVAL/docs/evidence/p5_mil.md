# Phase 5 — Multiple-Instance Learning over capture-event bags

Regime 3-event, 5 folds, identical to Phase 4. 14,310 parcels in 2,921 bags.

## Does modelling the bag structure help?

| Model | Parcel accuracy | Parcel macro F1 |
|---|---:|---:|
| Phase 4 baseline (per-parcel) | 81.7% | 0.566 |
| Attention-MIL (bag-supervised) | 78.7% | 0.509 |
| **Difference** | **-3.00 pp** | **-0.0565** |

Bag-level accuracy (one prediction per capture event, the unit the label was actually observed at): **87.6%** ± 0.020.

**MIL does not beat the per-parcel baseline on macro F1.** Reported as a negative result, per plan.md §11 rule 6. The attention signal is evaluated separately below and retains audit value regardless.

## Is the attention signal real?

The claim Phase 6 depends on: parcels the model attends to least should be the ones the satellite disagrees with. If not, `bag_support` is noise.

Measured against the **independently trained Phase 4 baseline**, which never saw the attention weights. Measuring against MIL's own prediction would be partly self-referential, since attention is what produced that prediction — the inflated figure is shown alongside so the difference is visible.

| Group (multi-parcel bags only) | vs independent baseline | vs MIL's own |
|---|---:|---:|
| Lowest-support quartile | 69.4% | 61.2% |
| Remaining three quartiles | 85.6% | 84.0% |
| **Gap** | **+16.18 pp** | +22.81 pp |

The signal is informative and is weighted in the Record Trust Score.

The self-referential measurement overstates the gap by +6.6 pp. Gating uses the independent figure.

`bag_support` is attention normalised by bag size, so it measures support rather than bag size: 1.0 is average support within the bag, below 1.0 marks a parcel the model treats as a passenger.
