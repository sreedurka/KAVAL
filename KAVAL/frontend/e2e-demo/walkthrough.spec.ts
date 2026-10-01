import { expect, test, type Page } from '@playwright/test'

/**
 * The recorded demo: docs/DEMO_WALKTHROUGH.md, driven through the real UI and API,
 * in the order the walkthrough makes its argument (not the order the pipeline runs).
 * A caption bar carries each beat's line so the video explains itself without audio.
 * Every figure in a caption is fetched from the API at record time, like the UI's
 * own numbers; none is typed into this file.
 *
 *   npx playwright test -c playwright.demo.config.ts   →   docs/demo/raw/…/video.webm
 */

async function caption(page: Page, title: string, line: string, ms = 4500) {
  await page.evaluate(
    ([t, l]) => {
      let el = document.getElementById('kaval-demo-caption')
      if (!el) {
        el = document.createElement('div')
        el.id = 'kaval-demo-caption'
        el.style.cssText =
          'position:fixed;left:50%;bottom:22px;transform:translateX(-50%);z-index:99999;' +
          'max-width:980px;background:rgba(11,11,11,.88);color:#fff;border-radius:12px;' +
          'padding:12px 18px;font:14px/1.45 system-ui,sans-serif;box-shadow:0 8px 24px rgba(0,0,0,.3)'
        document.body.appendChild(el)
      }
      el.innerHTML = ''
      const b = document.createElement('div')
      b.style.cssText = 'font-weight:700;font-size:12px;letter-spacing:.06em;text-transform:uppercase;opacity:.75;margin-bottom:3px'
      b.textContent = t
      const p = document.createElement('div')
      p.textContent = l
      el.append(b, p)
    },
    [title, line],
  )
  await page.waitForTimeout(ms)
}

async function tab(page: Page, id: string) {
  await page.goto(`/#${id}`)
  await page.waitForLoadState('networkidle')
  await expect(page.locator('.state:has-text("Loading")')).toHaveCount(0, { timeout: 60_000 })
}

async function scrollTo(page: Page, heading: string) {
  await page.locator(`h2:has-text("${heading}")`).first().scrollIntoViewIfNeeded()
  await page.waitForTimeout(600)
}

const pct = (x: number, d = 1) => `${(100 * x).toFixed(d)}%`
const int = (x: number) => Math.round(x).toLocaleString('en-US')

test('KAVAL demo walkthrough', async ({ page }) => {
  const get = async (path: string) => (await (await page.request.get(`/api${path}`)).json()).data
  const lad = await get('/validation/ladder')
  const cal = await get('/validation/calibration')
  const ac = await get('/audit/auto-clear')
  const gt = await get('/evidence/forensics')
  const rung = (r: string) => lad.ladder.find((x: { regime: string }) => x.regime === r).accuracy
  const H = lad.headline

  await tab(page, 'map')
  await caption(page, 'KAVAL · the frame',
    'The classifier is the instrument. The product is the audit: which Digital Crop Survey records to trust, which to re-verify, and which parcels never need a visit.', 6000)

  // 1 · Why the target cannot be met honestly
  await tab(page, 'validation')
  await caption(page, '1 · The Leakage Ladder',
    `Same model, only the split changes: ${pct(rung('1-random'))} on random rows, ${pct(rung('3-event'))} grouped by survey capture event, ${pct(rung('4-village'))} by village. Headline: ${pct(H.accuracy)} (${H.head}, regime ${H.regime}). The brief's 95% is only reachable by leaking.`, 7500)
  await page.mouse.wheel(0, 900)
  await caption(page, '1 · Embeddings, compared honestly',
    'GSE vs Presto on identical folds, paired fold by fold. Presto alone is clearly behind; combining adds nothing measurable (marked underpowered).', 6000)

  // 2 · The evidence is not where you think it is
  await scrollTo(page, 'What the supplied survey records actually contain')
  await caption(page, '2 · The ground truth, audited',
    `${int(gt.n_records)} records are ${int(gt.n_capture_events)} capture events: one photograph labels up to ${gt.max_parcels_per_capture_event} parcels, a median ${int(gt.photo_to_parcel_distance_m.median)} m from the parcel it documents.`, 6500)

  // 3 · The map
  await tab(page, 'map')
  await caption(page, '3 · Coloured by agreement, not by crop',
    'Blue: satellite and survey agree (CONFIRMED). Red: they disagree at high confidence (DISPUTED). A disagreement is not a verdict: a field visit decides which is right.', 6500)
  const disputed = page.locator('.leaflet-overlay-pane path[fill="var(--st-disputed)"]')
  await expect.poll(async () => disputed.count(), { timeout: 60_000 }).toBeGreaterThan(0)
  await disputed.nth(3).click({ force: true })
  await caption(page, '3 · One DISPUTED parcel',
    'Declared crop, satellite estimate, calibrated confidence, and the record\'s trust: bag size, photo distance, attention support.', 6000)

  // 4 · Confidence you can route on
  await tab(page, 'validation')
  await scrollTo(page, 'Calibration')
  await caption(page, '4 · Calibration',
    `Raw confidence claims ${pct(cal.mean_confidence_raw)} and delivers ${pct(cal.actual_accuracy)}. Cross-fitted isotonic calibration takes expected calibration error from ${cal.ece_raw.toFixed(3)} to ${cal.ece_calibrated.toFixed(3)}, so thresholds mean what they say.`, 6500)

  // 5 · What it is worth
  await tab(page, 'worklist')
  await caption(page, '5 · The field worklist',
    'Given N visits, the N parcels with the most estimated corrections, against the same N visits at random.', 5000)
  const slider = page.locator('#budget')
  for (const v of ['1000', '2000', '500']) {
    await slider.fill(v)
    await page.waitForTimeout(1600)
  }
  await caption(page, '5 · Stated honestly',
    'Corrections are a model estimate. The targeting ratio is capped by construction, so the screen reports ranking quality instead.', 5500)
  await tab(page, 'autoclear')
  await caption(page, '5 · What never needs a visit',
    `${int(ac.parcels)} parcels (${ac.pct_of_parcels}%) can be auto-cleared: ${int(ac.surveyor_days_saved)} of ${int(ac.baseline_surveyor_days)} surveyor-days. The residual risk (${pct(ac.expected_residual_error_rate)}) is a rough proxy, not a bound, and we say so.`, 6500)

  // 6 · Found without being asked
  await tab(page, 'villages')
  await caption(page, '6 · The registry, read carefully',
    'The Agrisnet registry is the survey\'s own published aggregate, so this compares the survey with itself, not with an independent truth. Where it diverges is where to look.', 6500)

  // 7 · Ask it a question
  await tab(page, 'analyst')
  await caption(page, '7 · The analyst',
    'An LLM plans over the same typed tools the screens use. Every answer names its model, cites its sources and states its split regime.', 5000)
  await page.locator('button:has-text("Where should we send 500 surveyors next season?")').click()
  await expect(page.locator('text=Thinking…')).toHaveCount(0, { timeout: 300_000 })
  await page.waitForTimeout(800)
  await page.locator('.md').last().scrollIntoViewIfNeeded()
  await caption(page, '7 · A cited answer',
    'Numbers come only from tool results; the chip names the model (with automatic fallback when a free tier is busy).', 7000)

  await caption(page, 'Closing',
    `We report ${pct(H.accuracy)} (capture-event-grouped), not 95%. The honest number is lower, and the product is better for it.`, 6000)
})
