import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "e2e-context-boundary",
  workers: 1,
  use: { baseURL: "http://127.0.0.1:8766" },
  webServer: {
    command: "uv run python -m scripts.prepare_e2e && uv run uvicorn backend.app:create_app --factory --host 127.0.0.1 --port 8766",
    url: "http://127.0.0.1:8766/api/health",
    env: { OPORA_CANVAS_PORT: "8766", OPORA_CANVAS_DATA: (process.env.LOCALAPPDATA || "C:/Users/Admin/AppData/Local") + "/Temp/opora-map-boundary-" + Date.now().toString(36) },
    reuseExistingServer: false,
    timeout: 60000,
  },
});
