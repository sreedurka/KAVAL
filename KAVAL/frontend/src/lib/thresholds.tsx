import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import type { Thresholds } from '../api/types'

function sameTriple(a: Thresholds, b: Thresholds): boolean {
  return (
    a.confidence_high === b.confidence_high &&
    a.trust_floor === b.trust_floor &&
    a.trust_high === b.trust_high
  )
}

/**
 * One threshold triple for the whole app.
 *
 * audit-signals: "never hard-code a threshold in more than one place". The one
 * place is KAVAL/kaval/config.py; it arrives here as `meta.thresholds` on the
 * first /parcels call and is sent back on every route that accepts it, so the
 * map, the worklist and the auto-clear saving always describe the same policy.
 */
export interface ThresholdCtx {
  /** What the sliders currently say. */
  value: Thresholds
  /** What the API's config says. Never written by this app. */
  defaults: Thresholds
  set: (patch: Partial<Thresholds>) => void
  reset: () => void
  /** True while the sliders match the API config. */
  atDefaults: boolean
}

const Ctx = createContext<ThresholdCtx | null>(null)

export function ThresholdProvider({ defaults, children }: { defaults: Thresholds; children: ReactNode }) {
  const [value, setValue] = useState<Thresholds>(defaults)
  const set = useCallback((patch: Partial<Thresholds>) => setValue((v) => ({ ...v, ...patch })), [])
  const reset = useCallback(() => setValue(defaults), [defaults])
  const ctx = useMemo<ThresholdCtx>(
    () => ({ value, defaults, set, reset, atDefaults: sameTriple(value, defaults) }),
    [value, defaults, set, reset],
  )
  return <Ctx.Provider value={ctx}>{children}</Ctx.Provider>
}

export function useThresholds(): ThresholdCtx {
  const c = useContext(Ctx)
  if (!c) throw new Error('useThresholds outside ThresholdProvider')
  return c
}

/** The exact triple the API routes accept. */
export function triple(t: Thresholds) {
  return {
    confidence_high: t.confidence_high,
    trust_floor: t.trust_floor,
    trust_high: t.trust_high,
  }
}
