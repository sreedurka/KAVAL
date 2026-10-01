/**
 * Mirrors KAVAL/api/main.py and KAVAL/api/analyst.py.
 *
 * Every shape here is the API contract, not a convenience model. If a field is
 * optional in this file it is because the backend can omit it, and the UI has
 * to render that absence honestly rather than substituting a plausible value.
 */

export const STATUSES = [
  'DISPUTED',
  'UNCERTAIN',
  'UNVERIFIABLE',
  'CONFIRMED',
  'UNSEEN',
] as const

export type AgreementStatus = (typeof STATUSES)[number]

export interface Meta {
  n: number
  generated_at: string
  sources: string[]
  /** Required whenever `data` carries a metric. `null` means the API did not name one. */
  split_regime: string | null
  model_version: string | null
  thresholds: Thresholds | null
}

export interface Envelope<T> {
  data: T
  meta: Meta
}

export interface Thresholds {
  confidence_high: number
  confidence_low?: number
  trust_floor: number
  trust_high: number
}

export interface Health {
  status: string
  phases_available?: { audit: boolean; p4: boolean; p5: boolean; p6: boolean }
}

export interface ParcelRow {
  parcel_id: string
  village_name: string
  survey_no: string | number
  subdivision: string | number
  y_true: string | null
  y_pred: string
  confidence_calibrated: number
  trust_score: number
  agreement_status: AgreementStatus
  p_label_wrong: number
  suggested_crop: string | null
  bag_size: number
  photo_distance_m: number | null
  area_m2: number
  lat: number
  lon: number
}

/** ftw = own delineated field; ftw_shared = field shared with other parcels; voronoi = fallback. */
export type GeometrySource = 'ftw' | 'ftw_shared' | 'voronoi'

export interface ParcelDetail {
  parcel_id: string
  village: string
  survey_no: string | number
  subdivision: string | number
  declared_crop: string | null
  predicted_crop: string
  confidence_calibrated: number
  confidence_raw: number
  agreement_status: AgreementStatus
  trust_score: number
  p_label_wrong: number
  suggested_crop: string | null
  evidence: {
    capture_event: string
    parcels_sharing_this_photograph: number
    photo_distance_m: number | null
    geometry_source: GeometrySource
    /**
     * Satellite delineation recovers physical FIELDS, not legal PARCELS. These four
     * are absent from the API until the field join is exposed; the UI renders
     * them only when present.
     */
    field_id?: string | null
    snap_m?: number | null
    parcels_sharing_field?: number | null
    field_area_m2?: number | null
    village_code_mismatch: boolean
    declared_stage: string | null
  }
  area_m2: number
}

export interface CropAreaRow {
  village_name?: string
  crop: string
  parcels: number
  area_ha: number
  mean_confidence: number
  /** Area of shared fields whose records disagree on the crop (field-level rule). */
  conflicted_area_ha?: number
}

/**
 * One village x crop row of the comparison against the Tamil Nadu Agrisnet
 * village-wise Digital Crop Survey report. Compared as SHARE of village cropped
 * area, because our parcels cover only part of each village.
 */
export interface RegistryDeltaRow {
  village: string
  crop: string
  registry_ha: number
  registry_share: number
  sat_ha: number
  satellite_share: number
  /** satellite_share - registry_share. Positive: satellite sees more of this crop. */
  delta_share: number
  abs_delta_share?: number
  /** Extrapolation from the share gap to the registry's village area. Not a measurement. */
  implied_ha_delta: number
  mean_confidence: number
  parcels?: number
}

export interface CropBias {
  crop: string
  registry_share: number
  satellite_share: number
  bias: number
}

export interface RegistryDeltaPayload {
  rows: RegistryDeltaRow[]
  /** The registry is the published aggregate of the SAME survey we audit. */
  independence_caveat: string | null
  /** Share, not hectares: parcel coverage of each village is partial. */
  scale_caveat: string | null
  systematic_bias_by_crop: CropBias[] | null
  registry_out_of_scope_pct: number | null
  season: string | null
}

/**
 * The routing economics, named exactly as `kaval.audit.route_budget` returns them.
 * An earlier contract used `lift_multiple` and `*_expected_corrections`; the API
 * renamed them when the "lift" was found to be pinned by construction
 * (correction #2), and the old names silently rendered as dashes.
 */
export interface Economics {
  budget: number
  pct_of_parcels_visited?: number
  routed_area_ha?: number
  base_disagreement_rate?: number
  total_disagreements_available?: number
  routed_disagreements_found?: number
  random_disagreements_expected?: number
  /** Capped at 1 / base_disagreement_rate by construction — coverage, not ranking. */
  targeting_efficiency?: number
  targeting_is_pinned_by_construction?: boolean
  /** The ranking-quality signal: better-evidenced disagreements first? */
  routed_mean_confidence?: number
  all_disagreements_mean_confidence?: number
  /** Model-estimated, Σ P(declared label is wrong) — an estimate, not a count. */
  estimated_corrections_routed?: number
  estimated_corrections_random?: number
  estimated_corrections_random_std?: number
  note?: string
}

