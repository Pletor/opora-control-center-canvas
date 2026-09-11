import { defineConfig } from '@playwright/test';
const temp = (process.env.LOCALAPPDATA || 'C:/Users/Admin/AppData/Local') + '/Temp/';
const stamp = Date.now().toString(36);
const port = 8795;
process.env.OPORA_TEST_DIST = '.data/clean-editor-dist';
// Vlastní izolovaný port a dočasná data pro inspector-style-boundary; nesdílí legacy 8742.
export default defineConfig({
  workers: 1,
  testDir: 'e2e',
  // Jen vlastní spec; predecessor drawing.spec.ts má natvrdo 8742, stav předchůdce se reprodukuje přes OPORA_INSPECTOR_SEED=1.
  testMatch: 'inspector-style-boundary.spec.ts',
  use: { baseURL: `http://127.0.0.1:${port}` },
  webServer: {
    command: 'uv run python -m scripts.prepare_e2e && uv run uvicorn scripts.serve_clean_editor_fixture:create_fixture --factory --host 127.0.0.1 --port ' + port,
    url: `http://127.0.0.1:${port}/api/health`,
    env: { OPORA_CANVAS_PORT: String(port), OPORA_CANVAS_DATA: temp + `opora-inspector-suite-${port}-${stamp}` },
    reuseExistingServer: false,
    timeout: 60000,
  },
});
