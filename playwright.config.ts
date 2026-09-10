import { defineConfig } from "@playwright/test";
// Izolace této design lane: port 8742 a vlastní datový kořen; produkce 8740 ani jiné lane se nedotýká.
export default defineConfig({
  testDir: "e2e",
  workers: 1,
  use: { baseURL: "http://127.0.0.1:8742" },
  webServer: {
    command:
      "uv run python -m scripts.prepare_e2e && uv run uvicorn backend.app:create_app --factory --host 127.0.0.1 --port 8742",
    url: "http://127.0.0.1:8742/api/health",
    // Krátký unikát: hluboká cesta worktree + fixture worktrees naráží na limit délky cesty Gitu na Windows.
    env: { OPORA_CANVAS_PORT: "8742", OPORA_CANVAS_DATA: ".data/e2e-design-" + Date.now().toString(36) },
    reuseExistingServer: false,
    timeout: 60000,
  },
});
