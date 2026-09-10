import { defineConfig } from "@playwright/test";
// Izolovaná lane pro WU-SOURCE-CREATION: vlastní port 8764 a datový kořen, mimo 8740/8750 a jejich data.
// Spouštět explicitně: npx playwright test -c playwright.source-creation.config.ts
export default defineConfig({
  testDir: "e2e-source-creation",
  workers: 1,
  use: { baseURL: "http://127.0.0.1:8764" },
  webServer: {
    command: "uv run uvicorn backend.app:create_app --factory --host 127.0.0.1 --port 8764",
    url: "http://127.0.0.1:8764/api/health",
    env: { OPORA_CANVAS_PORT: "8764", OPORA_CANVAS_DATA: ".data/e2e-source-creation-" + Date.now().toString(36) },
    reuseExistingServer: false,
    timeout: 60000,
  },
});
