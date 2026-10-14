import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './tests', testMatch: ['online-explorer.spec.ts', 'visual-map.spec.ts', 'github-import.spec.ts'],
  fullyParallel: false, workers: 1, timeout: 30000, expect: { timeout: 10000 }, reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:5174', channel: 'chrome', screenshot: 'only-on-failure', trace: 'retain-on-failure' },
  projects: [
    { name: 'desktop', use: { viewport: { width: 1600, height: 1100 } } },
    { name: 'narrow', use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  webServer: [
    { command: '../server/.venv/bin/python ../server/tests/serve_explorer_e2e.py', url: 'http://127.0.0.1:8001/api/health', reuseExistingServer: false },
    { command: 'npm run dev -- --port 5174', env: { REPOLENS_API_PROXY: 'http://127.0.0.1:8001' }, url: 'http://127.0.0.1:5174', reuseExistingServer: false },
  ],
})
