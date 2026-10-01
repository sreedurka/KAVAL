import { STATUSES, type AgreementStatus } from '../api/types'
import { STATUS_MEANING, STATUS_STYLE } from '../lib/palette'

import { n } from '../lib/format'

/**
 * The legend is the product's vocabulary, so it carries the ACTION for each
 * status, not just the colour. A reviewer should be able to read this column
 * and know what the system is for.
 *
 * Identity is never colour-alone: each row has a swatch, a name, the action,
 * and (for UNVERIFIABLE) a hatch; UNSEEN is an outline with no fill.
 */
export function StatusLegend({
  counts, hidden, onToggle,
}: {
  counts?: Partial<Record<AgreementStatus, number>>
  hidden: Set<AgreementStatus>
  onToggle: (s: AgreementStatus) => void
}) {
  return (
    <div className="legend">
      {STATUSES.map((s) => {
        const st = STATUS_STYLE[s]
        const on = !hidden.has(s)
        return (
          <div
            key={s}
            className="item"
            role="button"
            tabIndex={0}
            aria-pressed={on}
            onClick={() => onToggle(s)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                onToggle(s)
              }
            }}
            title={STATUS_MEANING[s].blurb}
          >
            <span
              className={`swatch${st.hatched ? ' hatch' : ''}${st.outlineOnly ? ' outline' : ''}`}
              style={{
                background: st.outlineOnly ? 'transparent' : `var(${st.varName})`,
                borderColor: `var(${st.varName})`,
                borderWidth: st.outlineOnly ? 2 : 1,
              }}
              aria-hidden
            />
            <span className="name">{s}</span>
            <span className="count">{counts ? n(counts[s] ?? 0) : ''}</span>
            <span className="meaning">{STATUS_MEANING[s].action}</span>
          </div>
        )
      })}
    </div>
  )
}
