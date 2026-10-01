/**
 * Formatting only. Nothing here may invent a value: every function takes a
 * number the API supplied, and returns "—" when the API supplied nothing.
 */

const NBSP = ' '

export const EM_DASH = '—'

export function n(x: number | null | undefined, digits = 0): string {
  if (x === null || x === undefined || !Number.isFinite(x)) return EM_DASH
  return x.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

export function pct(x: number | null | undefined, digits = 1): string {
  if (x === null || x === undefined || !Number.isFinite(x)) return EM_DASH
  return `${(x * 100).toFixed(digits)}%`
}

/** For values the API already expressed as a percentage. */
export function pctRaw(x: number | null | undefined, digits = 1): string {
  if (x === null || x === undefined || !Number.isFinite(x)) return EM_DASH
  return `${x.toFixed(digits)}%`
}

export function ha(x: number | null | undefined, digits = 1): string {
  if (x === null || x === undefined || !Number.isFinite(x)) return EM_DASH
  return `${n(x, digits)}${NBSP}ha`
}

export function metres(x: number | null | undefined): string {
  if (x === null || x === undefined || !Number.isFinite(x)) return EM_DASH
  if (x >= 1000) return `${(x / 1000).toFixed(2)}${NBSP}km`
  return `${Math.round(x)}${NBSP}m`
}

export function signed(x: number | null | undefined, digits = 2): string {
  if (x === null || x === undefined || !Number.isFinite(x)) return EM_DASH
  return `${x > 0 ? '+' : ''}${x.toFixed(digits)}`
}

export function fixed(x: number | null | undefined, digits = 2): string {
  if (x === null || x === undefined || !Number.isFinite(x)) return EM_DASH
  return x.toFixed(digits)
}

export function when(iso: string | null | undefined): string {
  if (!iso) return EM_DASH
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? EM_DASH : d.toLocaleString()
}
