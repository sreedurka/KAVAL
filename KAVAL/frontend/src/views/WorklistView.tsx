import { useMemo, useState } from 'react'
import { api } from '../api/client'
import type { WorklistRow } from '../api/types'
import { STATUS_STYLE } from '../lib/palette'
import { triple, useThresholds } from '../lib/thresholds'
import { useDebounced, useQuery } from '../lib/useQuery'
import { ErrorState, Loading, Provenance, RegimeChip, Tile } from '../components/common'
import { ChartFrame, HBars } from '../charts/primitives'
import { EM_DASH, fixed, ha, metres, n, pct, pctRaw } from '../lib/format'

/**
 * Field worklist with a live budget slider — the core product view.
 *
 * The slider is the argument. Moving N re-asks the API for the N parcels that
 * maximise expected corrections, and the counterfactual beside it says what the
 * same N visits chosen at random would have found. There is deliberately no
 * "lift" multiple: routed ÷ random disagreements is pinned at 1 / base rate by
 * construction (correction #2). Ranking quality is shown by the confidence tile.
 *
 * audit-signals: expected corrections is a sum of probabilities. Area steers the
 * ranking but must not inflate the count of corrections claimed, so this screen
 * never multiplies the two.
 */
export function WorklistView() {
  const { value: th } = useThresholds()
  const [budgetRaw, setBudgetRaw] = useState(500)
  const [village, setVillage] = useState('')
  const budget = useDebounced(budgetRaw, 260)
  const dth = useDebounced(th)

  const villagesQ = useQuery(() => api.cropArea({ group_by: 'village', source: 'predicted' }), [])
  const q = useQuery(
    () => api.worklist({ ...triple(dth), budget, village: village || undefined }),
    [budget, village, dth.confidence_high, dth.trust_floor, dth.trust_high],
  )
  // The export must reproduce the queue on screen, so it carries the same scope.
  const exportScope = { ...triple(dth), budget, village: village || undefined }

  const villageNames = useMemo(() => {
    const s = new Set<string>()
    for (const r of villagesQ.data?.data ?? []) if (r.village_name) s.add(r.village_name)
    return [...s].sort()
  }, [villagesQ.data])

  const econ = q.data?.data.economics
  const rows = (q.data?.data.worklist ?? []) as WorklistRow[]
  const routed = econ?.estimated_corrections_routed ?? null
  const random = econ?.estimated_corrections_random ?? null
  const randomSd = econ?.estimated_corrections_random_std
  const cap = econ?.base_disagreement_rate ? 1 / econ.base_disagreement_rate : null

  return (
    <div>
      <div className="card">
        <h2>Verification budget</h2>
        <p className="sub">
          Given N field visits, which N parcels? The objective is expected label corrections,
          not a heuristic ranking.
        </p>

        <div className="row" style={{ alignItems: 'flex-end', gap: 18 }}>
          <label className="slider" style={{ flex: 1, marginBottom: 0 }} htmlFor="budget">
            <span className="head">
              <span className="name">Field visits available (N)</span>
              <span className="val">{n(budgetRaw)}</span>
            </span>
            <span className="why">
              Drag. The estimated corrections, the random-visit counterfactual and the
              ranking-quality check all re-query the API.
            </span>
            <input
              id="budget"
              type="range"
              min={10}
              max={5000}
              step={10}
              value={budgetRaw}
              onChange={(e) => setBudgetRaw(Number(e.target.value))}
            />
          </label>
          <label style={{ fontSize: 12, color: 'var(--ink-2)' }}>
            Village{' '}
            <select value={village} onChange={(e) => setVillage(e.target.value)}>
              <option value="">whole taluk</option>
              {villageNames.map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </label>
        </div>
      </div>

      {q.loading ? (
        <Loading what="the worklist" />
      ) : q.error ? (
        <ErrorState error={q.error} what="The field worklist" />
      ) : !econ ? (
        <div className="state">The API returned no economics block for this budget.</div>
      ) : (
        <>
          <div className="grid3" style={{ marginBottom: 14 }}>
            <Tile
              label="Estimated corrections — KAVAL routing"
              value={fixed(routed, 1)}
              note={`from ${n(econ.budget)} visits · ${pctRaw(econ.pct_of_parcels_visited ?? null, 2)} of parcels · ${ha(econ.routed_area_ha ?? null)} covered`}
            />
            <Tile
              label="Estimated corrections — random visits"
              value={fixed(random, 1)}
              note={
                randomSd !== undefined
                  ? `mean of 200 draws, sd ${fixed(randomSd, 2)} — the counterfactual, not a rival method`
                  : 'counterfactual'
              }
            />
            <Tile
              label="Ranking quality"
              value={
                econ.routed_mean_confidence === undefined
                  ? EM_DASH
                  : `${fixed(econ.routed_mean_confidence, 3)} vs ${fixed(econ.all_disagreements_mean_confidence ?? null, 3)}`
              }
              note={`Mean calibrated confidence of routed parcels vs all ${n(econ.total_disagreements_available ?? 0)} disagreements: are the better-evidenced ones first? ${n(econ.routed_disagreements_found ?? 0)} of ${n(econ.budget)} routed parcels are disagreements (targeting ${fixed(econ.targeting_efficiency ?? null, 2)}×, capped at ${fixed(cap, 2)}× by construction, so not a result).`}
            />
          </div>

          <div className="card">
            <ChartFrame
              title={`Routing versus the counterfactual at N = ${n(econ.budget)}`}
              aside={
                <span className="chip">
                  estimated corrections = Σ P(declared label needs correction), a model estimate
                </span>
              }
            >
              <HBars
                max={Math.max(routed ?? 0, random ?? 0) * 1.15 || 1}
                fmt={(v) => v.toFixed(0)}
                labelWidth={186}
                rowHeight={26}
                series={[{ key: 'ec', label: 'expected corrections', color: 'var(--series-1)' }]}
                rows={[
                  {
                    key: 'routed',
                    label: 'KAVAL-routed visits',
                    values: [routed],
                    note: 'Ranked by P(label needs correction) × area weight, clipped to [0.25, 4].',
                  },
                  {
                    key: 'random',
                    label: 'Random visits (baseline)',
                    values: [random],
                    errors: [randomSd ?? null],
                    note: 'Mean over repeated random draws of the same budget; whisker is the standard deviation of the draws.',
                  },
                ]}
              />
            </ChartFrame>
            <p style={{ fontSize: 12, color: 'var(--ink-2)', margin: 0 }}>
              Both bars are the same measure on the same axis. The baseline is drawn in the same
              hue deliberately — it is the same quantity spent differently, not a second series.
            </p>
            <Provenance meta={q.data?.meta} />
            <div className="row" style={{ marginTop: 8 }}>
              <RegimeChip regime={q.data?.meta.split_regime ?? null} />
              <span className="chip">
                thresholds sent: confidence_high={fixed(dth.confidence_high, 2)} · trust_floor=
                {fixed(dth.trust_floor, 2)} · trust_high={fixed(dth.trust_high, 2)}
              </span>
            </div>
          </div>

          <div className="card">
            <h2>The queue</h2>
            <p className="sub">
              {n(rows.length)} parcels, highest expected correction first. This is what a field
              officer exports.
            </p>
            <div className="row" style={{ marginBottom: 8 }}>
              <a className="btn primary" href={api.exportUrl({ fmt: 'csv', ...exportScope })}>
                Export CSV
              </a>
              <a className="btn" href={api.exportUrl({ fmt: 'geojson', ...exportScope })}>
                Export GeoJSON
              </a>
              <span style={{ fontSize: 11, color: 'var(--ink-muted)' }}>
                Exports this queue: the same {n(budget)} visits, in this order, at these thresholds.
              </span>
            </div>
            <div className="scroll">
              <table className="data">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Parcel</th>
                    <th>Village</th>
                    <th>Status</th>
                    <th>Declared</th>
                    <th>Satellite</th>
                    <th className="num" title="P(declared label needs correction), discounted by measured model accuracy, so it cannot exceed it">P(correction)</th>
                    <th className="num">Conf.</th>
                    <th className="num">Trust</th>
                    <th className="num">Bag</th>
                    <th className="num">Photo</th>
                    <th className="num">Area</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.slice(0, 400).map((r, i) => (
                    <tr key={r.parcel_id}>
                      <td className="num" style={{ color: 'var(--ink-muted)' }}>{i + 1}</td>
                      <td style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>{r.parcel_id}</td>
                      <td>{r.village_name}</td>
                      <td>
                        <span className="row" style={{ gap: 5 }}>
                          <span
                            className={`swatch${STATUS_STYLE[r.agreement_status].hatched ? ' hatch' : ''}${STATUS_STYLE[r.agreement_status].outlineOnly ? ' outline' : ''}`}
                            style={{
                              background: `var(${STATUS_STYLE[r.agreement_status].varName})`,
                              borderColor: `var(${STATUS_STYLE[r.agreement_status].varName})`,
                            }}
                            aria-hidden
                          />
                          <span style={{ fontSize: 11 }}>{r.agreement_status}</span>
                        </span>
                      </td>
                      <td>{r.y_true ?? EM_DASH}</td>
                      <td>{r.y_pred}</td>
                      <td className="num" style={{ fontWeight: 600 }}>{pct(r.p_label_wrong, 0)}</td>
                      <td className="num">{pct(r.confidence_calibrated, 0)}</td>
                      <td className="num">{fixed(r.trust_score, 2)}</td>
                      <td className="num">{n(r.bag_size)}</td>
                      <td className="num">{metres(r.photo_distance_m)}</td>
                      <td className="num">{ha(r.area_m2 / 1e4, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {rows.length > 400 && (
              <p style={{ fontSize: 11, color: 'var(--ink-muted)', marginBottom: 0 }}>
                Showing the first 400 of {n(rows.length)} routed parcels. The export carries all of them.
              </p>
            )}
            <Provenance meta={q.data?.meta} />
          </div>
        </>
      )}
    </div>
  )
}
