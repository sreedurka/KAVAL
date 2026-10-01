import { useCallback, useLayoutEffect, useRef, useState, type ReactNode } from 'react'

/**
 * Charts draw at the container's real pixel width. A fixed viewBox stretched to the
 * card scaled every label with it (11.5px text rendered near 20px on a wide card,
 * and long labels ran off the left edge), so text sizes here are true CSS pixels.
 */
function useWidth(fallback = 640) {
  const ref = useRef<HTMLDivElement>(null)
  const [w, setW] = useState(fallback)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const set = () => setW(Math.max(280, Math.floor(el.getBoundingClientRect().width)))
    set()
    const ro = new ResizeObserver(set)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return [ref, w] as const
}

/** Fit a label into `px` at ~11.5px text; the full label stays in a <title>. */
function fit(label: string, px: number) {
  const max = Math.max(4, Math.floor(px / 6.4))
  return label.length <= max ? label : label.slice(0, max - 1) + '…'
}

/**
 * Chart primitives, built to the `dataviz` skill.
 *
 * Standing rules applied here so no individual chart has to remember them:
 *   - thin marks; 4px rounded data-ends anchored to the baseline
 *   - a 2px surface-coloured gap between adjacent fills (`rect.mark` stroke)
 *   - recessive grid and axes; text in ink tokens, never in the series colour
 *   - a hover tooltip on every mark — an SVG chart in a browser IS interactive
 *   - one axis, always. No chart here has two value scales.
 */

export interface TipContent {
  title: string
  rows: { k: string; v: string }[]
  note?: string
}

export function useTooltip() {
  const [tip, setTip] = useState<{ x: number; y: number; c: TipContent } | null>(null)
  const show = useCallback((e: { clientX: number; clientY: number }, c: TipContent) => {
    setTip({ x: e.clientX, y: e.clientY, c })
  }, [])
  const hide = useCallback(() => setTip(null), [])
  const node = tip ? (
    <div
      className="tooltip"
      role="tooltip"
      style={{ left: Math.min(tip.x + 14, window.innerWidth - 300), top: tip.y + 14 }}
    >
      <div className="t">{tip.c.title}</div>
      {tip.c.rows.map((r) => (
        <div className="r" key={r.k}>
          <span style={{ color: 'var(--ink-2)' }}>{r.k}</span>
          <span>{r.v}</span>
        </div>
      ))}
      {tip.c.note && <div style={{ color: 'var(--ink-muted)', marginTop: 4, fontSize: 11 }}>{tip.c.note}</div>}
    </div>
  ) : null
  return { show, hide, node }
}

export interface Series {
  key: string
  label: string
  /** CSS colour expression, e.g. `var(--series-1)`. */
  color: string
  /** 45° hatch as the secondary channel (CVD / print / forced-colors). */
  hatch?: boolean
}

export interface BarRow {
  key: string
  label: string
  /** One number per series, same order. */
  values: (number | null)[]
  /** Optional ± for an error whisker, same order. */
  errors?: (number | null)[]
  note?: string
}

/**
 * Grouped horizontal bars on a single value axis.
 *
 * Horizontal because the categories are named things (regimes, crops, villages)
 * whose labels must be readable without rotation.
 */
