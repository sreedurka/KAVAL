import { triple, useThresholds } from '../lib/thresholds'
import { fixed } from '../lib/format'

/**
 * The thresholds, made movable.
 *
 * react-map-ui rule 3: an audit whose thresholds are invisible is not auditable.
 * These three numbers decide which parcels a surveyor walks to, so they are
 * shown, moved, and sent verbatim to every route that accepts them.
 */
function Slider({
  name, why, value, min, max, step, onChange,
}: {
  name: string; why: string; value: number; min: number; max: number; step: number
  onChange: (v: number) => void
}) {
  const id = `th-${name.replace(/\W+/g, '-')}`
  return (
    <label className="slider" htmlFor={id}>
      <span className="head">
        <span className="name">{name}</span>
        <span className="val">{fixed(value, 2)}</span>
      </span>
      <span className="why">{why}</span>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  )
}

export function ThresholdControls() {
  const { value, defaults, set, reset, atDefaults } = useThresholds()
  const t = triple(value)
  return (
    <div>
      <h2 style={{ margin: '0 0 2px', fontSize: 14 }}>Thresholds</h2>
      <p className="sub" style={{ fontSize: 12, color: 'var(--ink-2)', margin: '0 0 12px' }}>
        Move one and the map, the worklist and the surveyor-day saving all re-derive from the
        same call. Defaults come from the API, not from this UI.
      </p>

      <Slider
        name="confidence_high"
        why="Above this calibrated confidence, a disagreement becomes DISPUTED and an agreement can be CONFIRMED."
        value={value.confidence_high}
        min={0.3}
        max={0.99}
        step={0.01}
        onChange={(v) => set({ confidence_high: v })}
      />
      <Slider
        name="trust_floor"
        why="Below this Record Trust Score the record cannot be tested at all — UNVERIFIABLE, whatever the model thinks."
        value={value.trust_floor}
        min={0}
        max={0.9}
        step={0.01}
        onChange={(v) => set({ trust_floor: v })}
      />
      <Slider
        name="trust_high"
        why="A record must clear this before an agreement is allowed to auto-clear a field visit."
        value={value.trust_high}
        min={0}
        max={0.99}
        step={0.01}
        onChange={(v) => set({ trust_high: v })}
      />

      <div className="row">
        <button className="btn" onClick={reset} disabled={atDefaults}>
          Reset to API defaults
        </button>
        {!atDefaults && <span className="chip warn">moved from config</span>}
      </div>

      <div className="prov">
        config: confidence_high={fixed(defaults.confidence_high, 2)} · trust_floor=
        {fixed(defaults.trust_floor, 2)} · trust_high={fixed(defaults.trust_high, 2)}
        <br />
        sent as: {Object.entries(t).map(([k, v]) => `${k}=${v}`).join('&')}
      </div>
    </div>
  )
}
