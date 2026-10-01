import { api } from '../api/client'
import type { AgreementStatus } from '../api/types'
import { useQuery } from '../lib/useQuery'
import { ErrorState, Loading, Provenance } from './common'

import { STATUS_MEANING, STATUS_STYLE } from '../lib/palette'
import { EM_DASH, fixed, ha, metres, n, pct } from '../lib/format'

function StatusBadge({ s }: { s: AgreementStatus }) {
  const st = STATUS_STYLE[s]
  return (
    <span className="chip" style={{ borderColor: `var(${st.varName})`, color: 'var(--ink-1)' }}>
      <span
        className={`swatch${st.hatched ? ' hatch' : ''}${st.outlineOnly ? ' outline' : ''}`}
        style={{ background: st.outlineOnly ? 'transparent' : `var(${st.varName})`, borderColor: `var(${st.varName})` }}
        aria-hidden
      />
      {s}
    </span>
  )
}

function Row({ k, v, hint }: { k: string; v: React.ReactNode; hint?: string }) {
  return (
    <tr>
      <th style={{ width: '48%', fontWeight: 500, color: 'var(--ink-2)', textTransform: 'none', letterSpacing: 0, fontSize: 12 }} title={hint}>
        {k}
      </th>
      <td className="num" style={{ fontWeight: 600 }}>{v}</td>
    </tr>
  )
}

/**
 * The full audit trail for one parcel.
 *
 * react-map-ui rule 4: the popup cites provenance. Which capture event supplied
 * the label, how many parcels shared that one photograph, and how far away the
 * photograph was taken are not footnotes — they are the reason a status is what
 * it is, and for UNVERIFIABLE they are the entire finding.
 */
export function ParcelPanel({ parcelId, onClose }: { parcelId: string; onClose: () => void }) {
  const q = useQuery(() => api.parcel(parcelId), [parcelId])

  if (q.loading) return <Loading what={`parcel ${parcelId}`} />
  if (q.error) return <ErrorState error={q.error} what={`Parcel ${parcelId}`} />
  if (!q.data) return null

  const d = q.data.data
  const e = d.evidence
  const meaning = STATUS_MEANING[d.agreement_status]

  return (
    <div>
      <div className="row">
        <StatusBadge s={d.agreement_status} />
        <span className="spacer" />
        <button className="btn" onClick={onClose}>Close</button>
      </div>

      <h2 style={{ margin: '10px 0 2px', fontSize: 15 }}>{d.parcel_id}</h2>
      <div style={{ fontSize: 12, color: 'var(--ink-2)' }}>
        {d.village} · survey no {d.survey_no}/{d.subdivision}
      </div>
      <p style={{ fontSize: 12, color: 'var(--ink-2)', marginTop: 8 }}>{meaning.blurb}</p>
      <p style={{ fontSize: 12, fontWeight: 600, margin: '0 0 12px' }}>→ {meaning.action}</p>

      <h3 style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--ink-muted)' }}>
        The disagreement
      </h3>
      <table className="data">
        <tbody>
          <Row k="Declared by surveyor" v={d.declared_crop ?? `${EM_DASH} no record`} />
          <Row k="Predicted from satellite" v={d.predicted_crop} />
          <Row k="Suggested correction" v={d.suggested_crop ?? EM_DASH} hint="From confident learning (AI-4). Empty where the model prefers no alternative." />
          <Row k="Calibrated confidence" v={pct(d.confidence_calibrated)} hint="Isotonic-calibrated. This is the number that routes the budget." />
          <Row k="Raw confidence" v={pct(d.confidence_raw)} hint="Uncalibrated model output. Shown only so the calibration gap is visible; never used for routing." />
          <Row k="P(declared label needs correction)" v={pct(d.p_label_wrong)} hint="Confident learning estimate. Drives the worklist ranking." />
        </tbody>
      </table>

      <h3 style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--ink-muted)', marginTop: 16 }}>
        Provenance of the record
      </h3>
      <table className="data">
        <tbody>
          <Row k="Record Trust Score" v={fixed(d.trust_score, 3)} hint="Weighted from bag size, photo distance, bag support, stage plausibility, mixed-crop flag, geometry source and within-parcel heterogeneity. Weights published in kaval/config.py." />
          <Row k="Capture event" v={<span style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>{e.capture_event}</span>} hint="The photograph this label came from." />
          <Row k="Parcels sharing this photograph" v={n(e.parcels_sharing_this_photograph)} hint="One photograph, one label, copied to every parcel in the bag. 43 is the maximum measured in the supplied data." />
          <Row k="Photograph taken" v={metres(e.photo_distance_m)} hint="Distance from the photograph's geotag to this parcel's centroid." />
          <Row k="Geometry source" v={e.geometry_source} hint="ftw: the parcel's own satellite-delineated field. ftw_shared: the field is shared with other legal parcels. voronoi: fallback tessellation, no delineated field found. Lower-fidelity geometry lowers trust." />
          {e.field_id != null && (
            <Row k="Physical field" v={<span style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>{e.field_id}</span>} hint="Satellite delineation recovers physical fields, not legal parcels." />
          )}
          {e.parcels_sharing_field != null && (
            <Row k="Legal parcels sharing this field" v={n(e.parcels_sharing_field)} hint="How many legal parcels sit on the one physical field this record was snapped to. Above 1, the field boundary cannot separate them." />
          )}
          {e.snap_m != null && (
            <Row k="Snapped to field by" v={metres(e.snap_m)} hint="Distance the survey point was moved to reach its satellite-delineated field." />
          )}
          {e.field_area_m2 != null && (
            <Row k="Field area" v={ha(e.field_area_m2 / 1e4, 2)} hint="Area of the whole physical field, which may exceed this parcel's area." />
          )}
          <Row k="Declared stage" v={e.declared_stage ?? EM_DASH} />
          <Row k="Village code mismatch" v={e.village_code_mismatch ? 'yes' : 'no'} hint="The record's village code disagrees with the administrative polygon the point falls in." />
          <Row k="Parcel area" v={ha(d.area_m2 / 1e4, 2)} />
        </tbody>
      </table>

      <Provenance meta={q.data.meta} />
    </div>
  )
}
