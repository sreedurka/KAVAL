/**
 * The only place this app talks to the network.
 *
 * Rule (plan.md §6 Phase 8 gate): every number on screen comes from here. There
 * is no fallback value anywhere in the UI — if a call fails, the component that
 * wanted the number renders an error, never a placeholder that looks real.
 */

import type { FeatureCollection, Geometry } from 'geojson'
import { mockFetch } from './mock'
import type {
  AnalystAnswer,
  AnalystToolsPayload,
  AutoClearPayload,
  CalibrationPayload,
  ConfusionPayload,
  CropAreaRow,
  Envelope,
  ForensicsPayload,
  GeoParcelProps,
  Health,
  LadderPayload,
  ParcelDetail,
  ParcelRow,
  RegistryDeltaPayload,
  StatusSummaryRow,
  Thresholds,
  VillageProps,
  WorklistPayload,
} from './types'

export const USE_MOCK = import.meta.env.VITE_USE_MOCK === '1'

const BASE = '/api'

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly path: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }

  /** 503 from this API means "an earlier phase has not run", not "broken". */
  get isPhaseMissing() {
    return this.status === 503
  }
}

type Params = Record<string, string | number | boolean | null | undefined>

function qs(params?: Params): string {
  if (!params) return ''
  const u = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v === null || v === undefined || v === '') continue
    u.set(k, String(v))
  }
  const s = u.toString()
  return s ? `?${s}` : ''
}

async function request<T>(path: string, params?: Params, init?: RequestInit): Promise<T> {
  const url = `${path}${qs(params)}`
  if (USE_MOCK) return mockFetch<T>(path, params, init)

  let res: Response
  try {
    res = await fetch(`${BASE}${url}`, {
      headers: { 'Content-Type': 'application/json' },
      ...init,
    })
  } catch (e) {
    throw new ApiError(
      `Cannot reach the KAVAL API at ${BASE}. Is uvicorn running on port 8077?`,
      0,
      url,
    )
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* body was not JSON; keep the status line */
    }
    throw new ApiError(detail, res.status, url)
  }
  return (await res.json()) as T
}

/** Threshold triple, sent to every route that accepts it. */
export interface ThresholdParams {
  confidence_high: number
  trust_floor: number
  trust_high: number
}

export const api = {
  health: () => request<Health>('/health'),

  /**
   * Thresholds are part of this call. The server re-derives `agreement_status`
   * at the caller's triple, so the map, the worklist and the saving always
   * describe one policy and the rule that produces a status exists in exactly
   * one place — `kaval/audit.py`.
   */
  parcels: (
    p: Partial<ThresholdParams> & {
      village?: string
      crop?: string
      status?: string
      min_confidence?: number
      max_confidence?: number
      min_trust?: number
      limit?: number
      offset?: number
    },
  ) => request<Envelope<ParcelRow[]>>('/parcels', p as Params),

  geoVillages: () =>
    request<Envelope<FeatureCollection<Geometry, VillageProps>>>('/geo/villages'),

  geoParcels: (p: ThresholdParams & { village?: string; simplify_m?: number; limit?: number }) =>
    request<Envelope<FeatureCollection<Geometry, GeoParcelProps>>>(
      '/geo/parcels',
      p as unknown as Params,
    ),

  parcel: (id: string) =>
    request<Envelope<ParcelDetail>>(`/parcels/${encodeURIComponent(id)}`),

  cropArea: (p: { group_by?: 'village' | 'taluk'; source?: 'predicted' | 'declared' }) =>
    request<Envelope<CropAreaRow[]>>('/summary/crop-area', p as Params),

  registryDelta: (p: { min_registry_ha?: number; village?: string; crop?: string; limit?: number }) =>
    request<Envelope<RegistryDeltaPayload>>('/summary/registry-delta', p as Params),

  worklist: (p: ThresholdParams & { budget: number; village?: string }) =>
    request<Envelope<WorklistPayload>>('/audit/worklist', p as unknown as Params),

  autoClear: (p: ThresholdParams) =>
    request<Envelope<AutoClearPayload>>('/audit/auto-clear', p as unknown as Params),

  statusSummary: (p: ThresholdParams) =>
    request<Envelope<StatusSummaryRow[]>>('/audit/status-summary', p as unknown as Params),

  ladder: () => request<Envelope<LadderPayload>>('/validation/ladder'),

  confusion: (p?: { regime?: string }) =>
    request<Envelope<ConfusionPayload>>('/validation/confusion', p as Params),

  calibration: () => request<Envelope<CalibrationPayload>>('/validation/calibration'),

  forensics: () => request<Envelope<ForensicsPayload>>('/evidence/forensics'),

  analystTools: () => request<AnalystToolsPayload>('/analyst/tools'),

  analystQuery: (question: string) =>
    request<AnalystAnswer>('/analyst/query', undefined, {
      method: 'POST',
      body: JSON.stringify({ question }),
    }),

  /**
   * Export is a browser download, not a fetch — the API streams it. With `budget`
   * it is the routed worklist (same rows, order, rank and priority as
   * /audit/worklist for the same thresholds); without, the whole parcel layer.
   */
  exportUrl: (p: {
    fmt: 'csv' | 'geojson'
    status?: string
    village?: string
    budget?: number
    confidence_high?: number
    trust_floor?: number
    trust_high?: number
  }) =>
    `${BASE}/export${qs(p as Params)}`,
}

/**
 * Default thresholds come from the API (`meta.thresholds` on /parcels), never
 * from a constant in this codebase. audit-signals: "never hard-code a threshold
 * in more than one place" — that place is KAVAL/kaval/config.py.
 */
export async function fetchDefaultThresholds(): Promise<Thresholds> {
  const res = await api.parcels({ limit: 1 })
  if (!res.meta.thresholds) {
    throw new ApiError(
      'The API did not return meta.thresholds. Threshold sliders cannot be initialised ' +
        'without them, and this UI will not invent defaults.',
      500,
      '/parcels',
    )
  }
  return res.meta.thresholds
}
