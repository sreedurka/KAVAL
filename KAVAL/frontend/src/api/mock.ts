/**
 * MOCK MODE — enabled only with VITE_USE_MOCK=1.
 *
 * Phases 5–7 were still executing while this UI was built, so
 * `data/derived/audit.parquet` may not exist. This module stands in for the
 * FastAPI process so rendering can be verified, and it implements the same
 * contract: the same envelope, the same threshold parameters, the same
 * re-derivation of agreement status when a threshold moves.
 *
 * Two safeguards so a mock number can never be mistaken for a measurement:
 *   1. every envelope's `meta.sources` begins with "MOCK", and the shell renders
 *      a persistent banner whenever USE_MOCK is set;
 *   2. the parcel rows are synthesised from a seeded PRNG, not sampled from any
 *      real file, so they cannot coincidentally reproduce a real figure.
 *
 * The validation payloads (ladder, per-class, forensics) are the *measured*
 * Phase 0/4 values copied from docs/evidence/*.json so the honesty credential
 * renders with its real shape. They are still served behind the MOCK banner.
 */

import type { AgreementStatus, Economics, Envelope, ParcelRow, Thresholds } from './types'

/**
 * The agreement-status rule, implemented HERE because this module is standing in
 * for the server. In live mode the browser derives nothing: `/parcels`,
 * `/geo/parcels`, `/audit/*` all take the threshold triple and re-derive
 * server-side, and `kaval/audit.py::agreement_status` is the single authority.
 * This copy exists only so mock mode responds to the sliders the same way.
 *
 * Ordering matters and mirrors the server: a record we cannot verify is
 * UNVERIFIABLE regardless of what the model thinks of it.
 */
function deriveStatus(r: ParcelRow, t: Thresholds): AgreementStatus {
  if (r.y_true === null || r.y_true === undefined || r.y_true === '') return 'UNSEEN'
  if (r.trust_score < t.trust_floor) return 'UNVERIFIABLE'
  const agrees = r.y_pred === r.y_true
  if (!agrees && r.confidence_calibrated >= t.confidence_high) return 'DISPUTED'
  if (agrees && r.confidence_calibrated >= t.confidence_high && r.trust_score >= t.trust_high)
    return 'CONFIRMED'
  return 'UNCERTAIN'
}

const MOCK_THRESHOLDS: Thresholds = {
  confidence_high: 0.8,
  confidence_low: 0.5,
  trust_floor: 0.35,
  trust_high: 0.65,
}

const CROPS = ['Rice (Paddy)', 'Coconut', 'Maize', 'Banana', 'Sugarcane', 'Other']
const VILLAGES = [
  'Sivagiri', 'Vadakarai', 'Viswanathaperi Part-1', 'Viswanathaperi Part-2',
  'Kuruvikulam', 'Melapavoor', 'Sundarapandiapuram', 'Vadakku Ilanji',
  'Pudur', 'Thalaivankottai', 'Kadayanallur North', 'Alangulam',
]

/** The four `village_co='YYY'` polygons: no ground truth, negative control. */
const RESERVE_FORESTS = [
  'Vasudevanallur R.F', 'Naranapuram R.F', 'CHINTAMANI R.F', 'Sivagiri Reserve Forest',
]

// Sivagiri taluk, Tenkasi district, Tamil Nadu.
const CENTRE = { lat: 9.345, lon: 77.45 }

function box(lat: number, lon: number, dLat: number, dLon: number, properties: object) {
  return {
    type: 'Feature' as const,
    properties,
    geometry: {
      type: 'Polygon' as const,
      coordinates: [[
        [lon, lat], [lon + dLon, lat], [lon + dLon, lat + dLat], [lon, lat + dLat], [lon, lat],
      ]],
    },
  }
}

