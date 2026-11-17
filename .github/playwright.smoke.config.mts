import { fileURLToPath } from 'node:url';
import { defineConfig } from '../src/apps/web/node_modules/@playwright/test/index.mjs';
import base from '../tests/browser/playwright.config';

// Exact filenames keep historical-reader/live-instance tests out of this gate.
// Existing application tests mock all API requests; Vite's proxy is also disabled.
const files = [
  'navigation', 'i18n', 'mobile-navigation', 'workflow-preferences',
  'provider-settings', 'translation-preparation', 'resource-settings',
];
const root = fileURLToPath(new URL('../', import.meta.url));
const url = 'http://127.0.0.1:5181';

export default defineConfig(base, {
  testDir: '../tests/browser',
  testMatch: new RegExp(`(?:^|[/\\\\])(?:${files.join('|')})\\.spec\\.ts$`),
  forbidOnly: true,
  retries: 0,
  workers: 1,
  use: { ...base.use, baseURL: url },
  webServer: {
    command: 'node src/apps/web/node_modules/vite/bin/vite.js src/apps/web --config .github/vite.smoke.config.mts --host 127.0.0.1 --port 5181 --strictPort',
    cwd: root,
    url,
    reuseExistingServer: false,
    timeout: 60_000,
    stdout: 'pipe',
    stderr: 'pipe',
  },
});
