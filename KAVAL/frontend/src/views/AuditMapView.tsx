import { useEffect, useMemo, useState } from 'react'
import { CircleMarker, GeoJSON, MapContainer, TileLayer, Tooltip, useMap } from 'react-leaflet'
import type { Feature, GeoJsonObject, Geometry } from 'geojson'
import type { Layer, PathOptions } from 'leaflet'
import { ApiError, api } from '../api/client'
import type {
  AgreementStatus, GeoParcelProps, ParcelRow, StatusSummaryRow, VillageProps,
} from '../api/types'
import { STATUSES } from '../api/types'
import { STATUS_STYLE, seriesVar } from '../lib/palette'
import { triple, useThresholds } from '../lib/thresholds'
import { useDebounced, useQuery } from '../lib/useQuery'
import { ErrorState, Loading, Provenance } from '../components/common'
import { StatusLegend } from '../components/StatusLegend'
import { ParcelPanel } from '../components/ParcelPanel'
import { StackedBar } from '../charts/primitives'
import { fixed, ha, metres, n, pct } from '../lib/format'

/** react-leaflet types `data` as GeoJsonObject; wrap a feature list for it. */
function fc<P>(features: Feature<Geometry, P>[]): GeoJsonObject {
  return { type: 'FeatureCollection', features } as unknown as GeoJsonObject
}

/** Sivagiri taluk, Tenkasi district. Used only to frame the first render. */
const FALLBACK_CENTRE: [number, number] = [9.345, 77.45]

/**
 * Injects one 45° hatch pattern into Leaflet's own overlay <svg>, so
 * UNVERIFIABLE parcels can be filled with texture rather than a fourth hue.
 * The pattern references the same CSS token as the legend swatch, so it tracks
 * light/dark automatically.
 */
function HatchDefs() {
  const map = useMap()
  useEffect(() => {
    const svg = map.getPane('overlayPane')?.querySelector('svg')
    if (!svg || svg.querySelector('#kaval-hatch')) return
    const ns = 'http://www.w3.org/2000/svg'
    const defs = document.createElementNS(ns, 'defs')
    const pat = document.createElementNS(ns, 'pattern')
    pat.setAttribute('id', 'kaval-hatch')
    pat.setAttribute('width', '5')
    pat.setAttribute('height', '5')
    pat.setAttribute('patternTransform', 'rotate(45)')
    pat.setAttribute('patternUnits', 'userSpaceOnUse')
    const bg = document.createElementNS(ns, 'rect')
    bg.setAttribute('width', '5')
    bg.setAttribute('height', '5')
    bg.setAttribute('fill', 'var(--st-unverifiable)')
    const line = document.createElementNS(ns, 'line')
    line.setAttribute('x1', '0'); line.setAttribute('y1', '0')
    line.setAttribute('x2', '0'); line.setAttribute('y2', '5')
    line.setAttribute('stroke', 'var(--surface-1)')
    line.setAttribute('stroke-width', '1.5')
    pat.appendChild(bg); pat.appendChild(line); defs.appendChild(pat)
    svg.insertBefore(defs, svg.firstChild)
  }, [map])
  return null
}

