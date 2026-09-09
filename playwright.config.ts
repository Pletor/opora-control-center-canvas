import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "e2e",
  workers: 1,
  use: { baseURL: "http://127.0.0.1:8740" },
  webServer: {
    command:
      "uv run python -m scripts.prepare_e2e && uv run uvicorn backend.app:create_app --factory --host 127.0.0.1 --port 8740",
    url: "http://127.0.0.1:8740/api/health",
    env: { OPORA_CANVAS_DATA: ".data/e2e-" + Date.now() },
    reuseExistingServer: false,
    timeout: 60000,
  },
});
