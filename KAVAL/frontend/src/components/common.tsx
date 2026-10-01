import type { ReactNode } from 'react'
import { ApiError } from '../api/client'
import type { Meta } from '../api/types'
import { when } from '../lib/format'

/**
 * A validation split regime, rendered beside the metric it belongs to.
 *
 * leakage-protocol rule 1 / react-map-ui rule 2: a bare accuracy figure on
 * screen is a bug. When the API returns `split_regime: null` for a response that
 * does contain a metric, this renders a visible defect notice rather than
 * quietly borrowing the headline regime from elsewhere.
 */
export function RegimeChip({ regime, metric = true }: { regime: string | null | undefined; metric?: boolean }) {
  if (!metric) return null
  if (!regime)
    return (
      <span className="chip warn" title="The API returned this metric without meta.split_regime. Nothing on this screen will guess one.">
        ⚠ split regime not reported by the API
      </span>
    )
  return (
    <span className="chip regime" title="The validation split this metric was measured under.">
      split: {regime}
    </span>
  )
}

/** Sources + generation time, straight from `meta`. Every panel carries one. */
export function Provenance({ meta, extra }: { meta: Meta | null | undefined; extra?: string }) {
  if (!meta) return null
  return (
    <div className="prov">
      {meta.sources.length ? meta.sources.join(' · ') : 'no source declared'} · n={meta.n.toLocaleString()} ·{' '}
      {meta.split_regime ? `split: ${meta.split_regime} · ` : ''}
      {when(meta.generated_at)}
      {extra ? ` · ${extra}` : ''}
    </div>
  )
}

export function Tile({
  label, value, note, children,
}: { label: string; value?: ReactNode; note?: ReactNode; children?: ReactNode }) {
  return (
    <div className="tile">
      <div className="label">{label}</div>
      {value !== undefined && <div className="value">{value}</div>}
      {children}
      {note && <div className="note">{note}</div>}
    </div>
  )
}

export function Loading({ what }: { what: string }) {
  return <div className="state">Loading {what}…</div>
}

/**
 * The only thing shown when a number is unavailable. Never a placeholder value:
 * a plausible-looking fake on an audit screen is the worst possible failure.
 */
export function ErrorState({ error, what }: { error: Error; what: string }) {
  const api = error instanceof ApiError ? error : null
  const phaseMissing = api?.isPhaseMissing
  return (
    <div className="state error">
      <h3>{phaseMissing ? `${what} is not available yet` : `${what} could not be loaded`}</h3>
      <p style={{ margin: '0 0 6px' }}>{error.message}</p>
      {api?.status === 0 && (
        <p style={{ margin: 0 }}>
          Start the backend with{' '}
          <code>.venv/bin/uvicorn KAVAL.api.main:app --reload --port 8077</code>, or run this UI
          with <code>VITE_USE_MOCK=1 npm run dev</code> to see it against synthetic data.
        </p>
      )}
      <p style={{ margin: '8px 0 0', color: 'var(--ink-muted)', fontSize: 12 }}>
        No figure is shown in place of the missing one — by design.
      </p>
    </div>
  )
}

export function Empty({ what }: { what: string }) {
  return <div className="state">No {what} matched the current filters and thresholds.</div>
}