function FitTo({ bounds }: { bounds: [[number, number], [number, number]] | null }) {
  const map = useMap()
  const key = bounds ? bounds.flat().join(',') : ''
  useEffect(() => {
    if (bounds) map.fitBounds(bounds, { padding: [24, 24] })
    // Fit once per result set, not on every pan.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
  return null
}

function boundsOf(coords: number[][][] | number[][][][]): [[number, number], [number, number]] | null {
  let minLat = 90, maxLat = -90, minLon = 180, maxLon = -180, seen = false
  const walk = (c: unknown): void => {
    if (Array.isArray(c) && typeof c[0] === 'number' && typeof c[1] === 'number') {
      const [lon, lat] = c as number[]
      seen = true
      if (lat < minLat) minLat = lat
      if (lat > maxLat) maxLat = lat
      if (lon < minLon) minLon = lon
      if (lon > maxLon) maxLon = lon
      return
    }
    if (Array.isArray(c)) c.forEach(walk)
  }
  walk(coords)
  return seen ? [[minLat, minLon], [maxLat, maxLon]] : null
}

export function AuditMapView() {
  const { value: th } = useThresholds()
  const dth = useDebounced(th)
  // Deep-linkable: `#map?village=Sivagiri` opens the full-detail view for one
  // village, which is how a reviewer gets sent somewhere specific.
  const [village, setVillage] = useState(
    () => new URLSearchParams(window.location.hash.split('?')[1] ?? '').get('village') ?? '',
  )
  const [limit, setLimit] = useState(3000)
  const [hidden, setHidden] = useState<Set<AgreementStatus>>(new Set())
  const [selected, setSelected] = useState<string | null>(null)
  const [colourBy, setColourBy] = useState<'status' | 'crop'>('status')
  const [showForests, setShowForests] = useState(true)

  const thKey = [dth.confidence_high, dth.trust_floor, dth.trust_high] as const

  // Polygons. This is the primary layer: the audit is about land, not dots.
  const geoQ = useQuery(
    () => api.geoParcels({ ...triple(dth), village: village || undefined, simplify_m: 2, limit }),
    [village, limit, ...thKey],
  )
  // Attribute rows, for the crop-layer palette ordering and the fallback marker
  // layer when parcel geometry is unavailable (Phase 3 not run).
  const rowsQ = useQuery(
    () => api.parcels({ ...triple(dth), village: village || undefined, limit }),
    [village, limit, ...thKey],
  )
  const villagesGeoQ = useQuery(() => api.geoVillages(), [])
  const summaryQ = useQuery(() => api.statusSummary(triple(dth)), [...thKey])
  const villageListQ = useQuery(() => api.cropArea({ group_by: 'village', source: 'predicted' }), [])

  const geometryMissing = geoQ.error instanceof ApiError && geoQ.error.isPhaseMissing
  const features = useMemo(
    () => (geoQ.data?.data.features ?? []).filter((f) => !hidden.has(f.properties.agreement_status)),
    [geoQ.data, hidden],
  )
  const rows: ParcelRow[] = rowsQ.data?.data ?? []

  const crops = useMemo(() => {
    const s = new Set<string>()
    for (const f of geoQ.data?.data.features ?? []) s.add(f.properties.y_pred)
    for (const r of rows) s.add(r.y_pred)
    return [...s].sort()
  }, [geoQ.data, rows])

  const counts = useMemo(() => {
    const out: Partial<Record<AgreementStatus, number>> = {}
    for (const r of (summaryQ.data?.data ?? []) as StatusSummaryRow[]) out[r.agreement_status] = r.parcels
    return out
  }, [summaryQ.data])

  const fitBounds = useMemo(() => {
    if (features.length) return boundsOf(features.map((f) => (f.geometry as { coordinates: number[][][] }).coordinates))
    if (rows.length) return boundsOf([rows.map((r) => [r.lon, r.lat])] as unknown as number[][][])
    return null
  }, [features.length, rows.length, village])

  const toggle = (s: AgreementStatus) =>
    setHidden((h) => {
      const next = new Set(h)
      if (next.has(s)) next.delete(s)
      else next.add(s)
      return next
    })

  const villageNames = useMemo(() => {
    const s = new Set<string>()
    for (const r of villageListQ.data?.data ?? []) if (r.village_name) s.add(r.village_name)
    return [...s].sort()
  }, [villageListQ.data])

  /** Status → Leaflet path options. The only place a parcel gets its look. */
  const styleFor = (p: GeoParcelProps): PathOptions => {
    if (colourBy === 'crop') {
      const c = seriesVar(crops.indexOf(p.y_pred))
      return { color: c, weight: 0.5, fillColor: c, fillOpacity: 0.75 }
    }
    const st = STATUS_STYLE[p.agreement_status]
    return {
      color: `var(${st.varName})`,
      weight: st.weight,
      fillColor: `var(${st.varName})`,
      fillOpacity: st.outlineOnly ? 0 : st.fillOpacity,
      className: st.hatched ? 'kaval-unverifiable' : undefined,
      dashArray: st.outlineOnly ? '3 3' : undefined,
    }
  }

  const onEachParcel = (f: Feature<Geometry, GeoParcelProps>, layer: Layer) => {
    const p = f.properties
    layer.on('click', () => setSelected(p.parcel_id))
    layer.bindTooltip(
      `<strong>${p.agreement_status}</strong><br/>${p.parcel_id}<br/>` +
        `declared ${p.y_true ?? '—'} · satellite ${p.y_pred}<br/>` +
        `confidence ${pct(p.confidence_calibrated)} · trust ${fixed(p.trust_score, 2)} · ${ha(p.area_m2 / 1e4, 2)}<br/>` +
        `<em>click for the capture event, bag size and photo distance</em>`,
      { sticky: true },
    )
  }

  // GeoJSON does not react to a changed `data` prop; remount on every query.
  const geoKey = `${village}|${limit}|${colourBy}|${thKey.join(',')}|${[...hidden].sort().join(',')}`

  return (
    <div>
      <div className="row" style={{ marginBottom: 12 }}>
        <label style={{ fontSize: 12, color: 'var(--ink-2)' }}>
          Village{' '}
          <select
            value={village}
            onChange={(e) => {
              setVillage(e.target.value)
              setSelected(null)
              window.location.hash = e.target.value
                ? `map?village=${encodeURIComponent(e.target.value)}`
                : 'map'
            }}
          >
            <option value="">all villages</option>
            {villageNames.map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
        </label>
        <label style={{ fontSize: 12, color: 'var(--ink-2)' }}>
          Colour by{' '}
          <select value={colourBy} onChange={(e) => setColourBy(e.target.value as 'status' | 'crop')}>
            <option value="status">agreement status</option>
            <option value="crop">crop class (secondary)</option>
          </select>
        </label>
        <label style={{ fontSize: 12, color: 'var(--ink-2)' }}>
          Parcels fetched{' '}
          <select value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
            {[1000, 3000, 6000].map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </label>
        <label style={{ fontSize: 12, color: 'var(--ink-2)' }}>
          <input type="checkbox" checked={showForests} onChange={(e) => setShowForests(e.target.checked)} />{' '}
          Reserve forests
        </label>
        <span className="spacer" />
        <a className="btn" href={api.exportUrl({ fmt: 'geojson', village: village || undefined, ...triple(dth) })}>
          Export GeoJSON
        </a>
        <a className="btn" href={api.exportUrl({ fmt: 'csv', village: village || undefined, ...triple(dth) })}>
          Export CSV
        </a>
      </div>

      {village && villageNames.length > 0 && !villageNames.includes(village) && (
        <p className="chip warn" style={{ marginBottom: 10 }}>
          ⚠ no village named "{village}" carries records — the map is empty because the filter
          matches nothing, not because the parcels are missing
        </p>
      )}

      {colourBy === 'crop' && (
        <p className="chip warn" style={{ marginBottom: 10 }}>
          Crop class is the secondary layer. The audit reads off agreement status — switch back
          to see what needs doing.
        </p>
      )}

      {geoQ.loading && rowsQ.loading ? (
        <Loading what="parcel geometry" />
      ) : geoQ.error && !geometryMissing && rowsQ.error ? (
        <ErrorState error={geoQ.error} what="The parcel layer" />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: selected ? '1fr 340px' : '1fr', gap: 14 }}>
          <div>
            <div className="mapwrap">
              <MapContainer center={FALLBACK_CENTRE} zoom={11} scrollWheelZoom>
                <TileLayer
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />
                <HatchDefs />
                <FitTo bounds={fitBounds} />

                {villagesGeoQ.data && (
                  <GeoJSON
                    key={`villages-${showForests}`}
                    data={fc(
                      villagesGeoQ.data.data.features.filter(
                        (f) => showForests || !f.properties.is_reserve_forest,
                      ),
                    )}
                    style={(f) =>
                      (f as Feature<Geometry, VillageProps>).properties.is_reserve_forest
                        ? {
                            // Negative control: no ground truth here, and a model
                            // confidently calling protected forest a crop is
                            // miscalibrated. Drawn as a labelled exclusion, not as
                            // another status.
                            color: 'var(--ink-muted)',
                            weight: 1.2,
                            dashArray: '6 3',
                            fill: true,
                            fillColor: 'var(--ink-muted)',
                            fillOpacity: 0.1,
                          }
                        : { color: 'var(--ink-muted)', weight: 1, fill: false, dashArray: '3 3' }
                    }
                    onEachFeature={(f, layer) => {
                      const p = (f as Feature<Geometry, VillageProps>).properties
                      layer.bindTooltip(
                        p.is_reserve_forest
                          ? `<strong>${p.vill_name}</strong><br/>Reserve Forest — no ground truth.<br/><em>Negative control: confident crop calls here indicate miscalibration.</em>`
                          : `<strong>${p.vill_name}</strong><br/>${p.taluk_name} taluk, ${p.dist_name}`,
                        { sticky: true },
                      )
                    }}
                  />
                )}

                {features.length > 0 && (
                  <GeoJSON
                    key={geoKey}
                    data={fc(features)}
                    style={(f) => styleFor((f as Feature<Geometry, GeoParcelProps>).properties)}
                    onEachFeature={(f, l) => onEachParcel(f as Feature<Geometry, GeoParcelProps>, l)}
                  />
                )}

                {/* Fallback only: parcel polygons unavailable, so centroids stand in. */}
                {geometryMissing &&
                  rows
                    .filter((r) => !hidden.has(r.agreement_status))
                    .map((r) => {
                      const st = STATUS_STYLE[r.agreement_status]
                      return (
                        <CircleMarker
                          key={r.parcel_id}
                          center={[r.lat, r.lon]}
                          radius={st.radius}
                          pathOptions={{
                            color: `var(${st.varName})`,
                            weight: st.weight,
                            fillColor: `var(${st.varName})`,
                            fillOpacity: st.fillOpacity,
                            className: st.hatched ? 'kaval-unverifiable' : undefined,
                          }}
                          eventHandlers={{ click: () => setSelected(r.parcel_id) }}
                        >
                          <Tooltip>
                            <strong>{r.agreement_status}</strong>
                            <br />
                            {r.parcel_id} · declared {r.y_true ?? '—'} · satellite {r.y_pred}
                            <br />
                            {n(r.bag_size)} parcels shared this photograph · taken{' '}
                            {metres(r.photo_distance_m)} away
                          </Tooltip>
                        </CircleMarker>
                      )
                    })}
              </MapContainer>
            </div>

            {geometryMissing && (
              <p className="chip warn" style={{ marginTop: 8 }}>
                ⚠ parcel polygons unavailable ({geoQ.error?.message}) — showing survey centroids
                instead. These are points, not land.
              </p>
            )}
            <Provenance
              meta={geoQ.data?.meta ?? rowsQ.data?.meta}
              extra={
                geoQ.data
                  ? `${features.length.toLocaleString()} polygons drawn of ${(rowsQ.data?.meta.n ?? 0).toLocaleString()} matching parcels · simplified 2 m`
                  : undefined
              }
            />
            {villagesGeoQ.error && (
              <div className="prov">village boundaries unavailable: {villagesGeoQ.error.message}</div>
            )}
          </div>

          {selected && (
            <div className="card" style={{ maxHeight: 'calc(100vh - 210px)', overflow: 'auto' }}>
              <ParcelPanel parcelId={selected} onClose={() => setSelected(null)} />
            </div>
          )}
        </div>
      )}

      <div className="card" style={{ marginTop: 14 }}>
        <h2>Agreement status across the taluk</h2>
        <p className="sub">
          Counts re-derived by the API at the thresholds currently set on the right — the same
          call path the map, the worklist and the saving use.
        </p>
        {summaryQ.error ? (
          <ErrorState error={summaryQ.error} what="The status summary" />
        ) : summaryQ.data ? (
          <>
            <StackedBar
              total={(summaryQ.data.data as StatusSummaryRow[]).reduce((s, r) => s + r.parcels, 0)}
              segments={STATUSES.filter((s) => counts[s]).map((s) => ({
                key: s,
                label: s,
                value: counts[s] ?? 0,
                color: `var(${STATUS_STYLE[s].varName})`,
                hatch: STATUS_STYLE[s].hatched,
              }))}
            />
            <table className="data" style={{ marginTop: 10 }}>
              <thead>
                <tr>
                  <th>Status</th>
                  <th className="num">Parcels</th>
                  <th className="num">Area</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {STATUSES.map((s) => {
                  const row = (summaryQ.data!.data as StatusSummaryRow[]).find((r) => r.agreement_status === s)
                  return (
                    <tr key={s}>
                      <td>
                        <span className="row" style={{ gap: 6 }}>
                          <span
                            className={`swatch${STATUS_STYLE[s].hatched ? ' hatch' : ''}${STATUS_STYLE[s].outlineOnly ? ' outline' : ''}`}
                            style={{ background: `var(${STATUS_STYLE[s].varName})`, borderColor: `var(${STATUS_STYLE[s].varName})` }}
                            aria-hidden
                          />
                          {s}
                        </span>
                      </td>
                      <td className="num">{n(row?.parcels ?? 0)}</td>
                      <td className="num">{ha(row?.area_ha ?? 0)}</td>
                      <td style={{ color: 'var(--ink-2)', fontSize: 12 }}>
                        {({
                          DISPUTED: 'Top of the field worklist',
                          UNCERTAIN: 'Route by remaining budget',
                          UNVERIFIABLE: 'Re-survey the record, not the parcel',
                          CONFIRMED: 'Auto-clear next season',
                          UNSEEN: 'Satellite-only, no audit claim',
                        } as Record<AgreementStatus, string>)[s]}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            <Provenance meta={summaryQ.data.meta} />
          </>
        ) : (
          <Loading what="the status summary" />
        )}
      </div>

      <div className="card">
        <h2>Legend</h2>
        <p className="sub">Click a status to hide it on the map.</p>
        <StatusLegend counts={counts} hidden={hidden} onToggle={toggle} />
        <div className="legend" style={{ marginTop: 12, paddingTop: 10, borderTop: '1px solid var(--grid)' }}>
          <div className="item" style={{ cursor: 'default' }}>
            <span
              className="swatch"
              style={{ background: 'var(--ink-muted)', opacity: 0.35, borderStyle: 'dashed' }}
              aria-hidden
            />
            <span className="name">Reserve Forest</span>
            <span className="count" />
            <span className="meaning">
              Negative control — no ground truth. A confident crop call inside these four polygons
              is evidence of miscalibration, not of farmland.
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
