import { expect, test, type Page } from '@playwright/test'

/**
 * KAVAL end-to-end: the real UI against the real API. Every tab, three viewports,
 * with the things a reviewer would notice treated as failures — a console error,
 * a failed /api call, an error panel, a spinner that never resolves, or a page
 * wider than the screen. Screenshots go to docs/e2e/ for inspection.
 */

const TABS = ['map', 'villages', 'worklist', 'autoclear', 'validation', 'analyst'] as const
const SHOTS = '../docs/e2e'

const VIEWPORTS = {
  desktop: { width: 1440, height: 900, scheme: 'light' as const },
  phone: { width: 390, height: 844, scheme: 'light' as const },
  dark: { width: 1440, height: 900, scheme: 'dark' as const },
}

function watch(page: Page) {
  const problems: string[] = []
  page.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`))
  page.on('console', (m) => {
    if (m.type() === 'error') problems.push(`console: ${m.text()}`)
  })
  page.on('response', (r) => {
    if (r.url().includes('/api/') && r.status() >= 400)
      problems.push(`api ${r.status()}: ${r.url()}`)
  })
  return problems
}

async function settle(page: Page) {
  await page.waitForLoadState('networkidle')
  await expect(page.locator('.state:has-text("Loading")')).toHaveCount(0, { timeout: 60_000 })
}

for (const [vp, cfg] of Object.entries(VIEWPORTS)) {
  test.describe(`${vp}`, () => {
    test.use({ viewport: { width: cfg.width, height: cfg.height }, colorScheme: cfg.scheme })

    for (const tab of TABS) {
      test(`${tab} renders cleanly`, async ({ page }) => {
        const problems = watch(page)
        await page.goto(`/#${tab}`)
        await settle(page)
        await expect(page.locator(`nav.tabs button[aria-current="page"]`)).toBeVisible()
        await expect(page.locator('.state.error')).toHaveCount(0)
        // A stat tile showing a dash means the UI read a field the API no longer
        // sends. That once shipped silently on the worklist; now it fails here.
        const blank = await page.locator('.tile .value').evaluateAll((els) =>
          els.map((e) => e.textContent?.trim() ?? '').filter((t) => /^[—–-]$/.test(t) || t === ''),
        )
        expect(blank, 'stat tiles rendering a placeholder instead of a value').toEqual([])
        const overflow = await page.evaluate(
          () => document.documentElement.scrollWidth - window.innerWidth,
        )
        await page.screenshot({ path: `${SHOTS}/${vp}-${tab}.png`, fullPage: true })
        expect(overflow, 'page is wider than the viewport').toBeLessThanOrEqual(1)
        expect(problems).toEqual([])
      })
    }
  })
}

test.describe('flows', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  test('map draws parcels coloured by status and opens a DISPUTED parcel', async ({ page }) => {
    const problems = watch(page)
    // As a presenter does it: one village (polygons large enough to click), then a
    // real mouse click on a DISPUTED parcel. An earlier version force-clicked path
    // #10 on the taluk view, which hit a village outline, so the panel was never
    // actually verified.
    await page.goto('/#map?village=' + encodeURIComponent('Rayagiri - Part-2'))
    await settle(page)
    const disputed = page.locator('.leaflet-overlay-pane path[fill="var(--st-disputed)"]')
    await expect.poll(async () => disputed.count(), { timeout: 60_000 }).toBeGreaterThan(0)
    const box = (await disputed.first().boundingBox())!
    await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2)
    const close = page.locator('button.btn:has-text("Close")')
    await expect(close).toBeVisible()
    await expect(page.locator('body')).toContainText('DISPUTED')
    await page.screenshot({ path: `${SHOTS}/flow-map-parcel.png` })
    // The map's exports must carry the thresholds the map is drawn at.
    const href = await page.locator('a.btn:has-text("Export CSV")').first().getAttribute('href')
    expect(href).toContain('confidence_high=')
    expect(problems).toEqual([])
  })

  test('village audit crop-area card follows the village filter', async ({ page }) => {
    const problems = watch(page)
    await page.goto('/#villages')
    await settle(page)
    await expect(page.locator('h2:has-text("whole taluk")')).toBeVisible()
    const sel = page.locator('label:has-text("Village") select')
    const opt = await sel.locator('option').nth(1).textContent()
    await sel.selectOption({ index: 1 })
    await settle(page)
    await expect(page.locator(`h2:has-text("${opt}")`)).toBeVisible()
    expect(problems).toEqual([])
  })

  test('worklist slider re-routes and export reproduces the queue', async ({ page }) => {
    const problems = watch(page)
    await page.goto('/#worklist')
    await settle(page)
    const slider = page.locator('#budget')
    await slider.fill('120')
    await page.waitForTimeout(700)
    await settle(page)
    const rows = page.locator('table.data tbody tr')
    await expect.poll(async () => rows.count()).toBe(120)
    const href = await page.locator('a.btn.primary:has-text("Export CSV")').getAttribute('href')
    expect(href).toContain('budget=120')
    const csv = await (await page.request.get(href!)).text()
    expect(csv.trim().split('\n').length - 1).toBe(120)
    await page.screenshot({ path: `${SHOTS}/flow-worklist-120.png`, fullPage: true })
    expect(problems).toEqual([])
  })

  test('ladder shows the honest headline, Presto and the paired verdicts', async ({ page }) => {
    const problems = watch(page)
    await page.goto('/#validation')
    await settle(page)
    const body = page.locator('body')
    await expect(body).toContainText('Presto')
    await expect(body).toContainText('underpowered')
    await expect(body).not.toContainText(/9[5-9](\.\d)?% accuracy/)
    expect(problems).toEqual([])
  })

  test('analyst answers a starter question with a labelled planner and citations', async ({ page }) => {
    test.setTimeout(900_000) // a local CPU model can take minutes
    const problems = watch(page)
    await page.goto('/#analyst')
    await settle(page)
    await page.locator('button:has-text("Which parcels can we stop visiting?")').click()
    await expect(page.locator('text=Thinking…')).toHaveCount(0, { timeout: 880_000 })
    const body = page.locator('body')
    await expect(body).toContainText(/offline planner|LLM/)
    await expect(page.locator('.cites .chip').first()).toBeVisible()
    await page.screenshot({ path: `${SHOTS}/flow-analyst.png`, fullPage: true })
    expect(problems).toEqual([])
  })
})
