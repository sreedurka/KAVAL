/**
 * The agreement-status palette.
 *
 * Built by the method in the `dataviz` skill and VALIDATED with its script, not
 * chosen by eye. Run from the skill directory:
 *
 *   node scripts/validate_palette.js "#2a78d6,#eda100,#d03b3b,#1baf7a" \
 *        --mode light --pairs all
 *   node scripts/validate_palette.js "#3987e5,#c98500,#d03b3b,#199e70" \
 *        --mode dark  --pairs all
 *
 * Both runs report ALL CHECKS PASS. `--pairs all` is the right pairlist because
 * a map is a choropleth: any two statuses can end up adjacent, so every pair has
 * to separate, not just neighbours in a legend.
 *
 * Why these hues, and not the obvious ones:
 *
 *   CONFIRMED is BLUE, not green. The reflex palette (green = agrees, red =
 *   disagrees) fails hard: #0ca30c against #d03b3b measures CVD ΔE 4.1 under
 *   deuteranopia, i.e. the product's two most consequential states are
 *   indistinguishable for the most common form of colour blindness. Blue↔red is
 *   the validated diverging pair; it reads as "opposite" and it separates.
 *
 *   UNVERIFIABLE is TEAL and always HATCHED. It sits off the severity axis on
 *   purpose — it is not "more or less wrong" than UNCERTAIN, it is a different
 *   kind of problem (the record, not the field). Teal↔red is the one pair in the
 *   6–8 CVD warn band in dark mode (ΔE 7.2), which the skill permits only with
 *   secondary encoding — the 45° hatch is exactly that, and it is on by default
 *   for this status rather than as an accessibility fallback.
 *
 *   UNSEEN is achromatic and carries NO FILL — outline only. It fails the
 *   validator's chroma floor by design; it is the "no record" slot and must not
 *   look like a state anyone can act on.
 *
 * Salience is not carried by hue alone. DISPUTED renders at full fill opacity
 * with the thickest stroke and the largest radius; CONFIRMED recedes to a low
 * opacity wash. That ordering is what makes the money rows pop, not saturation.
 */

import type { AgreementStatus } from '../api/types'

export interface StatusStyle {
  /** CSS custom-property name; the value swaps for dark mode in styles.css. */
  varName: string
  fillOpacity: number
  weight: number
  radius: number
  hatched: boolean
  outlineOnly: boolean
}

/** Render order = severity order. DISPUTED first everywhere: legends, bars, tables. */
export const STATUS_STYLE: Record<AgreementStatus, StatusStyle> = {
  DISPUTED: { varName: '--st-disputed', fillOpacity: 0.95, weight: 1.8, radius: 7.5, hatched: false, outlineOnly: false },
  UNCERTAIN: { varName: '--st-uncertain', fillOpacity: 0.5, weight: 0.8, radius: 5, hatched: false, outlineOnly: false },
  UNVERIFIABLE: { varName: '--st-unverifiable', fillOpacity: 0.85, weight: 1, radius: 5, hatched: true, outlineOnly: false },
  CONFIRMED: { varName: '--st-confirmed', fillOpacity: 0.22, weight: 0.6, radius: 4, hatched: false, outlineOnly: false },
  UNSEEN: { varName: '--st-unseen', fillOpacity: 0, weight: 1.1, radius: 4.5, hatched: false, outlineOnly: true },
}

/** Read the resolved hex for a status from the DOM, so light/dark stay in CSS. */
export function statusColor(status: AgreementStatus, root?: HTMLElement): string {
  const el = root ?? document.documentElement
  const v = getComputedStyle(el).getPropertyValue(STATUS_STYLE[status].varName).trim()
  return v || '#898781'
}

/**
 * What each status MEANS and what it obliges someone to do.
 *
 * Presentation copy, not logic — the rule that assigns a status lives in
 * `kaval/audit.py` and is applied server-side at the caller's thresholds. The
 * browser derives nothing.
 */
export const STATUS_MEANING: Record<AgreementStatus, { action: string; blurb: string }> = {
  DISPUTED: {
    action: 'Top of the field worklist',
    blurb:
      'Satellite disagrees with the survey at high calibrated confidence. Not "wrong" — ' +
      'the two sources disagree, and a field visit decides which is right.',
  },
  UNCERTAIN: {
    action: 'Route by remaining budget',
    blurb: 'Calibrated confidence is below the high threshold. The model cannot separate the classes here.',
  },
  UNVERIFIABLE: {
    action: 'Re-survey the record, not the parcel',
    blurb:
      'Record Trust Score is below the floor — a large capture-event bag, a distant photograph, ' +
      'a mixed-crop declaration. The problem is the evidence, so visiting the field would not fix it.',
  },
  CONFIRMED: {
    action: 'Auto-clear — skip next season’s visit',
    blurb: 'Satellite agrees at high calibrated confidence on a record we trust. Nothing to do here.',
  },
  UNSEEN: {
    action: 'Satellite-only prediction, no audit claim',
    blurb: 'No survey record exists for this parcel, so there is nothing to agree or disagree with.',
  },
}

/** Categorical slots for the secondary crop-class layer and for charts. */
export const SERIES_VARS = [
  '--series-1', '--series-2', '--series-3', '--series-4',
  '--series-5', '--series-6', '--series-7', '--series-8',
] as const

export function seriesVar(i: number): string {
  // Never cycle a 9th hue. Past eight, the caller folds into "Other".
  return `var(${SERIES_VARS[Math.min(i, SERIES_VARS.length - 1)]})`
}
