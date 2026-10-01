import { useRef, useState } from 'react'
import { ApiError, api } from '../api/client'
import type { AnalystAnswer, AnalystPlanner } from '../api/types'
import { useQuery } from '../lib/useQuery'
import { Provenance, RegimeChip } from '../components/common'
import { Markdown } from '../components/Markdown'
import { n } from '../lib/format'

/**
 * The agentic analyst (AI-5), Phase 7b.
 *
 * Wired to POST /analyst/query. Two things this panel insists on:
 *   - every answer renders its citations and the tool calls that produced them.
 *     An audit system whose analyst asserts numbers without provenance defeats
 *     its own purpose, so an answer with no citations is shown as such.
 *   - every answer says which planner produced it. Without ANTHROPIC_API_KEY
 *     the API answers through its offline rule-based planner (keyword routing
 *     over the same tools); that is labelled on every answer as "not LLM", so a
 *     reader can never mistake it for LLM planning.
 *   - a 503 is a *state*, not a crash (only reachable when the LLM planner is
 *     forced without a key).
 */

// The nine questions scripts/p7_verify_analyst.py verifies end to end: the brief's
// six analysis requests, then the three the product exists to answer.
const SUGGESTIONS = [
  'Using the supplied satellite embeddings, classify all agricultural parcels in the selected study area. Show crop-wise cultivated area and confidence, and highlight low-confidence parcels that require field verification.',
  'Show crop-wise area for the selected village and highlight parcels below 80% confidence.',
  'Compare the performance obtained from Google Satellite Embeddings and Presto embeddings where both are supplied.',
  'Show villages where predicted crop area differs significantly from the supplied registry.',
  'List the crop classes with the highest confusion and show representative errors.',
  'Export the classified parcel layer, confidence values and crop-area summary.',
  'Where should we send 500 surveyors next season?',
  'Which parcels can we stop visiting?',
  'How trustworthy is the ground truth itself?',
]

function PlannerChip({ planner, provider }: { planner: AnalystPlanner; provider?: string | null }) {
  return planner === 'offline' ? (
    <span className="chip warn" title="Routed by keyword to the typed tools; not LLM planning">
      offline planner — not LLM
    </span>
  ) : (
    <span className="chip regime" title="An LLM chose which typed tools to call">
      LLM{provider ? ` · ${provider}` : ''}
    </span>
  )
}

interface Turn {
  q: string
  a: AnalystAnswer | null
  error: Error | null
  pending: boolean
}

