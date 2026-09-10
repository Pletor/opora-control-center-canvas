import { defineConfig } from '@playwright/test';
const temp = (process.env.LOCALAPPDATA || 'C:/Users/Admin/AppData/Local') + '/Temp/';
const stamp = Date.now().toString(36);
process.env.OPORA_TEST_DIST = '.data/clean-editor-dist';
// Původní sady mají bezpečnostně pevné porty a vlastní Git fixture; neměníme jejich testy.
export default defineConfig({
  workers: 1,
  projects: [
    { name: 'legacy', testDir: 'e2e', use: { baseURL: 'http://127.0.0.1:8742' } },
    { name: 'document', testDir: 'e2e-document-task', use: { baseURL: 'http://127.0.0.1:8769' } },
    { name: 'clean-source', testDir: '.', testMatch: ['e2e-clean-editor/*.spec.ts', 'e2e-source-creation/*.spec.ts'], use: { baseURL: 'http://127.0.0.1:8771' } },
  ],
  webServer: [8742,8769,8771].map(port => ({
    command: (port === 8771 ? '' : 'uv run python -m scripts.prepare_e2e && ') + 'uv run uvicorn scripts.serve_clean_editor_fixture:create_fixture --factory --host 127.0.0.1 --port ' + port,
    url: `http://127.0.0.1:${port}/api/health`,
    env: { OPORA_CANVAS_PORT: String(port), OPORA_CANVAS_DATA: temp + `opora-clean-${port}-${stamp}` },
    reuseExistingServer: false,
    timeout: 60000,
  })),
});
