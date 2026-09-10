import { defineConfig } from '@playwright/test';
const temp = (process.env.LOCALAPPDATA || 'C:/Users/Admin/AppData/Local') + '/Temp/';
const stamp = Date.now().toString(36);
// OPUS lane: vlastní build (.data/v3-shell-dist), vlastní port 8783, dočasná data; živé servery se nepoužívají.
// Build: npx vite build --outDir .data/v3-shell-dist && node scripts/copy-drawing-assets.mjs .data/v3-shell-dist
export default defineConfig({
  workers: 1,
  timeout: 60000,
  projects: [
    { name: 'v3-shell', testDir: 'e2e-v3-shell', use: { baseURL: 'http://127.0.0.1:8783' } },
    { name: 'clean-regression', testDir: 'e2e-clean-editor', use: { baseURL: 'http://127.0.0.1:8783' } },
  ],
  webServer: {
    command: 'uv run uvicorn scripts.serve_v3_shell_fixture:create_fixture --factory --host 127.0.0.1 --port 8783',
    url: 'http://127.0.0.1:8783/api/health',
    env: { OPORA_CANVAS_PORT: '8783', OPORA_CANVAS_DATA: temp + `opora-v3-shell-${stamp}` },
    reuseExistingServer: false,
    timeout: 60000,
  },
});
