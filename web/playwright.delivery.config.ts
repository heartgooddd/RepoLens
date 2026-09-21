import {defineConfig} from '@playwright/test'

// Opt-in against the already-started .command delivery. No mock backend and no paid calls.
export default defineConfig({
  testDir: './delivery-tests', workers: 1, timeout: 30000,
  reporter: 'list', use: {baseURL: 'http://127.0.0.1:8000', channel: 'chrome', viewport: {width:1440,height:1000}},
})
