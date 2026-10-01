---
name: proposal-style
description: Writing conventions for KAVAL's proposal and narrative documents aimed at FarmwiseAI reviewers. Load before writing or editing proposal_updated.md, the validation report narrative, the README, or any document a reviewer reads. Triggers: "proposal", "write up", "report narrative", "README", "executive summary", "submission".
---

# Proposal Writing

Audience: FarmwiseAI reviewers shortlisting student teams. They read many proposals that
restate the brief. Ours must be recognisable in the first paragraph.

## Voice

- **Lead with the measurement, not the ambition.** "We measured X" beats "we will build Y".
- **Plain sentences.** No "leverage", "cutting-edge", "revolutionise", "seamless",
  "state-of-the-art", "robust and scalable".
- **Specific over grand.** "3,204 capture events behind 14,643 records" beats
  "significant data quality challenges".
- **Own the limits.** Naming what we will not attempt reads as competence, not weakness.
- No emoji. No exclamation marks.

## Structure obligations

The brief lists required proposal contents. Every one must be present and findable:
chosen challenge · title · objective · problem understanding in our own words · what we
will build and demonstrate · approach, architecture, models, tools, stack · main
components and capabilities · project plan with sequence, milestones, deliverables ·
innovative/exploratory ideas · datasets, APIs, cloud and model access required · team
members and responsibilities.

Map each brief-required capability to where we deliver it, explicitly. Reviewers check.

## The honesty section is load-bearing

The Leakage Ladder must appear early and in full. Frame it as: the brief warns leakage
invalidates results; we measured how much; here is the number we will report and why.

Never claim >95%. Never soften the finding into "data quality challenges".

## Tone on FarmwiseAI's data

The Digital Crop Survey is a national-scale achievement. Provenance artefacts are
inherent to field programmes at that scale, and no downstream ML currently detects them.
That gap is the opportunity. Write it that way — we are building them an instrument, not
grading their homework.

## Every number cites its script

Any figure in the proposal must be regenerable from `KAVAL/scripts/`. If it cannot be,
remove it.
