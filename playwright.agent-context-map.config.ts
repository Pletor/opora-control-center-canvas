import { defineConfig } from "@playwright/test";

// Isolated lane for the context-map slice: its own server, port, and data root.
export default defineConfig({
  testDir: "e2e",
  testMatch: "agent-context-map.spec.ts",
  workers: 1,
  use: { baseURL: "http://127.0.0.1:8762" },
  webServer: {
    command: "uv run python -m scripts.prepare_e2e && uv run uvicorn backend.app:create_app --factory --host 127.0.0.1 --port 8762",
    url: "http://127.0.0.1:8762/api/health",
    env: { OPORA_CANVAS_PORT: "8762", OPORA_CANVAS_DATA: ".data/a-" + Date.now().toString(36) },
    reuseExistingServer: false,
    timeout: 60000,
  },
});
