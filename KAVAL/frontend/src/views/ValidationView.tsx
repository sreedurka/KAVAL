import { api } from '../api/client'
import type { ForensicsPayload, LadderRung, PerClassRow, SourceComparison } from '../api/types'
import { useQuery } from '../lib/useQuery'
import { ErrorState, Loading, Provenance, RegimeChip, Tile } from '../components/common'
import { ChartFrame, HBars, Heatmap } from '../charts/primitives'
import { EM_DASH, fixed, n, pct, pctRaw } from '../lib/format'

const REGIME_NOTE: Record<string, string> = {
  '1-random': 'Rows shuffled. Parcels from the same photograph land on both sides of the split.',
  '2-parcel': 'Grouped by parcel id. Barely moves the number — parcel grouping is not protection.',
  '3-event': 'Grouped by capture event. THE HEADLINE. One photograph, one label, one side of the split.',
  '4-village': 'Grouped by village. Tests transfer to land the model has never seen.',
}

/**
 * The Leakage Ladder, in-product.
 *
 * plan.md §1.2 and §6 Phase 4: this is a headline deliverable, not an appendix.
 * It is on a tab of the product because the honest number is the credential —
 * the same model and the same features under four splits, with only the split
 * changing. A reviewer who sees the random-split figure beside the event-grouped
 * one does not have to take the headline on trust.
 */