export function AnalystView() {
  const [turns, setTurns] = useState<Turn[]>([])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)
  const toolsQ = useQuery(() => api.analystTools(), [])

  const planner = toolsQ.data?.planner
  const plannerNote = toolsQ.data?.planner_note ?? turns.find((t) => t.a)?.a?.planner_note
  // Only a real 503 from the tools endpoint means the analyst is down; the offline
  // planner is a working state, not an outage.
  const unavailable =
    planner !== 'offline' && toolsQ.error instanceof ApiError && toolsQ.error.isPhaseMissing

  async function ask(q: string) {
    if (!q.trim() || busy) return
    setText('')
    setBusy(true)
    const i = turns.length
    setTurns((t) => [...t, { q, a: null, error: null, pending: true }])
    try {
      const a = await api.analystQuery(q)
      setTurns((t) => t.map((x, j) => (j === i ? { ...x, a, pending: false } : x)))
    } catch (e) {
      setTurns((t) =>
        t.map((x, j) => (j === i ? { ...x, error: e as Error, pending: false } : x)),
      )
    } finally {
      setBusy(false)
      queueMicrotask(() => endRef.current?.scrollIntoView({ behavior: 'smooth' }))
    }
  }

  return (
    <div className="grid2" style={{ gridTemplateColumns: '1fr 300px', alignItems: 'start' }}>
      <div className="card">
        <h2>Analyst</h2>
        <p className="sub">
          Ask in plain language. The analyst plans over the typed tool layer and never computes a
          number itself — every figure in an answer came out of a tool call.
        </p>
        {planner && (
          <div className="row" style={{ marginBottom: 10, gap: 8 }}>
            <span style={{ fontSize: 12, color: 'var(--ink-2)' }}>Active planner:</span>
            <PlannerChip planner={planner} provider={toolsQ.data?.provider} />
          </div>
        )}

        {unavailable && (
          <div className="state" style={{ marginBottom: 12 }}>
            <strong>The analyst is unavailable.</strong>
            <p style={{ margin: '6px 0 0' }}>{toolsQ.error?.message}</p>
            <p style={{ margin: '6px 0 0', color: 'var(--ink-muted)', fontSize: 12 }}>
              Every other endpoint still works. Unset <code>KAVAL_ANALYST_PLANNER=llm</code> to use
              the offline planner, or set <code>ANTHROPIC_API_KEY</code> and restart uvicorn.
            </p>
          </div>
        )}

        <div className="chat">
          {turns.length === 0 && (
            <div className="state">
              Nothing asked yet. Try one of the starters on the right — they are the analysis
              requests the challenge brief asks for.
            </div>
          )}
          {turns.map((t, i) => (
            <div key={i}>
              <div className="msg user">
                <div className="who">You</div>
                <div>{t.q}</div>
              </div>
              <div className="msg bot" style={{ marginTop: 8 }}>
                <div className="who" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  KAVAL analyst
                  {t.a && <PlannerChip planner={t.a.planner} provider={t.a.provider} />}
                </div>
                {t.pending && (
                  <div style={{ color: 'var(--ink-2)' }}>
                    Planning over tools…
                    {toolsQ.data?.provider?.startsWith('local:') &&
                      ' A local model on CPU takes one to three minutes per question.'}
                  </div>
                )}
                {t.error && (
                  <div>
                    <div style={{ color: 'var(--st-disputed)', fontWeight: 600 }}>
                      {t.error instanceof ApiError && t.error.isPhaseMissing
                        ? 'The analyst is unavailable (503)'
                        : 'The analyst could not answer'}
                    </div>
                    <div style={{ color: 'var(--ink-2)', marginTop: 4 }}>{t.error.message}</div>
                  </div>
                )}
                {t.a && (
                  <>
                    <Markdown text={t.a.answer} />
                    <div className="cites">
                      {t.a.citations.length === 0 ? (
                        <span className="chip warn">
                          {t.a.tool_calls.length === 0
                            ? 'no tools called — no figures stated'
                            : '⚠ answer carried no citations'}
                        </span>
                      ) : (
                        t.a.citations.map((c, j) => (
                          <span
                            key={j}
                            className="chip"
                            title={c.parcel_ids?.length ? `${c.source}\n${c.parcel_ids.join(', ')}` : c.source}
                          >
                            {c.source}
                            {c.parcel_ids?.length
                              ? ` · ${n(c.parcel_ids.length)} parcel${c.parcel_ids.length === 1 ? '' : 's'} cited`
                              : ''}
                            {c.n !== null && c.n !== undefined ? ` · n=${n(c.n)}` : ''}
                            {c.split_regime ? ` · split: ${c.split_regime}` : ''}
                          </span>
                        ))
                      )}
                    </div>
                    {t.a.tool_calls.length > 0 && (
                      <details style={{ marginTop: 8 }}>
                        <summary style={{ cursor: 'pointer', fontSize: 12, color: 'var(--ink-2)' }}>
                          {t.a.tool_calls.length} tool call
                          {t.a.tool_calls.length === 1 ? '' : 's'}
                        </summary>
                        {t.a.tool_calls.map((c, j) => (
                          <div className="toolcall" key={j}>
                            {c.tool}({JSON.stringify(c.args)})
                          </div>
                        ))}
                      </details>
                    )}
                  </>
                )}
              </div>
            </div>
          ))}
          <div ref={endRef} />
        </div>

        <form
          className="row"
          style={{ marginTop: 14 }}
          onSubmit={(e) => {
            e.preventDefault()
            void ask(text)
          }}
        >
          <input
            type="text"
            style={{ flex: 1 }}
            placeholder="Ask about parcels, villages, area, the worklist or the validation…"
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={busy}
          />
          <button className="btn primary" type="submit" disabled={busy || !text.trim()}>
            {busy ? 'Thinking…' : 'Ask'}
          </button>
        </form>
        {plannerNote && (
          <p className="prov" style={{ marginTop: 8 }}>
            {plannerNote}
          </p>
        )}
      </div>

      <div>
        <div className="card">
          <h2>Starters</h2>
          <p className="sub">
            The brief's six analysis requests, then three product questions — all nine verified end
            to end by <code>scripts/p7_verify_analyst.py</code>.
          </p>
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              className="btn"
              style={{ display: 'block', width: '100%', textAlign: 'left', marginBottom: 6 }}
              onClick={() => void ask(s)}
              disabled={busy}
            >
              {s}
            </button>
          ))}
        </div>

        <div className="card">
          <h2>Tools the analyst can call</h2>
          <p className="sub">
            The same endpoints this UI reads. The agent and the screen cannot disagree, because
            they share the code path.
          </p>
          {toolsQ.loading && <div style={{ color: 'var(--ink-2)', fontSize: 12 }}>Loading…</div>}
          {toolsQ.error && !unavailable && (
            <div style={{ color: 'var(--ink-2)', fontSize: 12 }}>{toolsQ.error.message}</div>
          )}
          {toolsQ.data && (
            <>
              <div className="prov" style={{ marginTop: 0, marginBottom: 8 }}>
                {toolsQ.data.planner === 'offline'
                  ? 'planner: offline, rule-based (no LLM available: set a free GEMINI_API_KEY or start the local model)'
                  : `planner: LLM · first in the fallback chain: ${toolsQ.data.provider ?? toolsQ.data.model} (each answer names the model that actually answered)`}
              </div>
              {toolsQ.data.tools.map((t) => (
                <div key={t.name} style={{ marginBottom: 8 }}>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 11.5, fontWeight: 600 }}>{t.name}</div>
                  <div style={{ fontSize: 11.5, color: 'var(--ink-2)' }}>{t.description}</div>
                </div>
              ))}
            </>
          )}
        </div>

        <div className="card">
          <h2>What the analyst will not do</h2>
          <ul style={{ fontSize: 12, color: 'var(--ink-2)', margin: 0, paddingLeft: 18, lineHeight: 1.7 }}>
            <li>Compute a number itself — model arithmetic is not evidence.</li>
            <li>State a metric without its split regime.</li>
            <li>Call a parcel "wrong". The record and the satellite disagree; a visit decides.</li>
          </ul>
          <div className="row" style={{ marginTop: 10 }}>
            <RegimeChip regime={null} metric={false} />
          </div>
          <Provenance meta={null} />
        </div>
      </div>
    </div>
  )
}
