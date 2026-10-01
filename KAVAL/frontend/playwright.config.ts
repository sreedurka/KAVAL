import { defineConfig } from '@playwright/test'

// Drives the real product: Vite dev server on 5173, proxying /api to the FastAPI
// backend on 8077. Start both first (see README), or let `webServer` start Vite.
export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,
  expect: { timeout: 30_000 },
  outputDir: '../docs/e2e/test-results',
  reporter: [['list'], ['json', { outputFile: '../docs/e2e/results.json' }]],
  use: { baseURL: process.env.KAVAL_UI ?? 'http://127.0.0.1:5173', trace: 'off' },
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1',
    url: 'http://127.0.0.1:5173',
    reuseExistingServer: true,
    timeout: 60_000,
  },
})
