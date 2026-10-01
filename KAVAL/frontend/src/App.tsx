import { useEffect, useState } from 'react'
import { USE_MOCK, api, fetchDefaultThresholds } from './api/client'
import { ThresholdProvider } from './lib/thresholds'
import { ThresholdControls } from './components/ThresholdControls'
import { ErrorState, Loading } from './components/common'
import { AuditMapView } from './views/AuditMapView'
import { VillageAuditView } from './views/VillageAuditView'
import { WorklistView } from './views/WorklistView'
import { AutoClearView } from './views/AutoClearView'
import { ValidationView } from './views/ValidationView'
import { AnalystView } from './views/AnalystView'
import { useQuery } from './lib/useQuery'

/**
 * `needsThresholds` marks the views that consume the threshold triple, and
 * therefore the ones that cannot render before Phase 6 has written
 * `audit.parquet`. The Leakage Ladder deliberately is NOT one of them: Phase 4
 * finishes long before Phase 6, and the honesty credential must be viewable the
 * moment it exists rather than waiting on the audit layer.
 */
const TABS = [
  { id: 'map', label: 'Audit map', el: AuditMapView, needsThresholds: true },
  { id: 'villages', label: 'Village audit', el: VillageAuditView, needsThresholds: false },
  { id: 'worklist', label: 'Field worklist', el: WorklistView, needsThresholds: true },
  { id: 'autoclear', label: 'Auto-clear', el: AutoClearView, needsThresholds: true },
  { id: 'validation', label: 'Leakage Ladder', el: ValidationView, needsThresholds: false },
  { id: 'analyst', label: 'Analyst', el: AnalystView, needsThresholds: false },
] as const

type TabId = (typeof TABS)[number]['id']

type Theme = 'system' | 'light' | 'dark'

function useTheme(): [Theme, (t: Theme) => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    try {
      const v = localStorage.getItem('kaval-theme')
      if (v === 'light' || v === 'dark' || v === 'system') return v
    } catch {
      /* private mode, blocked storage — fall through to system */
    }
    return 'system'
  })
  useEffect(() => {
    const root = document.documentElement
    if (theme === 'system') root.removeAttribute('data-theme')
    else root.setAttribute('data-theme', theme)
    try {
      localStorage.setItem('kaval-theme', theme)
    } catch {
      /* not fatal */
    }
  }, [theme])
  return [theme, setTheme]
}

function HealthChip() {
  const q = useQuery(() => api.health(), [])
  if (q.loading) return <span className="chip">checking API…</span>
  if (q.error) return <span className="chip" style={{ borderColor: 'var(--st-disputed)' }}>API unreachable</span>
  // Something answering on the proxied port is not proof it is KAVAL. /health
  // must carry `phases_available`, or we are talking to a stranger.
  if (!q.data?.phases_available)
    return (
      <span
        className="chip warn"
        title="Something answered /health but it is not the KAVAL API — check what is listening on the proxied port."
      >
        ⚠ not the KAVAL API
      </span>
    )
  const p = q.data.phases_available
  const missing = p ? Object.entries(p).filter(([, ok]) => !ok).map(([k]) => k) : []
  return (
    <span
      className="chip"
      title={
        missing.length
          ? `These phases have not produced their artefacts yet: ${missing.join(', ')}`
          : 'All phase artefacts present.'
      }
    >
      API {q.data?.status}
      {missing.length ? ` · missing: ${missing.join(', ')}` : ''}
    </span>
  )
}

function initialTab(): TabId {
  // `#map?village=Sivagiri` — the tab is the path part, views own the query.
  const h = window.location.hash.replace('#', '').split('?')[0]
  return TABS.some((t) => t.id === h) ? (h as TabId) : 'map'
}

export default function App() {
  // Hash routing, so a reviewer can be sent straight to the ladder or the worklist.
  const [tab, setTab] = useState<TabId>(initialTab)
  useEffect(() => {
    // Only rewrite when the tab itself changed, so a view's own query
    // parameters (the map's village deep-link) survive.
    if (window.location.hash.replace('#', '').split('?')[0] !== tab) window.location.hash = tab
  }, [tab])
  useEffect(() => {
    const on = () => setTab(initialTab())
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  const [theme, setTheme] = useTheme()
  const boot = useQuery(() => fetchDefaultThresholds(), [])
  const activeTab = TABS.find((t) => t.id === tab)!
  const Active = activeTab.el

  return (
    <div className="app">
      {USE_MOCK && (
        <div className="mockbar">
          <span>Mock data</span>&nbsp;&nbsp;VITE_USE_MOCK=1 — every figure on screen is synthetic.
          Nothing here is a measurement. Restart without the flag to read the live API.
        </div>
      )}

      <header className="top">
        <div className="brand">
          KAVAL
          <small>The classifier is the instrument. The product is the audit.</small>
        </div>
        <nav className="tabs" aria-label="Views">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              aria-current={t.id === tab ? 'page' : undefined}
            >
              {t.label}
            </button>
          ))}
        </nav>
        <HealthChip />
        <label style={{ fontSize: 12, color: 'var(--ink-2)' }}>
          <span className="sr-only">Theme</span>
          <select value={theme} onChange={(e) => setTheme(e.target.value as Theme)}>
            <option value="system">system theme</option>
            <option value="light">light</option>
            <option value="dark">dark</option>
          </select>
        </label>
      </header>

      <div className="main">
        {boot.loading ? (
          <div className="content">
            <Loading what="threshold configuration from the API" />
          </div>
        ) : boot.error ? (
          // Thresholds come from /parcels, which 503s until Phase 6 has written
          // audit.parquet. That must not take the whole product down: the views
          // that do not consume thresholds still render, so the Leakage Ladder
          // and the analyst work the moment their own phases do.
          <>
            <div className="content">
              {activeTab.needsThresholds ? (
                <ErrorState error={boot.error} what={activeTab.label} />
              ) : (
                <Active />
              )}
            </div>
            <aside className="rail">
              <h2 style={{ margin: '0 0 6px', fontSize: 14 }}>Thresholds</h2>
              <div className="state error">
                <h3>Not available</h3>
                <p style={{ margin: 0 }}>{boot.error.message}</p>
                <p style={{ margin: '8px 0 0', color: 'var(--ink-muted)', fontSize: 12 }}>
                  The sliders take their defaults from the API's own config and this UI will not
                  substitute its own.
                </p>
              </div>
            </aside>
          </>
        ) : boot.data ? (
          <ThresholdProvider defaults={boot.data}>
            <div className="content">
              <Active />
            </div>
            <aside className="rail">
              <ThresholdControls />
              <hr style={{ border: 0, borderTop: '1px solid var(--border)', margin: '16px 0' }} />
              <h2 style={{ fontSize: 13, margin: '0 0 6px' }}>Why this map is not coloured by crop</h2>
              <p style={{ fontSize: 12, color: 'var(--ink-2)', margin: 0 }}>
                A crop-coloured map answers "what is growing". This one answers "what should a
                surveyor do next". Disagreement is the product, not the error — so the most
                salient colour on screen belongs to the parcels where satellite and survey
                disagree, and agreement recedes.
              </p>
              <p style={{ fontSize: 12, color: 'var(--ink-2)' }}>
                Crop class is still available as a secondary layer on the map tab.
              </p>
            </aside>
          </ThresholdProvider>
        ) : null}
      </div>
    </div>
  )
}