export function ValidationView() {
  const ladderQ = useQuery(() => api.ladder(), [])
  const confQ = useQuery(() => api.confusion(), [])
  const calQ = useQuery(() => api.calibration(), [])
  const forQ = useQuery(() => api.forensics(), [])

  return (
    <div>
      <div className="card">
        <h2>The Leakage Ladder</h2>
        <p className="sub">
          One model, one feature set, four validation splits. Only the split changes. The brief's
          own clause — spatial or parcel leakage invalidates a claimed result — is why this is on
          screen rather than in an appendix.
        </p>

        {ladderQ.loading ? (
          <Loading what="the ladder" />
        ) : ladderQ.error ? (
          <ErrorState error={ladderQ.error} what="The Leakage Ladder" />
        ) : ladderQ.data ? (
          <LadderBody
            rungs={ladderQ.data.data.ladder}
            headline={ladderQ.data.data.headline}
            heads={ladderQ.data.data.heads}
            sources={ladderQ.data.data.sources}
            comparisons={ladderQ.data.data.source_comparisons ?? []}
            regime={ladderQ.data.meta.split_regime}
          />
        ) : null}
        <Provenance meta={ladderQ.data?.meta} />
      </div>

      <div className="card">
        <h2>Per-class metrics with effective n</h2>
        <p className="sub">
          Record count is not sample size. A class's evidence is its number of independent capture
          events, and the two differ by up to 12× in this data.
        </p>
        {confQ.loading ? (
          <Loading what="per-class metrics" />
        ) : confQ.error ? (
          <ErrorState error={confQ.error} what="Per-class metrics" />
        ) : confQ.data ? (
          <PerClass
            rows={confQ.data.data.per_class}
            regime={confQ.data.meta.split_regime}
            head={confQ.data.meta.model_version}
          />
        ) : null}
        <Provenance meta={confQ.data?.meta} />
      </div>

      {confQ.data && (
        <div className="card">
          <h2>Confusion matrix</h2>
          <p className="sub">
            Rows are the declared crop, columns the satellite prediction. Shaded by share of the
            declared row, so a large class does not swamp the picture.
          </p>
          <div className="row" style={{ marginBottom: 8 }}>
            <RegimeChip regime={confQ.data.meta.split_regime} />
            {confQ.data.meta.model_version && <span className="chip">head: {confQ.data.meta.model_version}</span>}
          </div>
          <Heatmap
            labels={confQ.data.data.confusion_matrix.labels}
            counts={confQ.data.data.confusion_matrix.counts}
            rowTotalLabel="declared class"
          />
          <h3 style={{ fontSize: 12, marginTop: 16, marginBottom: 6 }}>Most-confused pairs</h3>
          <table className="data">
            <thead>
              <tr>
                <th>Declared</th>
                <th>Predicted</th>
                <th className="num">Records</th>
              </tr>
            </thead>
            <tbody>
              {confQ.data.data.top_confusions.map((c) => (
                <tr key={`${c.true}|${c.predicted}`}>
                  <td>{c.true}</td>
                  <td>{c.predicted}</td>
                  <td className="num">{n(c.n)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <Provenance meta={confQ.data.meta} />
        </div>
      )}

      <div className="card">
        <h2>Calibration</h2>
        <p className="sub">
          Uncalibrated confidence cannot route a budget. Isotonic calibration is fitted on
          validation folds only — fitting it on the evaluation set would manufacture the result it
          claims to measure.
        </p>
        {calQ.loading ? (
          <Loading what="calibration" />
        ) : calQ.error ? (
          <ErrorState error={calQ.error} what="Calibration (Phase 6)" />
        ) : calQ.data ? (
          <>
            <div className="row" style={{ marginBottom: 10 }}>
              <RegimeChip regime={calQ.data.meta.split_regime} />
            </div>
            <table className="data">
              <tbody>
                {Object.entries(calQ.data.data).map(([k, v]) => (
                  <tr key={k}>
                    <th style={{ textTransform: 'none', letterSpacing: 0, fontSize: 12.5, fontWeight: 500, color: 'var(--ink-2)' }}>
                      {k}
                    </th>
                    <td className="num" style={{ fontWeight: 600 }}>
                      {typeof v === 'number' ? fixed(v, 4) : String(v)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Provenance meta={calQ.data.meta} />
          </>
        ) : null}
      </div>

      <div className="card">
        <h2>What the supplied survey records actually contain</h2>
        <p className="sub">
          Phase 0 forensics. These are measurements of the data, not of the model, and they are why
          the ladder falls the way it does.
        </p>
        {forQ.loading ? (
          <Loading what="forensics" />
        ) : forQ.error ? (
          <ErrorState error={forQ.error} what="Ground-truth forensics" />
        ) : forQ.data ? (
          <Forensics d={forQ.data.data} />
        ) : null}
        <Provenance meta={forQ.data?.meta} />
      </div>
    </div>
  )
}

function LadderBody({
  rungs, headline, heads, sources, comparisons, regime,
}: {
  rungs: LadderRung[]
  headline: { regime: string; head: string; accuracy: number; macro_f1: number }
  heads: LadderRung[]
  sources: LadderRung[]
  comparisons: SourceComparison[]
  regime: string | null
}) {
  const loosest = rungs[0]
  const strictest = rungs[rungs.length - 1]
  const gapPP =
    loosest && strictest ? (loosest.accuracy - strictest.accuracy) * 100 : null

  return (
    <>
      <div className="grid3" style={{ marginBottom: 16 }}>
        <Tile label="Headline accuracy">
          <div className="value">{pct(headline.accuracy)}</div>
          <div style={{ marginTop: 6 }}><RegimeChip regime={headline.regime} /></div>
          <div className="note">head: {headline.head}. Never quoted without the regime.</div>
        </Tile>
        <Tile label="Headline macro F1">
          <div className="value">{fixed(headline.macro_f1, 3)}</div>
          <div style={{ marginTop: 6 }}><RegimeChip regime={headline.regime} /></div>
          <div className="note">Macro, so rare classes are not hidden by the 63% majority.</div>
        </Tile>
        <Tile
          label="Cost of honesty"
          value={gapPP === null ? EM_DASH : `${gapPP.toFixed(1)} pp`}
          note={`Accuracy lost moving from ${loosest?.regime} to ${strictest?.regime}. Same model, same features, only the split changed.`}
        />
      </div>

      <ChartFrame
        title="Accuracy and macro F1 under each split"
        aside={<RegimeChip regime={regime} />}
      >
        <HBars
          max={1}
          fmt={(v) => v.toFixed(2)}
          labelWidth={120}
          series={[
            { key: 'acc', label: 'accuracy', color: 'var(--series-1)' },
            { key: 'f1', label: 'macro F1', color: 'var(--series-2)' },
          ]}
          rows={rungs.map((r) => ({
            key: r.regime,
            label: r.regime,
            values: [r.accuracy, r.macro_f1],
            errors: [r.accuracy_std, r.macro_f1_std],
            note: REGIME_NOTE[r.regime] ?? undefined,
          }))}
        />
      </ChartFrame>
      <p style={{ fontSize: 12, color: 'var(--ink-2)' }}>
        Both series are unit-interval scores, so they share one axis honestly. Whiskers are the
        fold standard deviation.
      </p>
      {(() => {
        const r3 = rungs.find((r) => r.regime === headline.regime)
        return r3 ? (
          <p style={{ fontSize: 12, color: 'var(--ink-2)' }}>
            <strong>Why ★ {headline.regime} shows {pct(r3.accuracy)} here but the headline tile shows{' '}
            {pct(headline.accuracy)}:</strong> the ladder holds one model (LightGBM) fixed so the split is
            the only thing that changes. The headline is the best head ({headline.head}) under the same{' '}
            {headline.regime} split — see “Model heads” below. Both are honest; they answer different
            questions.
          </p>
        ) : null
      })()}

      <table className="data" style={{ marginTop: 6 }}>
        <thead>
          <tr>
            <th>Split regime</th>
            <th className="num">Accuracy</th>
            <th className="num">Macro F1</th>
            <th className="num">Log loss</th>
            <th>What it tests</th>
          </tr>
        </thead>
        <tbody>
          {rungs.map((r) => (
            <tr key={r.regime} style={r.regime === headline.regime ? { fontWeight: 600 } : undefined}>
              <td>{r.regime}{r.regime === headline.regime ? ' ★' : ''}</td>
              <td className="num">{pct(r.accuracy)} ± {pctRaw((r.accuracy_std ?? 0) * 100, 1)}</td>
              <td className="num">{fixed(r.macro_f1, 3)}</td>
              <td className="num">{fixed(r.log_loss ?? null, 3)}</td>
              <td style={{ fontWeight: 400, color: 'var(--ink-2)', fontSize: 12 }}>
                {REGIME_NOTE[r.regime] ?? EM_DASH}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="grid2" style={{ marginTop: 18 }}>
        <div>
          <ChartFrame title="Model heads, identical folds" aside={<RegimeChip regime={heads[0]?.regime ?? null} />}>
            <HBars
              max={1}
              fmt={(v) => v.toFixed(2)}
              labelWidth={112}
              series={[
                { key: 'acc', label: 'accuracy', color: 'var(--series-1)' },
                { key: 'f1', label: 'macro F1', color: 'var(--series-2)' },
              ]}
              rows={heads.map((h, i) => ({
                key: `${h.regime}-${(h as { head?: string }).head ?? i}`,
                label: (h as { head?: string }).head ?? `head ${i + 1}`,
                values: [h.accuracy, h.macro_f1],
              }))}
            />
          </ChartFrame>
        </div>
        <div>
          <ChartFrame title="Feature sources, identical folds" aside={<RegimeChip regime={sources[0]?.regime ?? null} />}>
            <HBars
              max={1}
              fmt={(v) => v.toFixed(2)}
              labelWidth={112}
              series={[
                { key: 'acc', label: 'accuracy', color: 'var(--series-1)' },
                { key: 'f1', label: 'macro F1', color: 'var(--series-2)' },
              ]}
              rows={sources.map((s, i) => ({
                key: `${s.regime}-${(s as { source?: string }).source ?? i}`,
                label: (s as { source?: string }).source ?? `source ${i + 1}`,
                values: [s.accuracy, s.macro_f1],
              }))}
            />
          </ChartFrame>
          {comparisons.length > 0 && (
            <>
              <p className="sub" style={{ marginTop: 10 }}>
                Each source against {comparisons[0].reference}, macro F1, fold by fold. A gap
                smaller than fold-to-fold noise is reported as underpowered, not as a result.
              </p>
              <table className="data">
                <thead>
                  <tr>
                    <th>Source</th>
                    <th style={{ textAlign: 'right' }}>Mean Δ</th>
                    <th style={{ textAlign: 'right' }}>SD of Δ</th>
                    <th style={{ textAlign: 'right' }}>Folds ahead</th>
                    <th>Verdict</th>
                  </tr>
                </thead>
                <tbody>
                  {comparisons
                    .filter((c) => c.metric === 'macro_f1')
                    .map((c) => (
                      <tr key={c.source}>
                        <td>{c.source}</td>
                        <td style={{ textAlign: 'right' }}>
                          {(c.mean_delta >= 0 ? '+' : '') + c.mean_delta.toFixed(3)}
                        </td>
                        <td style={{ textAlign: 'right' }}>{c.delta_sd.toFixed(3)}</td>
                        <td style={{ textAlign: 'right' }}>
                          {c.folds_favouring_source}/{c.folds}
                        </td>
                        <td>
                          {c.underpowered
                            ? 'underpowered: within fold noise'
                            : c.mean_delta > 0
                              ? 'ahead'
                              : 'behind'}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      </div>
    </>
  )
}

function PerClass({ rows, regime, head }: { rows: PerClassRow[]; regime: string | null; head: string | null }) {
  const sorted = [...rows].sort((a, b) => b.f1 - a.f1)
  return (
    <>
      <div className="row" style={{ marginBottom: 10 }}>
        <RegimeChip regime={regime} />
        {head && <span className="chip">head: {head}</span>}
      </div>
      <ChartFrame title="F1 by crop">
        <HBars
          max={1}
          fmt={(v) => v.toFixed(2)}
          labelWidth={132}
          series={[{ key: 'f1', label: 'F1', color: 'var(--series-1)' }]}
          rows={sorted.map((r) => ({
            key: r.crop,
            label: r.crop,
            values: [r.f1],
            note: `${n(r.records)} records but only ${n(r.capture_events)} independent capture events`,
          }))}
        />
      </ChartFrame>
      <table className="data">
        <thead>
          <tr>
            <th>Crop</th>
            <th className="num">Records</th>
            <th className="num" title="Independent capture events. This is the sample size.">
              Effective n
            </th>
            <th className="num">Inflation</th>
            <th className="num">Precision</th>
            <th className="num">Recall</th>
            <th className="num">F1</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => (
            <tr key={r.crop}>
              <td>{r.crop}</td>
              <td className="num" style={{ color: 'var(--ink-muted)' }}>{n(r.records)}</td>
              <td className="num" style={{ fontWeight: 650 }}>{n(r.capture_events)}</td>
              <td className="num">{r.capture_events ? `${(r.records / r.capture_events).toFixed(1)}×` : EM_DASH}</td>
              <td className="num">{fixed(r.precision, 3)}</td>
              <td className="num">{fixed(r.recall, 3)}</td>
              <td className="num" style={{ fontWeight: 600 }}>{fixed(r.f1, 3)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p style={{ fontSize: 12, color: 'var(--ink-2)', marginBottom: 0 }}>
        Low F1 on a class with few capture events is a finding about the data, not a modelling
        failure. It is reported rather than hidden behind a macro average.
      </p>
    </>
  )
}

function Forensics({ d }: { d: ForensicsPayload }) {
  const dist = d.photo_to_parcel_distance_m ?? {}
  const eff = d.per_crop_effective_n ?? {}
  const effRows = Object.entries(eff).sort((a, b) => b[1].records - a[1].records)
  return (
    <>
      <div className="grid3" style={{ marginBottom: 14 }}>
        <Tile
          label="Records → capture events"
          value={`${n(d.n_records)} → ${n(d.n_capture_events)}`}
          note={`${fixed(d.label_inflation_factor ?? null, 2)}× label inflation. One photograph supplies up to ${n(d.max_parcels_per_capture_event)} parcel labels.`}
        />
        <Tile
          label="Median photo-to-parcel distance"
          value={dist.median !== undefined ? `${n(dist.median)} m` : EM_DASH}
          note={`p90 ${n(dist.p90)} m · ${pctRaw(dist.pct_over_1km ?? null)} of photographs were taken over a kilometre from the parcel they document.`}
        />
        <Tile
          label="Capture events with a mixed crop label"
          value={n(d.capture_events_with_mixed_crop_label)}
          note="Zero. The label is attached to the event and copied to every parcel in it — which is exactly why event-grouped splitting is the honest one."
        />
      </div>
      {effRows.length > 0 && (
        <>
          <h3 style={{ fontSize: 12, margin: '0 0 6px' }}>Effective n per crop</h3>
          <table className="data">
            <thead>
              <tr>
                <th>Crop</th>
                <th className="num">Records</th>
                <th className="num">Capture events</th>
                <th className="num">Inflation</th>
              </tr>
            </thead>
            <tbody>
              {effRows.map(([crop, v]) => (
                <tr key={crop}>
                  <td>{crop}</td>
                  <td className="num" style={{ color: 'var(--ink-muted)' }}>{n(v.records)}</td>
                  <td className="num" style={{ fontWeight: 650 }}>{n(v.capture_events)}</td>
                  <td className="num">{fixed(v.inflation, 1)}×</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </>
  )
}
