import { defineConfig } from '@playwright/test';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

// End-to-end tests drive the real engine with the small Python fixture pack
// (ipykernel), so they run anywhere Python is available, without R.
const port = 8765;
const dataDir = mkdtempSync(join(tmpdir(), 'curelab-e2e-'));
const python = process.env.CURELAB_PYTHON ?? 'python3';

export default defineConfig({
  testDir: 'e2e',
  timeout: 120_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  outputDir: 'test-results',
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    viewport: { width: 1440, height: 900 },
    launchOptions: process.env.PW_CHROMIUM_PATH ? { executablePath: process.env.PW_CHROMIUM_PATH } : {},
  },
  webServer: {
    command:
      `${python} -m curelab --pack ../engine/tests/fixtures/pack_py --illnesses ../illnesses ` +
      `--data ${dataDir} --web dist --port ${port}`,
    url: `http://127.0.0.1:${port}/api/health`,
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
