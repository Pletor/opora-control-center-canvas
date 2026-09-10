import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: 'e2e-document-task', workers: 1,
  use: { baseURL: 'http://127.0.0.1:8769' },
  webServer: {
    command: 'uv run python -m scripts.prepare_e2e && uv run uvicorn backend.app:create_app --factory --host 127.0.0.1 --port 8769',
    url: 'http://127.0.0.1:8769/api/health',
    env: { OPORA_CANVAS_PORT: '8769', OPORA_CANVAS_DATA: '.data/task-ui-' + Date.now().toString(36) },
    reuseExistingServer: false, timeout: 60000,
  },
});
