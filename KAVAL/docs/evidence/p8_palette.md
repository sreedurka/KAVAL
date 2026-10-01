# Phase 8 — Agreement-status palette, colour-vision check

Colours read from `KAVAL/frontend/src/styles.css`. Validator `validate_palette.js` (dataviz skill), `--pairs all`.

| Palette | Mode | Worst CVD ΔE | Normal-vision floor ΔE | Result |
|---|---|---:|---:|---|
| filled_light | light | 9.1 (protan) | 22.9 | pass (warn: Contrast vs surface) |
| with_unseen_light | light | 5.1 (deutan) | 14.5 | FAIL: Chroma floor, CVD separation, Normal-vision floor |
| filled_dark | dark | 7.2 (deutan) | 16.9 | pass (warn: CVD separation) |
| with_unseen_dark | dark | 2.0 (deutan) | 12.6 | FAIL: Chroma floor, CVD separation, Normal-vision floor |
| retired_light | light | 4.1 (deutan) | 18.9 | FAIL: Lightness band, Chroma floor, CVD separation |

`with_unseen` fails the chroma floor by design: UNSEEN is achromatic and drawn as an outline with no fill. `retired` is the green/red palette that Phase 8 replaced.

## Raw validator output

### filled_light

```
/tmp/claude-1000/bundled-skills/2.1.285/5f88d207b57b51bcce81e1355cb0a1dc/dataviz/scripts/validate_palette.js #d03b3b,#eda100,#1baf7a,#2a78d6 --mode light --surface #fcfcfb --pairs all
Palette (light, surface #fcfcfb, categorical): 4 slots
  [PASS] Lightness band         all 4 inside L 0.43–0.77
  [PASS] Chroma floor           all 4 >= 0.1
  [PASS] CVD separation         worst all-pairs #1baf7a↔#eda100 ΔE 9.1 (protan) · tritan 9.6
  [PASS] Normal-vision floor    worst all-pairs #1baf7a↔#eda100 ΔE 22.9 (normal)
  [WARN] Contrast vs surface    below 3:1 — relief required (visible labels or table view): [["#eda100",2.11],["#1baf7a",2.74]]

  → ALL CHECKS PASS  (CVD in the 6–8 floor band is legal ONLY with secondary encoding: direct labels, gaps, or texture)
  scope: categorical palettes only. For a lone status/text color check WCAG text contrast; for a sequential ramp, lightness monotonicity.
```

### with_unseen_light

```
/tmp/claude-1000/bundled-skills/2.1.285/5f88d207b57b51bcce81e1355cb0a1dc/dataviz/scripts/validate_palette.js #d03b3b,#eda100,#1baf7a,#2a78d6,#898781 --mode light --surface #fcfcfb --pairs all
Palette (light, surface #fcfcfb, categorical): 5 slots
  [PASS] Lightness band         all 5 inside L 0.43–0.77
  [FAIL] Chroma floor           below floor (reads gray): [["#898781",0.009]]
  [FAIL] CVD separation         worst all-pairs #898781↔#1baf7a ΔE 5.1 (deutan) · tritan 9.6
  [FAIL] Normal-vision floor    worst all-pairs #898781↔#1baf7a ΔE 14.5 (normal) — below 15, hard to tell apart even with full color vision
  [WARN] Contrast vs surface    below 3:1 — relief required (visible labels or table view): [["#eda100",2.11],["#1baf7a",2.74]]

  → FAILED — fix the marked checks  (CVD in the 6–8 floor band is legal ONLY with secondary encoding: direct labels, gaps, or texture)
  scope: categorical palettes only. For a lone status/text color check WCAG text contrast; for a sequential ramp, lightness monotonicity.
```

### filled_dark

```
/tmp/claude-1000/bundled-skills/2.1.285/5f88d207b57b51bcce81e1355cb0a1dc/dataviz/scripts/validate_palette.js #d03b3b,#c98500,#199e70,#3987e5 --mode dark --surface #1a1a19 --pairs all
Palette (dark, surface #1a1a19, categorical): 4 slots
  [PASS] Lightness band         all 4 inside L 0.48–0.67
  [PASS] Chroma floor           all 4 >= 0.1
  [WARN] CVD separation         worst all-pairs #199e70↔#d03b3b ΔE 7.2 (deutan) · tritan 4.0
  [PASS] Normal-vision floor    worst all-pairs #c98500↔#d03b3b ΔE 16.9 (normal)
  [PASS] Contrast vs surface    all 4 >= 3:1

  → ALL CHECKS PASS  (CVD in the 6–8 floor band is legal ONLY with secondary encoding: direct labels, gaps, or texture)
  scope: categorical palettes only. For a lone status/text color check WCAG text contrast; for a sequential ramp, lightness monotonicity.
```

### with_unseen_dark

```
/tmp/claude-1000/bundled-skills/2.1.285/5f88d207b57b51bcce81e1355cb0a1dc/dataviz/scripts/validate_palette.js #d03b3b,#c98500,#199e70,#3987e5,#898781 --mode dark --surface #1a1a19 --pairs all
Palette (dark, surface #1a1a19, categorical): 5 slots
  [PASS] Lightness band         all 5 inside L 0.48–0.67
  [FAIL] Chroma floor           below floor (reads gray): [["#898781",0.009]]
  [FAIL] CVD separation         worst all-pairs #898781↔#199e70 ΔE 2.0 (deutan) · tritan 4.0
  [FAIL] Normal-vision floor    worst all-pairs #898781↔#199e70 ΔE 12.6 (normal) — below 15, hard to tell apart even with full color vision
  [PASS] Contrast vs surface    all 5 >= 3:1

  → FAILED — fix the marked checks  (CVD in the 6–8 floor band is legal ONLY with secondary encoding: direct labels, gaps, or texture)
  scope: categorical palettes only. For a lone status/text color check WCAG text contrast; for a sequential ramp, lightness monotonicity.
```

### retired_light

```
/tmp/claude-1000/bundled-skills/2.1.285/5f88d207b57b51bcce81e1355cb0a1dc/dataviz/scripts/validate_palette.js #0ca30c,#fab219,#d03b3b,#4a3aa7,#898781 --mode light --surface #fcfcfb --pairs all
Palette (light, surface #fcfcfb, categorical): 5 slots
  [FAIL] Lightness band         outside band: [["#fab219",0.811]]
  [FAIL] Chroma floor           below floor (reads gray): [["#898781",0.009]]
  [FAIL] CVD separation         worst all-pairs #d03b3b↔#0ca30c ΔE 4.1 (deutan) · tritan 11.9
  [PASS] Normal-vision floor    worst all-pairs #898781↔#d03b3b ΔE 18.9 (normal)
  [WARN] Contrast vs surface    below 3:1 — relief required (visible labels or table view): [["#fab219",1.79]]

  → FAILED — fix the marked checks  (CVD in the 6–8 floor band is legal ONLY with secondary encoding: direct labels, gaps, or texture)
  scope: categorical palettes only. For a lone status/text color check WCAG text contrast; for a sequential ramp, lightness monotonicity.
```
