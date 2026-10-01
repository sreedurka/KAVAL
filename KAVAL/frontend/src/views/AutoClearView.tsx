import { api } from '../api/client'
import { triple, useThresholds } from '../lib/thresholds'
import { useDebounced, useQuery } from '../lib/useQuery'
import { ErrorState, Loading, Provenance, RegimeChip, Tile } from '../components/common'
import { ChartFrame, HBars } from '../charts/primitives'
import { EM_DASH, fixed, ha, n, pct, pctRaw } from '../lib/format'

/**
 * Auto-clear — the parcels a surveyor need not walk to next season.
 *
 * The saving is meaningless without the assumption behind it, so
 * `cost_assumption` is rendered in full, verbatim from the API, immediately
 * beside the number it produces. A surveyor-day figure whose denominator is
 * hidden is a sales claim, not an audit finding.
 */
export function AutoClearView() {
  const { value: th } = useThresholds()
  const dth = useDebounced(th)
  const q = useQuery(
    () => api.autoClear(triple(dth)),
    [dth.confidence_high, dth.trust_floor, dth.trust_high],
  )

  if (q.loading) return <Loading what="the auto-clear list" />
  if (q.error) return <ErrorState error={q.error} what="The auto-clear panel" />
  if (!q.data) return null

  const d = q.data.data
  const saved = d.surveyor_days_saved
  const baseline = d.baseline_surveyor_days
  const remaining = Number.isFinite(baseline) && Number.isFinite(saved) ? baseline - saved : null

  return (
    <div>
      <div className="grid3" style={{ marginBottom: 14 }}>
        <Tile
          label="Parcels safe to skip"
          value={n(d.parcels)}
          note={`${pctRaw(d.pct_of_parcels)} of parcels · ${ha(d.area_ha)}`}
        />
        <Tile
          label="Surveyor-days saved"
          value={fixed(saved, 1)}
          note={`against a baseline of ${fixed(baseline, 1)} days to visit everything`}
        />
        <Tile label="Expected residual error rate">
          <div className="value">
            {d.expected_residual_error_rate === null ? EM_DASH : pct(d.expected_residual_error_rate)}
          </div>
          <div style={{ marginTop: 6 }}>
            <RegimeChip regime={q.data.meta.split_regime} />
          </div>
          <div className="note">
            ≈{fixed(d.expected_parcels_wrongly_cleared, 0)} of the {n(d.parcels)} cleared parcels
            are expected to be cleared in error.
          </div>
        </Tile>
      </div>

      <div className="card">
        <h2>What this panel does not claim</h2>
        <p className="sub">
          The obvious figure here would be "accuracy within the cleared set". It is not reported,
          because it is circular.
        </p>
        <p style={{ fontSize: 13, margin: '0 0 10px' }}>
          <code>CONFIRMED</code> is <em>defined</em> as the model agreeing with the survey, so the
          share of cleared parcels where the two agree is 100% by construction. It would look like
          a validation result and contain no information. The honest quantity is the one above: the
          residual risk that satellite and survey err <em>together</em>, roughly estimated from the
          calibrated confidence. It is a proxy, not a bound (correction #1).
        </p>
        <p style={{ fontSize: 13, margin: 0, color: 'var(--ink-2)' }}>{d.residual_note}</p>
        <div className="row" style={{ marginTop: 10 }}>
          <RegimeChip regime={q.data.meta.split_regime} />
          <span className="chip">
            {pct(d.expected_residual_error_rate)} × {n(d.parcels)} cleared ≈{' '}
            {fixed(d.expected_parcels_wrongly_cleared, 0)} parcels
          </span>
        </div>
        <Provenance meta={q.data.meta} />
      </div>

      <div className="card">
        <ChartFrame title="Where the season's surveyor-days go" aside={<span className="chip">days</span>}>
          <HBars
            max={Math.max(baseline || 1, 1)}
            fmt={(v) => v.toFixed(0)}
            labelWidth={210}
            rowHeight={26}
            series={[{ key: 'days', label: 'surveyor-days', color: 'var(--series-1)' }]}
            rows={[
              {
                key: 'baseline',
                label: 'Visit every parcel (status quo)',
                values: [baseline],
                note: 'What the current Digital Crop Survey cycle costs on this cost assumption.',
              },
              {
                key: 'remaining',
                label: 'Visit only what KAVAL does not clear',
                values: [remaining],
                note: 'Baseline minus the auto-cleared parcels, at the thresholds currently set.',
              },
              {
                key: 'saved',
                label: 'Saved by auto-clear',
                values: [saved],
                note: 'Parcels where satellite and survey agree at high calibrated confidence on a trusted record.',
              },
            ]}
          />
        </ChartFrame>
        <Provenance meta={q.data.meta} />
      </div>

      <div className="card">
        <h2>The cost assumption</h2>
        <p className="sub">Stated, not hidden. Change it and every saving on this page changes.</p>
        <table className="data">
          <tbody>
            <tr>
              <th style={{ textTransform: 'none', letterSpacing: 0, fontSize: 12.5, color: 'var(--ink-2)', fontWeight: 500 }}>
                Parcels a surveyor covers per day
              </th>
              <td className="num" style={{ fontWeight: 650 }}>
                {n(d.cost_assumption.parcels_per_surveyor_day)}
              </td>
            </tr>
          </tbody>
        </table>
        <p style={{ fontSize: 12, color: 'var(--ink-2)', marginTop: 10, marginBottom: 0 }}>
          {d.cost_assumption.note}
        </p>
        <p style={{ fontSize: 12, color: 'var(--ink-2)', marginTop: 10, marginBottom: 0 }}>
          This figure is an assumption supplied by the backend, not a measurement. It is the one
          number on this screen that FarmwiseAI can replace with an actual and get a directly
          usable answer.
        </p>
        <Provenance meta={q.data.meta} />
      </div>

      <div className="card">
        <h2>What auto-clear does and does not claim</h2>
        <ul style={{ fontSize: 12.5, color: 'var(--ink-2)', margin: 0, paddingLeft: 18, lineHeight: 1.7 }}>
          <li>
            It claims the <em>record</em> is consistent with the satellite at the set thresholds —
            not that the crop is certainly what the record says.
          </li>
          <li>
            The residual is <em>estimated</em>, from calibrated confidence. Settling it needs an
            independent field audit of a sample of CONFIRMED parcels — a measurement nobody has
            made yet.
          </li>
          <li>
            It clears a parcel from <em>next season's</em> visit list. It does not retire the parcel
            from the survey permanently.
          </li>
          <li>
            Raising <code>trust_high</code> shrinks this set. That is the intended control: the
            saving and the risk move together and both are on screen.
          </li>
        </ul>
      </div>
    </div>
  )
}