export function HBars({
  rows, series, max, fmt, ticks = 5, rowHeight = 22, labelWidth = 150, directLabels = true,
}: {
  rows: BarRow[]
  series: Series[]
  max: number
  fmt: (v: number) => string
  ticks?: number
  rowHeight?: number
  labelWidth?: number
  directLabels?: boolean
}) {
  const { show, hide, node } = useTooltip()
  const [ref, w] = useWidth()
  const pad = { t: 8, r: 58, b: 22, l: Math.min(labelWidth, Math.round(w * 0.42)) }
  const groupH = rowHeight * series.length + 10
  const h = pad.t + rows.length * groupH + pad.b
  const plotW = w - pad.l - pad.r
  const x = (v: number) => (Math.max(0, v) / (max || 1)) * plotW
  const tickVals = Array.from({ length: ticks + 1 }, (_, i) => (max / ticks) * i)

  return (
    <div ref={ref}>
      {series.length >= 2 && (
        <div className="row" style={{ marginBottom: 6, gap: 14 }}>
          {series.map((s) => (
            <span key={s.key} className="row" style={{ gap: 6 }}>
              <span
                className={`swatch${s.hatch ? ' hatch' : ''}`}
                style={{ background: s.color }}
                aria-hidden
              />
              <span style={{ fontSize: 12 }}>{s.label}</span>
            </span>
          ))}
        </div>
      )}
      <svg className="chart" width={w} height={h} role="img">
        {tickVals.map((t, i) => (
          <g key={i}>
            <line className="gridline" x1={pad.l + x(t)} x2={pad.l + x(t)} y1={pad.t} y2={h - pad.b} />
            <text className="tick" x={pad.l + x(t)} y={h - pad.b + 13} textAnchor="middle">
              {fmt(t)}
            </text>
          </g>
        ))}
        <line className="baseline" x1={pad.l} x2={pad.l} y1={pad.t} y2={h - pad.b} />
        {rows.map((r, ri) => (
          <g key={r.key} transform={`translate(0 ${pad.t + ri * groupH})`}>
            <text className="lbl" x={pad.l - 10} y={groupH / 2 + 1} textAnchor="end" dominantBaseline="middle">
              <title>{r.label}</title>
              {fit(r.label, pad.l - 14)}
            </text>
            {series.map((s, si) => {
              const v = r.values[si]
              if (v === null || v === undefined || !Number.isFinite(v)) return null
              const y = si * rowHeight + 5
              const bw = Math.max(2, x(v))
              const err = r.errors?.[si]
              return (
                <g key={s.key}>
                  <rect
                    className="mark"
                    x={pad.l}
                    y={y}
                    width={bw}
                    height={rowHeight - 6}
                    rx={4}
                    fill={s.color}
                    fillOpacity={s.hatch ? 0.75 : 1}
                    onMouseMove={(e) =>
                      show(e, {
                        title: r.label,
                        rows: [
                          { k: s.label, v: fmt(v) },
                          ...(err ? [{ k: '± (fold sd)', v: fmt(err) }] : []),
                        ],
                        note: r.note,
                      })
                    }
                    onMouseLeave={hide}
                  />
                  {err ? (
                    <g stroke="var(--ink-2)" strokeWidth={1}>
                      <line x1={pad.l + x(v - err)} x2={pad.l + x(v + err)} y1={y + (rowHeight - 6) / 2} y2={y + (rowHeight - 6) / 2} />
                      <line x1={pad.l + x(v - err)} x2={pad.l + x(v - err)} y1={y + 3} y2={y + rowHeight - 9} />
                      <line x1={pad.l + x(v + err)} x2={pad.l + x(v + err)} y1={y + 3} y2={y + rowHeight - 9} />
                    </g>
                  ) : null}
                  {directLabels && (
                    // Clear the whisker, not just the bar, so the two never collide.
                    <text
                      className="lbl"
                      x={pad.l + Math.max(bw, err ? x(v + err) : 0) + 8}
                      y={y + (rowHeight - 6) / 2}
                      dominantBaseline="middle"
                    >
                      {fmt(v)}
                    </text>
                  )}
                </g>
              )
            })}
          </g>
        ))}
      </svg>
      {node}
    </div>
  )
}

/**
 * Diverging bars around a zero baseline. Blue/red poles with a neutral gap —
 * the sign is the message, so the midpoint has to read as "nothing".
 */
