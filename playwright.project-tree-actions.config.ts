import { defineConfig } from '@playwright/test';
const temp = (process.env.LOCALAPPDATA || 'C:/Users/Admin/AppData/Local') + '/Temp/';
const stamp = Date.now().toString(36);
process.env.OPORA_TEST_DIST = '.data/clean-editor-dist';
// Zúžený harness pro V3-PRJ-003..015 / V3-KEY-004; stejná izolovaná fixture jako playwright.clean-editor.config.ts,
// ale spouští jen e2e/project-tree-actions.spec.ts na vyhrazeném portu 8742.
export default defineConfig({
  workers: 1,
  projects: [
    { name: 'legacy', testDir: 'e2e', testMatch: ['project-tree-actions.spec.ts'], use: { baseURL: 'http://127.0.0.1:8742' } },
  ],
  webServer: [8742].map(port => ({
    command: 'uv run python -m scripts.prepare_e2e && uv run uvicorn scripts.serve_clean_editor_fixture:create_fixture --factory --host 127.0.0.1 --port ' + port,
    url: `http://127.0.0.1:${port}/api/health`,
    env: { OPORA_CANVAS_PORT: String(port), OPORA_CANVAS_DATA: temp + `opora-clean-${port}-${stamp}` },
    reuseExistingServer: false,
    timeout: 60000,
  })),
});
