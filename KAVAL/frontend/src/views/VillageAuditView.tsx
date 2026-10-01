import { useMemo, useState } from 'react'
import { api } from '../api/client'
import type { CropAreaRow } from '../api/types'
import { useQuery } from '../lib/useQuery'
import { ErrorState, Loading, Provenance, RegimeChip, Tile } from '../components/common'
import { ChartFrame, DivergingBars, HBars } from '../charts/primitives'
import { EM_DASH, ha, n, pct, pctRaw, signed } from '../lib/format'

/**
 * Village audit panel — satellite crop mix against the published Agrisnet registry.
 *
 * Both API caveats sit above the chart, always visible, because the registry is
 * the aggregate of the same survey we audit: this is a consistency check, and a
 * reviewer must not be able to read it as external validation.
 *
 * Sorted by |delta_share|: "where should a district officer look first" is a
 * question of divergence magnitude, not of which side is larger.
 */
export function VillageAuditView() {
  const [minHa, setMinHa] = useState(1)
  const [crop, setCrop] = useState('')
  const [village, setVillage] = useState('')

  const deltaQ = useQuery(() => api.registryDelta({ min_registry_ha: minHa }), [minHa])
  // Totals come from the API (kaval/area.py aggregates shared fields at field level);
  // the browser never sums area itself. A selected village shows that village's rows.
  const areaQ = useQuery(
    () => api.cropArea({ group_by: village ? 'village' : 'taluk', source: 'predicted' }),
    [village],
  )

  const payload = deltaQ.data?.data
  const rows = useMemo(
    () => [...(payload?.rows ?? [])].sort((a, b) => Math.abs(b.delta_share) - Math.abs(a.delta_share)),
    [payload],
  )
  const crops = useMemo(() => [...new Set(rows.map((r) => r.crop))].sort(), [rows])
  const villages = useMemo(() => [...new Set(rows.map((r) => r.village))].sort(), [rows])
  const filtered = rows.filter(
    (r) => (!crop || r.crop === crop) && (!village || r.village === village),
  )
  const top = filtered.slice(0, 18)
  const regime = deltaQ.data?.meta.split_regime

  return (
    <div>
      {payload && (
        <div className="caveats" role="note" aria-label="How to read this comparison">
          <div className="caveat">
            <strong>Not independent validation.</strong>{' '}
            {payload.independence_caveat ?? 'The API did not supply the independence caveat.'}
          </div>
          <div className="caveat">
            <strong>Share, not hectares.</strong>{' '}
            {payload.scale_caveat ?? 'The API did not supply the scale caveat.'}
          </div>
        </div>
      )}

      <div className="row" style={{ marginBottom: 12 }}>
        <label style={{ fontSize: 12, color: 'var(--ink-2)' }}>
          Minimum registry area{' '}
          <select value={minHa} onChange={(e) => setMinHa(Number(e.target.value))}>
            {[0, 1, 5, 10, 25].map((v) => <option key={v} value={v}>{v} ha</option>)}
          </select>
        </label>
        <label style={{ fontSize: 12, color: 'var(--ink-2)' }}>
          Crop{' '}
          <select value={crop} onChange={(e) => setCrop(e.target.value)}>
            <option value="">all crops</option>
            {crops.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        <label style={{ fontSize: 12, color: 'var(--ink-2)' }}>
          Village{' '}
          <select value={village} onChange={(e) => setVillage(e.target.value)}>
            <option value="">all villages</option>
            {villages.map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
        </label>
      </div>

      {deltaQ.loading ? (
        <Loading what="the registry comparison" />
      ) : deltaQ.error ? (
        <ErrorState error={deltaQ.error} what="The registry comparison" />
      ) : payload ? (
        <>
          <div className="grid3" style={{ marginBottom: 14 }}>
            <Tile
              label="Registry compared"
              value={payload.season ?? EM_DASH}
              note="Tamil Nadu Agrisnet village-wise Digital Crop Survey report."
            />
            <Tile
              label="Village x crop rows"
              value={n(filtered.length)}
              note={`of ${n(rows.length)} returned at the area filter.`}
            />
            <Tile
              label="Registry area outside our scope"
              value={pctRaw(payload.registry_out_of_scope_pct)}
              note="Registry hectares in crops or villages the satellite model does not cover."
            />
          </div>

          <div className="card">
            <ChartFrame
              title="Village x crop, sorted by share divergence"
              aside={<><RegimeChip regime={regime} /><span className="chip">percentage points of village crop share</span></>}
            >
              <DivergingBars
                unit="pp"
                fmt={(v) => `${Math.abs(v).toFixed(1)}`}
                rows={top.map((r) => ({
                  key: `${r.village}|${r.crop}`,
                  label: `${r.village} · ${r.crop}`,
                  value: r.delta_share * 100,
                  note: `registry ${pct(r.registry_share)} · satellite ${pct(r.satellite_share)} · mean confidence ${pct(r.mean_confidence)}`,
                }))}
              />
            </ChartFrame>
            <p style={{ fontSize: 12, color: 'var(--ink-2)', margin: '4px 0 0' }}>
              A positive bar means the satellite sees a larger share of that crop than the registry
              publishes. Neither side is assumed correct, and because the registry aggregates the
              same survey, agreement is weaker evidence than it looks.
            </p>
            <Provenance meta={deltaQ.data?.meta} />
          </div>

          {payload.systematic_bias_by_crop && payload.systematic_bias_by_crop.length > 0 && (
            <div className="card">
              <h2>Systematic bias by crop</h2>
              <p className="sub">
                Satellite share minus registry share, pooled over villages. A consistent sign is a
                model or registry habit, not a village finding.
              </p>
              <table className="data">
                <thead>
                  <tr>
                    <th>Crop</th>
                    <th className="num">Registry share</th>
                    <th className="num">Satellite share</th>
                    <th className="num">Bias (pp)</th>
                  </tr>
                </thead>
                <tbody>
                  {payload.systematic_bias_by_crop.map((b) => (
                    <tr key={b.crop}>
                      <td>{b.crop}</td>
                      <td className="num">{pct(b.registry_share)}</td>
                      <td className="num">{pct(b.satellite_share)}</td>
                      <td className="num" style={{ color: b.bias < 0 ? 'var(--div-neg)' : 'var(--div-pos)', fontWeight: 600 }}>
                        {signed(b.bias * 100, 1)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="row" style={{ marginTop: 8 }}><RegimeChip regime={regime} /></div>
              <Provenance meta={deltaQ.data?.meta} />
            </div>
          )}

          <div className="card">
            <h2>Full comparison</h2>
            <p className="sub">
              {n(filtered.length)} village x crop rows, largest share divergence first. Implied
              hectares extrapolate the share gap to the registry's village area; they are not measured.
            </p>
            <div className="scroll">
              <table className="data">
                <thead>
                  <tr>
                    <th>Village</th>
                    <th>Crop</th>
                    <th className="num">Registry ha</th>
                    <th className="num">Registry share</th>
                    <th className="num">Satellite ha</th>
                    <th className="num">Satellite share</th>
                    <th className="num">Delta share (pp)</th>
                    <th className="num">Implied ha delta</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((r) => (
                    <tr key={`${r.village}|${r.crop}`}>
                      <td>{r.village}</td>
                      <td>{r.crop}</td>
                      <td className="num">{ha(r.registry_ha)}</td>
                      <td className="num">{pct(r.registry_share)}</td>
                      <td className="num">{ha(r.sat_ha)}</td>
                      <td className="num">{pct(r.satellite_share)}</td>
                      <td className="num" style={{ color: r.delta_share < 0 ? 'var(--div-neg)' : 'var(--div-pos)', fontWeight: 600 }}>
                        {signed(r.delta_share * 100, 1)}
                      </td>
                      <td className="num">{signed(r.implied_ha_delta, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="row" style={{ marginTop: 8 }}><RegimeChip regime={regime} /></div>
            <Provenance meta={deltaQ.data?.meta} />
          </div>
        </>
      ) : null}

      <div className="card">
        <h2>Satellite-estimated crop area — {village || 'whole taluk'}</h2>
        <p className="sub">
          Prediction-side areas with the mean calibrated confidence behind each. A large area
          resting on low mean confidence is not a usable statistic.
        </p>
        {areaQ.loading ? (
          <Loading what="crop areas" />
        ) : areaQ.error ? (
          <ErrorState error={areaQ.error} what="Crop areas" />
        ) : (
          <>
            <div className="row" style={{ marginBottom: 6 }}><RegimeChip regime={areaQ.data?.meta.split_regime} /></div>
            <CropAreaChart
              rows={((areaQ.data?.data ?? []) as CropAreaRow[]).filter(
                (r) => !village || r.village_name === village,
              )}
            />
            <Provenance meta={areaQ.data?.meta} />
          </>
        )}
      </div>
    </div>
  )
}

function CropAreaChart({ rows }: { rows: CropAreaRow[] }) {
  const sorted = [...rows].sort((a, b) => b.area_ha - a.area_ha)
  if (!sorted.length) return <div className="state">No crop-area rows returned.</div>
  const max = Math.max(...sorted.map((c) => c.area_ha))
  return (
    <HBars
      max={max}
      fmt={(v) => `${v.toFixed(0)}`}
      labelWidth={140}
      series={[{ key: 'area', label: 'satellite-estimated area (ha)', color: 'var(--series-1)' }]}
      rows={sorted.map((c) => ({
        key: c.crop,
        label: c.crop,
        values: [c.area_ha],
        note:
          `${n(c.parcels)} parcels · mean calibrated confidence ${pct(c.mean_confidence)}` +
          (c.conflicted_area_ha ? ` · ${c.conflicted_area_ha.toFixed(1)} ha in shared fields whose records disagree` : ''),
      }))}
    />
  )
}