export function DivergingBars({
  rows, fmt, unit,
}: {
  rows: { key: string; label: string; value: number; note?: string }[]
  fmt: (v: number) => string
  unit: string
}) {
  const { show, hide, node } = useTooltip()
  const max = Math.max(1e-9, ...rows.map((r) => Math.abs(r.value)))
  const rowH = 20
  const [ref, w] = useWidth()
  const pad = { t: 6, r: 62, b: 20, l: Math.min(230, Math.round(w * 0.4)) }
  const h = pad.t + rows.length * rowH + pad.b
  const plotW = w - pad.l - pad.r
  const mid = pad.l + plotW / 2
  const x = (v: number) => (v / max) * (plotW / 2)

  return (
    <div ref={ref}>
      <div className="row" style={{ marginBottom: 6, gap: 14 }}>
        <span className="row" style={{ gap: 6 }}>
          <span className="swatch" style={{ background: 'var(--div-neg)' }} aria-hidden />
          <span style={{ fontSize: 12 }}>satellite below declared</span>
        </span>
        <span className="row" style={{ gap: 6 }}>
          <span className="swatch" style={{ background: 'var(--div-pos)' }} aria-hidden />
          <span style={{ fontSize: 12 }}>satellite above declared</span>
        </span>
      </div>
      <svg className="chart" width={w} height={h} role="img">
        <line className="baseline" x1={mid} x2={mid} y1={pad.t} y2={h - pad.b} />
        <text className="tick" x={mid} y={h - pad.b + 13} textAnchor="middle">0 {unit}</text>
        <text className="tick" x={pad.l} y={h - pad.b + 13} textAnchor="start">−{fmt(max)}</text>
        <text className="tick" x={w - pad.r} y={h - pad.b + 13} textAnchor="end">+{fmt(max)}</text>
        {rows.map((r, i) => {
          const bw = Math.abs(x(r.value))
          const neg = r.value < 0
          return (
            <g key={r.key} transform={`translate(0 ${pad.t + i * rowH})`}>
              <text className="lbl" x={pad.l - 10} y={rowH / 2} textAnchor="end" dominantBaseline="middle">
                <title>{r.label}</title>
                {fit(r.label, pad.l - 14)}
              </text>
              <rect
                className="mark"
                x={neg ? mid - bw : mid}
                y={3}
                width={Math.max(2, bw)}
                height={rowH - 6}
                rx={4}
                fill={neg ? 'var(--div-neg)' : 'var(--div-pos)'}
                onMouseMove={(e) => show(e, { title: r.label, rows: [{ k: `delta (${unit})`, v: fmt(r.value) }], note: r.note })}
                onMouseLeave={hide}
              />
              {/* Long bars label inside, so the value never collides with the
                  category name at the far end of the axis. */}
              {bw > 42 ? (
                <text
                  className="lbl"
                  x={neg ? mid - bw + 7 : mid + bw - 7}
                  y={rowH / 2}
                  textAnchor={neg ? 'start' : 'end'}
                  dominantBaseline="middle"
                  style={{ fill: 'var(--surface-1)' }}
                >
                  {fmt(r.value)}
                </text>
              ) : (
                <text
                  className="lbl"
                  x={neg ? mid - bw - 7 : mid + bw + 7}
                  y={rowH / 2}
                  textAnchor={neg ? 'end' : 'start'}
                  dominantBaseline="middle"
                >
                  {fmt(r.value)}
                </text>
              )}
            </g>
          )
        })}
      </svg>
      {node}
    </div>
  )
}

