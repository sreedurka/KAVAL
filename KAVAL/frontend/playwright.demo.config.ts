import { defineConfig } from '@playwright/test'

// Records the demo walkthrough (docs/DEMO_WALKTHROUGH.md) as a video through the
// real UI and API. Separate from the test suite: `npx playwright test -c playwright.demo.config.ts`.
export default defineConfig({
  testDir: './e2e-demo',
  timeout: 600_000,
  outputDir: '../docs/demo/raw',
  reporter: [['list']],
  use: {
    baseURL: process.env.KAVAL_UI ?? 'http://127.0.0.1:5173',
    viewport: { width: 1440, height: 900 },
    video: { mode: 'on', size: { width: 1440, height: 900 } },
    colorScheme: 'light',
  },
})