export interface WorklistRow extends ParcelRow {
  priority: number
}

export interface WorklistPayload {
  economics: Economics
  worklist: WorklistRow[]
}

export interface AutoClearPayload {
  parcels: number
  pct_of_parcels: number
  area_ha: number
  surveyor_days_saved: number
  baseline_surveyor_days: number
  /**
   * NOT an accuracy. `CONFIRMED` is *defined* as the model agreeing with the
   * survey, so "accuracy within the cleared set" was 100% by construction and
   * has been removed from the contract. This is the honest quantity: the share
   * of auto-cleared parcels where the calibrated confidence says satellite and
   * surveyor could still be wrong together.
   */
  expected_residual_error_rate: number | null
  expected_parcels_wrongly_cleared: number | null
  /** Why the residual cannot be measured against the surveyor's own label. */
  residual_note: string
  cost_assumption: { parcels_per_surveyor_day: number; note: string }
}

export interface StatusSummaryRow {
  agreement_status: AgreementStatus
  parcels: number
  area_ha: number
}

export interface LadderRung {
  regime: string
  accuracy: number
  accuracy_std: number
  macro_f1: number
  macro_f1_std: number
  log_loss?: number
  folds?: number
}

export interface HeadRow extends LadderRung {
  head?: string
  source?: string
}

export interface LadderPayload {
  ladder: LadderRung[]
  headline: { regime: string; head: string; accuracy: number; macro_f1: number }
  heads: HeadRow[]
  sources: HeadRow[]
  /** Each source against GSE only, fold by fold on identical folds (p4 §C). */
  source_comparisons?: SourceComparison[]
  sources_pending?: string[]
  presto_caveats?: Record<string, string | number | null> | null
}

export interface SourceComparison {
  source: string
  reference: string
  metric: 'macro_f1' | 'accuracy'
  mean_delta: number
  delta_sd: number
  folds_favouring_source: number
  folds: number
  reference_fold_sd: number
  /** Computed in p4: |mean Δ| below the larger of its SD and the reference fold SD. */
  underpowered: boolean
}

export interface PerClassRow {
  crop: string
  records: number
  /** Effective n. The number that matters. */
  capture_events: number
  precision: number
  recall: number
  f1: number
  support: number
}

export interface ConfusionPayload {
  per_class: PerClassRow[]
  confusion_matrix: { labels: string[]; counts: number[][] }
  top_confusions: { true: string; predicted: string; n: number }[]
}

/** Phase 6 writes this; shape is not pinned in the contract, so render generically. */
export type CalibrationPayload = Record<string, unknown>

export interface ForensicsPayload {
  n_records?: number
  n_villages?: number
  n_capture_events?: number
  label_inflation_factor?: number
  max_parcels_per_capture_event?: number
  pct_records_in_multi_parcel_events?: number
  capture_events_with_mixed_crop_label?: number
  per_crop_effective_n?: Record<
    string,
    { records: number; capture_events: number; inflation: number }
  >
  photo_to_parcel_distance_m?: Record<string, number>
  [k: string]: unknown
}

/** `GET /geo/villages` — administrative boundaries. */
export interface VillageProps {
  vill_name: string
  dist_name: string
  taluk_name: string
  village_co: string
  /**
   * True for the four `village_co='YYY'` Reserve Forest polygons. They carry no
   * ground truth and are the project's NEGATIVE CONTROL: a model confidently
   * calling protected forest a crop is miscalibrated. Drawn distinctly.
   */
  is_reserve_forest: boolean
  [k: string]: unknown
}

/** `GET /geo/parcels` — parcel polygons joined to audit status. */
export interface GeoParcelProps {
  parcel_id: string
  agreement_status: AgreementStatus
  y_pred: string
  y_true: string | null
  confidence_calibrated: number
  trust_score: number
  area_m2: number
}

export interface AnalystCitation {
  source: string
  /** parcel_id of every row the tool returned (capped at 50); empty for summaries. */
  parcel_ids?: string[]
  n?: number | null
  split_regime?: string | null
}

export interface AnalystToolCall {
  tool: string
  args: Record<string, unknown>
}

/** Which planner produced an answer: the LLM agent, or the offline keyword router. */
export type AnalystPlanner = 'llm' | 'offline'

export interface AnalystAnswer {
  answer: string
  citations: AnalystCitation[]
  tool_calls: AnalystToolCall[]
  planner: AnalystPlanner
  planner_note: string
  /** e.g. "gemini:gemini-flash-lite-latest" or "local:qwen2.5-7b-instruct-q4_k_m"; null offline. */
  provider?: string | null
}

export interface AnalystToolsPayload {
  /** The active LLM's model id; null when the offline planner is in use. */
  model: string | null
  provider?: string | null
  planner: AnalystPlanner
  planner_note: string
  offline_intents?: string[]
  tools: { name: string; description: string }[]
}