/** Sequential single-hue heatmap. One hue, light → dark. Never a rainbow. */
export function Heatmap({
  labels, counts, rowTotalLabel = 'row total',
}: {
  labels: string[]
  counts: number[][]
  rowTotalLabel?: string
}) {
  const { show, hide, node } = useTooltip()
  const cell = 46
  const pad = { t: 74, l: 132, r: 8, b: 8 }
  const w = pad.l + labels.length * cell + pad.r
  const h = pad.t + labels.length * cell + pad.b
  const steps = ['var(--seq-100)', 'var(--seq-250)', 'var(--seq-400)', 'var(--seq-550)', 'var(--seq-700)']

  return (
    <div style={{ overflowX: 'auto' }}>
      <svg className="chart" width={w} height={h} role="img">
        {labels.map((l, j) => (
          <text
            key={l}
            className="tick"
            transform={`translate(${pad.l + j * cell + cell / 2} ${pad.t - 8}) rotate(-40)`}
            textAnchor="start"
          >
            {l}
          </text>
        ))}
        {labels.map((l, i) => {
          const total = counts[i].reduce((a, b) => a + b, 0) || 1
          return (
            <g key={l}>
              <text className="tick" x={pad.l - 8} y={pad.t + i * cell + cell / 2} textAnchor="end" dominantBaseline="middle">
                {l}
              </text>
              {labels.map((m, j) => {
                const v = counts[i][j]
                const frac = v / total
                const si = frac === 0 ? -1 : Math.min(4, Math.floor(frac * 5))
                return (
                  <g key={m}>
                    <rect
                      className="mark"
                      x={pad.l + j * cell}
                      y={pad.t + i * cell}
                      width={cell}
                      height={cell}
                      rx={4}
                      fill={si < 0 ? 'var(--surface-2)' : steps[si]}
                      onMouseMove={(e) =>
                        show(e, {
                          title: `declared ${l} → predicted ${m}`,
                          rows: [
                            { k: 'records', v: v.toLocaleString() },
                            { k: `share of ${rowTotalLabel}`, v: `${(frac * 100).toFixed(1)}%` },
                          ],
                        })
                      }
                      onMouseLeave={hide}
                    />
                    <text
                      x={pad.l + j * cell + cell / 2}
                      y={pad.t + i * cell + cell / 2}
                      textAnchor="middle"
                      dominantBaseline="middle"
                      style={{ fontSize: 10.5, fill: si >= 3 ? 'var(--surface-1)' : 'var(--ink-2)' }}
                    >
                      {v}
                    </text>
                  </g>
                )
              })}
            </g>
          )
        })}
      </svg>
      {node}
    </div>
  )
}

/** A single-row stacked bar. Segments separated by a 2px surface gap. */
export function StackedBar({
  segments, total, height = 26,
}: {
  segments: { key: string; label: string; value: number; color: string; hatch?: boolean }[]
  total: number
  height?: number
}) {
  const { show, hide, node } = useTooltip()
  const w = 640
  let x = 0
  return (
    <div>
      <svg className="chart" viewBox={`0 0 ${w} ${height}`} role="img" preserveAspectRatio="none" style={{ height }}>
        <defs>
          <pattern id="hatch45" width="6" height="6" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
            <rect width="6" height="6" fill="var(--st-unverifiable)" />
            <line x1="0" y1="0" x2="0" y2="6" stroke="var(--surface-1)" strokeWidth="2.4" />
          </pattern>
        </defs>
        {segments.map((s) => {
          const bw = (s.value / (total || 1)) * w
          const seg = (
            <rect
              key={s.key}
              className="mark"
              x={x}
              y={0}
              width={Math.max(0, bw)}
              height={height}
              rx={3}
              fill={s.hatch ? 'url(#hatch45)' : s.color}
              onMouseMove={(e) =>
                show(e, {
                  title: s.label,
                  rows: [
                    { k: 'parcels', v: s.value.toLocaleString() },
                    { k: 'share', v: `${((s.value / (total || 1)) * 100).toFixed(1)}%` },
                  ],
                })
              }
              onMouseLeave={hide}
            />
          )
          x += bw
          return seg
        })}
      </svg>
      {node}
    </div>
  )
}

export function ChartFrame({ title, aside, children }: { title: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div className="row" style={{ marginBottom: 6 }}>
        <strong style={{ fontSize: 12.5 }}>{title}</strong>
        <span className="spacer" />
        {aside}
      </div>
      {children}
    </div>
  )
}