function mulberry32(seed: number) {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function buildParcels(n = 1400): ParcelRow[] {
  const rnd = mulberry32(20260930)
  const rows: ParcelRow[] = []
  let bag = 0
  while (rows.length < n) {
    // Capture-event bags: one photograph, many parcels, one copied label.
    const bagSize = Math.max(1, Math.round(1 + Math.pow(rnd(), 2.2) * 24))
    const village = VILLAGES[Math.floor(rnd() * VILLAGES.length)]
    const declared = CROPS[Math.floor(rnd() * rnd() * CROPS.length)]
    const photoDistance = Math.round(Math.pow(rnd(), 0.55) * 6200)
    const bagId = `IMG_${String(bag).padStart(5, '0')}.jpg`
    const bLat = CENTRE.lat + (rnd() - 0.5) * 0.22
    const bLon = CENTRE.lon + (rnd() - 0.5) * 0.3
    for (let i = 0; i < bagSize && rows.length < n; i++) {
      const agrees = rnd() > 0.19
      const predicted = agrees
        ? declared
        : CROPS[Math.floor(rnd() * CROPS.length)]
      const conf = Math.min(0.999, 0.42 + Math.pow(rnd(), 0.7) * 0.58)
      const trust =
        0.92 -
        0.42 * Math.min(1, (bagSize - 1) / 20) -
        0.3 * Math.min(1, photoDistance / 3000) +
        rnd() * 0.18
      const pWrong = agrees ? rnd() * 0.18 : 0.25 + rnd() * 0.7
      const unseen = rnd() < 0.05
      rows.push({
        parcel_id: `${village.replace(/\s+/g, '')}_${100 + rows.length}_${1 + (rows.length % 3)}`,
        village_name: village,
        survey_no: 100 + rows.length,
        subdivision: 1 + (rows.length % 3),
        y_true: unseen ? null : declared,
        y_pred: predicted,
        confidence_calibrated: round(conf, 4),
        trust_score: round(Math.max(0.02, Math.min(1, trust)), 4),
        agreement_status: 'UNCERTAIN', // replaced below at the served thresholds
        p_label_wrong: round(pWrong, 4),
        suggested_crop: agrees ? null : predicted,
        bag_size: bagSize,
        photo_distance_m: photoDistance,
        area_m2: round(400 + Math.pow(rnd(), 2) * 22000, 1),
        lat: round(bLat + (rnd() - 0.5) * 0.004, 6),
        lon: round(bLon + (rnd() - 0.5) * 0.004, 6),
        // carried for the detail view
        ...({ __bag: bagId } as object),
      })
    }
    bag++
  }
  return rows
}

function round(x: number, d: number) {
  const f = Math.pow(10, d)
  return Math.round(x * f) / f
}

const PARCELS = buildParcels()

function applyStatus(rows: ParcelRow[], t: Thresholds): ParcelRow[] {
  return rows.map((r) => ({ ...r, agreement_status: deriveStatus(r, t) }))
}

function env<T>(data: T, extra: Partial<Envelope<T>['meta']> = {}): Envelope<T> {
  return {
    data,
    meta: {
      n: Array.isArray(data) ? data.length : 1,
      generated_at: new Date().toISOString(),
      sources: ['MOCK — synthesised in src/api/mock.ts, not measured'],
      split_regime: null,
      model_version: null,
      thresholds: null,
      ...extra,
    },
  }
}

function thresholdsFrom(params: Record<string, unknown> | undefined): Thresholds {
  return {
    confidence_high: num(params?.confidence_high, MOCK_THRESHOLDS.confidence_high),
    confidence_low: MOCK_THRESHOLDS.confidence_low,
    trust_floor: num(params?.trust_floor, MOCK_THRESHOLDS.trust_floor),
    trust_high: num(params?.trust_high, MOCK_THRESHOLDS.trust_high),
  }
}

function num(v: unknown, d: number): number {
  const x = Number(v)
  return Number.isFinite(x) ? x : d
}

// Measured values, copied from KAVAL/docs/evidence/. Served behind the MOCK banner.
const LADDER = {
  ladder: [
    { regime: '1-random', accuracy: 0.8972, accuracy_std: 0.0044, macro_f1: 0.7722, macro_f1_std: 0.0177, log_loss: 0.3432, folds: 5 },
    { regime: '2-parcel', accuracy: 0.8953, accuracy_std: 0.0051, macro_f1: 0.7694, macro_f1_std: 0.0163, log_loss: 0.3487, folds: 5 },
    { regime: '3-event', accuracy: 0.8202, accuracy_std: 0.0057, macro_f1: 0.5586, macro_f1_std: 0.0245, log_loss: 0.7656, folds: 5 },
    { regime: '4-village', accuracy: 0.6906, accuracy_std: 0.0412, macro_f1: 0.3271, macro_f1_std: 0.0338, log_loss: 1.1354, folds: 5 },
  ],
  headline: { regime: '3-event', head: 'MLP', accuracy: 0.8208, macro_f1: 0.5975 },
  heads: [
    { regime: '3-event', head: 'MLP', accuracy: 0.8208, accuracy_std: 0.0061, macro_f1: 0.5975, macro_f1_std: 0.0245, log_loss: 0.7132 },
    { regime: '3-event', head: 'LightGBM', accuracy: 0.8202, accuracy_std: 0.0057, macro_f1: 0.5586, macro_f1_std: 0.0245, log_loss: 0.7656 },
    { regime: '3-event', head: 'RandomForest', accuracy: 0.8134, accuracy_std: 0.0049, macro_f1: 0.5127, macro_f1_std: 0.0201, log_loss: 0.8021 },
    { regime: '3-event', head: 'Logistic', accuracy: 0.8016, accuracy_std: 0.0072, macro_f1: 0.5342, macro_f1_std: 0.0219, log_loss: 0.7894 },
  ],
  sources: [
    { regime: '3-event', source: 'GSE only', accuracy: 0.83, accuracy_std: 0.0123, macro_f1: 0.6069, macro_f1_std: 0.0128, log_loss: 0.9378 },
    { regime: '3-event', source: 'GSE + seasonal', accuracy: 0.8208, accuracy_std: 0.0061, macro_f1: 0.5975, macro_f1_std: 0.0245, log_loss: 0.7132 },
    { regime: '3-event', source: 'seasonal only', accuracy: 0.7421, accuracy_std: 0.0094, macro_f1: 0.4188, macro_f1_std: 0.0176, log_loss: 1.0214 },
  ],
}

const PER_CLASS = [
  { crop: 'Rice (Paddy)', records: 8970, capture_events: 2322, precision: 0.8814, recall: 0.9071, f1: 0.894, support: 8970 },
  { crop: 'Coconut', records: 2566, capture_events: 517, precision: 0.7405, recall: 0.763, f1: 0.7516, support: 2566 },
  { crop: 'Maize', records: 1560, capture_events: 162, precision: 0.5612, recall: 0.4744, f1: 0.5142, support: 1560 },
  { crop: 'Banana', records: 653, capture_events: 64, precision: 0.3915, recall: 0.2404, f1: 0.2979, support: 653 },
  { crop: 'Sugarcane', records: 429, capture_events: 120, precision: 0.5231, recall: 0.4056, f1: 0.457, support: 429 },
  { crop: 'Other', records: 132, capture_events: 17, precision: 0.2143, recall: 0.0682, f1: 0.1034, support: 132 },
]

const CM_LABELS = ['Banana', 'Coconut', 'Maize', 'Other', 'Rice (Paddy)', 'Sugarcane']
const CM_COUNTS = [
  [157, 150, 62, 3, 272, 9],
  [77, 1958, 54, 14, 429, 34],
  [23, 61, 740, 6, 707, 23],
  [3, 18, 11, 9, 88, 3],
  [124, 380, 425, 8, 7975, 58],
  [17, 78, 27, 2, 131, 174],
]

const FORENSICS = {
  n_records: 14643,
  n_villages: 21,
  n_capture_events: 3204,
  label_inflation_factor: 4.57,
  max_parcels_per_capture_event: 43,
  pct_records_in_multi_parcel_events: 93.8,
  capture_events_with_mixed_crop_label: 0,
  records_with_multivalued_image_coord: 645,
  records_with_out_of_area_image_coord: 13,
  photo_to_parcel_distance_m: { median: 1436, p75: 2436, p90: 3808, p99: 6582, max: 8559, pct_over_1km: 62.3, pct_over_3km: 16.2 },
  per_crop_effective_n: {
    'Rice (Paddy)': { records: 9221, capture_events: 2322, inflation: 4.0 },
    Coconut: { records: 2633, capture_events: 517, inflation: 5.1 },
    Maize: { records: 1568, capture_events: 162, inflation: 9.7 },
    Banana: { records: 655, capture_events: 66, inflation: 9.9 },
    Sugarcane: { records: 433, capture_events: 120, inflation: 3.6 },
    Marigold: { records: 36, capture_events: 3, inflation: 12.0 },
    Sorghum: { records: 30, capture_events: 4, inflation: 7.5 },
    Cassava: { records: 24, capture_events: 3, inflation: 8.0 },
    'Diploid Cotton (Paruththi)': { records: 19, capture_events: 2, inflation: 9.5 },
    Groundnut: { records: 16, capture_events: 2, inflation: 8.0 },
    Mango: { records: 6, capture_events: 1, inflation: 6.0 },
    'Fodder Sorghum': { records: 2, capture_events: 2, inflation: 1.0 },
  },
}

const VISIT_COST = {
  parcels_per_surveyor_day: 25,
  note:
    'Assumption. Derived from 3,204 capture events over a ~7-day survey window across ' +
    '21 villages in the supplied sample; revise with FarmwiseAI actuals.',
}

const MEASURED = ['MOCK envelope · payload copied from KAVAL/docs/evidence/']

export async function mockFetch<T>(
  path: string,
  params?: Record<string, unknown>,
  init?: RequestInit,
): Promise<T> {
  await new Promise((r) => setTimeout(r, 90))
  const t = thresholdsFrom(params)
  const withStatus = () => applyStatus(PARCELS, t)

  if (path === '/health')
    return { status: 'ok (mock)', phases_available: { audit: true, p4: true, p5: true, p6: true } } as T

  if (path === '/parcels') {
    let rows = withStatus()
    if (params?.village) rows = rows.filter((r) => r.village_name.toLowerCase() === String(params.village).toLowerCase())
    if (params?.crop) rows = rows.filter((r) => r.y_pred === params.crop)
    if (params?.status) rows = rows.filter((r) => r.agreement_status === String(params.status).toUpperCase())
    const minC = num(params?.min_confidence, 0), maxC = num(params?.max_confidence, 1), minT = num(params?.min_trust, 0)
    rows = rows.filter((r) => r.confidence_calibrated >= minC && r.confidence_calibrated <= maxC && r.trust_score >= minT)
    const total = rows.length
    const offset = num(params?.offset, 0), limit = num(params?.limit, 200)
    return { ...env(rows.slice(offset, offset + limit)), meta: { ...env(rows).meta, n: total, thresholds: MOCK_THRESHOLDS } } as T
  }

  if (path.startsWith('/parcels/')) {
    const id = decodeURIComponent(path.slice('/parcels/'.length))
    const r = withStatus().find((x) => x.parcel_id === id)
    if (!r) throw Object.assign(new Error(`no parcel ${id}`), { status: 404 })
    const bag = (r as unknown as { __bag?: string }).__bag ?? 'IMG_UNKNOWN.jpg'
    return env({
      parcel_id: r.parcel_id, village: r.village_name, survey_no: r.survey_no,
      subdivision: r.subdivision, declared_crop: r.y_true, predicted_crop: r.y_pred,
      confidence_calibrated: r.confidence_calibrated,
      confidence_raw: round(Math.min(0.999, r.confidence_calibrated * 1.08), 4),
      agreement_status: r.agreement_status, trust_score: r.trust_score,
      p_label_wrong: r.p_label_wrong, suggested_crop: r.suggested_crop,
      evidence: {
        capture_event: bag,
        parcels_sharing_this_photograph: r.bag_size,
        photo_distance_m: r.photo_distance_m,
        geometry_source: r.bag_size > 12 ? 'voronoi' : r.bag_size > 6 ? 'ftw_shared' : 'ftw',
        village_code_mismatch: r.village_name.startsWith('Viswanathaperi'),
        declared_stage: 'Vegetative',
      },
      area_m2: r.area_m2,
    }) as T
  }

  if (path === '/summary/crop-area') {
    const src = params?.source === 'declared' ? 'y_true' : 'y_pred'
    const byVillage = params?.group_by !== 'taluk'
    const m = new Map<string, { village_name?: string; crop: string; parcels: number; area_ha: number; c: number }>()
    for (const r of withStatus()) {
      const crop = (src === 'y_true' ? r.y_true : r.y_pred) ?? 'UNSEEN'
      const key = byVillage ? `${r.village_name}|${crop}` : crop
      const e = m.get(key) ?? { ...(byVillage ? { village_name: r.village_name } : {}), crop, parcels: 0, area_ha: 0, c: 0 }
      e.parcels++; e.area_ha += r.area_m2 / 1e4; e.c += r.confidence_calibrated
      m.set(key, e)
    }
    return env([...m.values()].map((e) => ({
      ...(e.village_name ? { village_name: e.village_name } : {}),
      crop: e.crop, parcels: e.parcels, area_ha: round(e.area_ha, 3),
      mean_confidence: round(e.c / e.parcels, 3),
    }))) as T
  }

  if (path === '/summary/registry-delta') {
    // MOCK: the "registry" here is the mock's own declared crop, so the two
    // caveats below are true of it in the strongest possible sense.
    const dec = new Map<string, number>(), pred = new Map<string, number>()
    const vtot = new Map<string, { d: number; s: number }>()
    for (const r of withStatus()) {
      const ha = r.area_m2 / 1e4
      const t = vtot.get(r.village_name) ?? { d: 0, s: 0 }
      if (r.y_true) { dec.set(`${r.village_name}|${r.y_true}`, (dec.get(`${r.village_name}|${r.y_true}`) ?? 0) + ha); t.d += ha }
      pred.set(`${r.village_name}|${r.y_pred}`, (pred.get(`${r.village_name}|${r.y_pred}`) ?? 0) + ha); t.s += ha
      vtot.set(r.village_name, t)
    }
    const keys = new Set([...dec.keys(), ...pred.keys()])
    const minHa = num(params?.min_registry_ha, 0)
    const rows = [...keys].map((k) => {
      const [village, crop] = k.split('|')
      const t = vtot.get(village) ?? { d: 1, s: 1 }
      const d = dec.get(k) ?? 0, s = pred.get(k) ?? 0
      const rs = d / Math.max(t.d, 1e-9), ss = s / Math.max(t.s, 1e-9)
      return {
        village, crop, registry_ha: round(d, 2), registry_share: round(rs, 4),
        sat_ha: round(s, 2), satellite_share: round(ss, 4), delta_share: round(ss - rs, 4),
        abs_delta_share: Math.abs(round(ss - rs, 4)), implied_ha_delta: round((ss - rs) * t.d, 1),
        mean_confidence: 0.8,
      }
    }).filter((r) => r.registry_ha >= minHa).sort((a, b) => b.abs_delta_share - a.abs_delta_share)
    return env({
      rows,
      independence_caveat: 'MOCK. The registry is the published aggregate of the SAME survey whose parcel sample is the ground truth. Not independent validation.',
      scale_caveat: 'MOCK. Compared as crop SHARE, not hectares: parcel coverage of each village is partial.',
      systematic_bias_by_crop: [],
      registry_out_of_scope_pct: 0,
      season: 'MOCK',
    }) as T
  }

  if (path === '/audit/worklist') {
    let rows = withStatus()
    if (params?.village) rows = rows.filter((r) => r.village_name.toLowerCase() === String(params.village).toLowerCase())
    const budget = Math.min(num(params?.budget, 500), rows.length)
    const areas = rows.map((r) => r.area_m2).sort((a, b) => a - b)
    const median = areas[Math.floor(areas.length / 2)] || 1
    const scored = rows.map((r) => ({ ...r, priority: round(r.p_label_wrong * Math.min(4, Math.max(0.25, r.area_m2 / median)), 4) }))
      .sort((a, b) => b.priority - a.priority)
    const top = scored.slice(0, budget)
    const routed = top.reduce((s, r) => s + r.p_label_wrong, 0)
    const mean = rows.reduce((s, r) => s + r.p_label_wrong, 0) / rows.length
    const random = mean * budget
    const sd = Math.sqrt(rows.reduce((s, r) => s + Math.pow(r.p_label_wrong - mean, 2), 0) / rows.length) * Math.sqrt(budget)
    return { ...env({
      // Typed, so a renamed API field breaks the build instead of rendering dashes.
      economics: {
        budget,
        estimated_corrections_routed: round(routed, 2),
        estimated_corrections_random: round(random, 2),
        estimated_corrections_random_std: round(sd, 2),
        routed_area_ha: round(top.reduce((s, r) => s + r.area_m2, 0) / 1e4, 2),
        pct_of_parcels_visited: round((100 * budget) / rows.length, 2),
      } satisfies Economics,
      worklist: top,
    }), meta: { ...env(null).meta, n: top.length, thresholds: t } } as T
  }

  if (path === '/audit/auto-clear') {
    const rows = withStatus()
    const cleared = rows.filter((r) => r.agreement_status === 'CONFIRMED')
    const perDay = VISIT_COST.parcels_per_surveyor_day
    return { ...env({
      parcels: cleared.length,
      pct_of_parcels: round((100 * cleared.length) / Math.max(rows.length, 1), 1),
      area_ha: round(cleared.reduce((s, r) => s + r.area_m2, 0) / 1e4, 1),
      surveyor_days_saved: round(cleared.length / perDay, 1),
      baseline_surveyor_days: round(rows.length / perDay, 1),
      expected_residual_error_rate: cleared.length
        ? round(1 - cleared.reduce((s, r) => s + r.confidence_calibrated, 0) / cleared.length, 4)
        : null,
      expected_parcels_wrongly_cleared: cleared.length
        ? round(cleared.reduce((s, r) => s + (1 - r.confidence_calibrated), 0), 2)
        : null,
      residual_note:
        'Auto-clearing fails only where satellite and surveyor err in the same way, ' +
        'which cannot be measured against a label the surveyor supplied. Settle it with an ' +
        'independent field audit of a CONFIRMED sample.',
      cost_assumption: VISIT_COST,
    }), meta: { ...env(null).meta, n: cleared.length, thresholds: t, split_regime: '3-event' } } as T
  }

  if (path === '/geo/villages') {
    // Coarse rectangles; enough to prove the layer, never mistaken for real
    // boundaries — the banner and meta.sources both say MOCK.
    const feats = VILLAGES.map((name, i) => {
      const lat = CENTRE.lat - 0.09 + Math.floor(i / 4) * 0.06
      const lon = CENTRE.lon - 0.13 + (i % 4) * 0.07
      return box(lat, lon, 0.055, 0.065, {
        vill_name: name, dist_name: 'Tenkasi', taluk_name: 'Sivagiri',
        village_co: String(i + 1), is_reserve_forest: false,
      })
    })
    RESERVE_FORESTS.forEach((name, i) => {
      const lat = CENTRE.lat + 0.02 + i * 0.04
      feats.push(box(lat, CENTRE.lon - 0.2, 0.05, 0.05, {
        vill_name: name, dist_name: 'Tenkasi', taluk_name: 'Sivagiri',
        village_co: 'YYY', is_reserve_forest: true,
      }))
    })
    return { ...env({ type: 'FeatureCollection', features: feats }),
      meta: { ...env(null).meta, n: feats.length } } as T
  }

  if (path === '/geo/parcels') {
    let rows = withStatus()
    if (params?.village) rows = rows.filter((r) => r.village_name.toLowerCase() === String(params.village).toLowerCase())
    rows = rows.slice(0, num(params?.limit, 6000))
    // Square of the parcel's own area, centred on its point — the mock has no
    // delineated geometry and must not pretend otherwise.
    const feats = rows.map((r) => {
      const halfDeg = Math.sqrt(r.area_m2) / 2 / 111320
      return box(r.lat - halfDeg, r.lon - halfDeg / Math.cos((r.lat * Math.PI) / 180), halfDeg * 2,
        (halfDeg * 2) / Math.cos((r.lat * Math.PI) / 180), {
          parcel_id: r.parcel_id, agreement_status: r.agreement_status, y_pred: r.y_pred,
          y_true: r.y_true, confidence_calibrated: r.confidence_calibrated,
          trust_score: r.trust_score, area_m2: r.area_m2,
        })
    })
    return { ...env({ type: 'FeatureCollection', features: feats }),
      meta: { ...env(null).meta, n: feats.length, thresholds: t } } as T
  }

  if (path === '/audit/status-summary') {
    const rows = withStatus()
    const m = new Map<AgreementStatus, { parcels: number; area_ha: number }>()
    for (const r of rows) {
      const e = m.get(r.agreement_status) ?? { parcels: 0, area_ha: 0 }
      e.parcels++; e.area_ha += r.area_m2 / 1e4
      m.set(r.agreement_status, e)
    }
    return { ...env([...m.entries()].map(([agreement_status, v]) => ({ agreement_status, parcels: v.parcels, area_ha: round(v.area_ha, 1) }))),
      meta: { ...env(null).meta, n: m.size, thresholds: t } } as T
  }

  if (path === '/validation/ladder')
    return { ...env(LADDER), meta: { ...env(null).meta, sources: MEASURED, split_regime: 'all four regimes reported side by side' } } as T

  if (path === '/validation/confusion')
    return { ...env({ per_class: PER_CLASS, confusion_matrix: { labels: CM_LABELS, counts: CM_COUNTS },
      top_confusions: topConfusions() }), meta: { ...env(null).meta, sources: MEASURED, split_regime: '3-event', model_version: 'MLP' } } as T

  if (path === '/validation/calibration')
    return { ...env({ ece_before: 0.0812, ece_after: 0.0194, n_bins: 15, method: 'isotonic, fitted on validation folds only' }),
      meta: { ...env(null).meta, sources: MEASURED, split_regime: '3-event' } } as T

  if (path === '/evidence/forensics')
    return { ...env(FORENSICS), meta: { ...env(null).meta, n: 1, sources: MEASURED } } as T

  if (path === '/analyst/tools')
    return { model: 'mock', planner: 'offline', planner_note: MOCK_PLANNER_NOTE, tools: [
      { name: 'query_parcels', description: 'List parcels filtered by village, crop, agreement status, confidence or trust.' },
      { name: 'crop_area_summary', description: 'Crop-wise cultivated area by village or taluk, predicted or declared.' },
      { name: 'compare_to_registry', description: 'Per-village declared versus satellite-estimated area, sorted by divergence.' },
      { name: 'confusion_report', description: 'Per-class precision/recall/F1 with effective n, plus the confusion matrix.' },
      { name: 'route_verification_budget', description: 'Given N visits, the N parcels maximising expected corrections.' },
      { name: 'leakage_ladder', description: 'Accuracy and macro F1 for the same model under four validation splits.' },
    ] } as T

  if (path === '/analyst/query') {
    const q = JSON.parse(String(init?.body ?? '{}')).question ?? ''
    return {
      answer:
        'MOCK ANALYST — the real endpoint is POST /analyst/query (AI-5, Phase 7b). ' +
        `You asked: "${q}". A live answer would be composed only from tool results, ` +
        'would name its split regime for any metric, and would never describe a parcel as "wrong" — ' +
        'the survey record and the satellite disagree; a field visit decides which is right.',
      citations: [
        { source: 'MOCK — src/api/mock.ts', n: 1400 },
        { source: 'MOCK — leakage ladder', split_regime: '3-event' },
      ],
      tool_calls: [{ tool: 'query_parcels', args: { status: 'DISPUTED', limit: 20 } }],
      planner: 'offline',
      planner_note: MOCK_PLANNER_NOTE,
    } as T
  }

  throw Object.assign(new Error(`mock: no handler for ${path}`), { status: 404 })
}

const MOCK_PLANNER_NOTE =
  'MOCK — in the real API this note comes from GET /analyst/tools. Offline answers are ' +
  "produced by KAVAL's rule-based planner, not an LLM."

function topConfusions() {
  const out: { true: string; predicted: string; n: number }[] = []
  for (let i = 0; i < CM_LABELS.length; i++)
    for (let j = 0; j < CM_LABELS.length; j++)
      if (i !== j) out.push({ true: CM_LABELS[i], predicted: CM_LABELS[j], n: CM_COUNTS[i][j] })
  return out.sort((a, b) => b.n - a.n).slice(0, 10)
}
