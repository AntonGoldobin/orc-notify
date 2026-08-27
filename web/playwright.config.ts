import { defineConfig, devices } from '@playwright/test'

const PORT = 5173
const BASE_URL = `http://localhost:${PORT}`
const API_BASE = process.env.E2E_API_BASE ?? 'http://localhost:8000'

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  retries: 0,
  fullyParallel: false,
  workers: 1,
  reporter: process.env.CI ? 'dot' : 'list',
  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  // The FastAPI backend must be running on $API_BASE for these tests to pass.
  // Easiest: `cd ../ && source .venv/bin/activate && uvicorn app.main:app --port 8000`
  // in one terminal, then `pnpm e2e` in another.
  webServer: {
    command: 'pnpm dev',
    url: BASE_URL,
    timeout: 60_000,
    reuseExistingServer: true,
    env: { VITE_API_BASE: API_BASE },
    stdout: 'pipe',
    stderr: 'pipe',
  },
})
