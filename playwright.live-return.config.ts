import { defineConfig } from "@playwright/test";
// Izolace této lane: port 8742 je vyhrazen výhradně této worktree po dobu ladění
// (viz clean-editor config); vlastní datový kořen, žádná jiná lane se nedotýká.
// Fixture server servíruje soukromý build .data/clean-editor-dist (ne chybějící dist/).
process.env.OPORA_TEST_DIST = ".data/clean-editor-dist";
export default defineConfig({
  testDir: "e2e",
  testMatch: /live-view-return\.spec\.ts$/,
  workers: 1,
  use: { baseURL: "http://127.0.0.1:8742" },
  webServer: {
    command:
      "uv run python -m scripts.prepare_e2e && uv run uvicorn scripts.serve_clean_editor_fixture:create_fixture --factory --host 127.0.0.1 --port 8742",
    url: "http://127.0.0.1:8742/api/health",
    env: { OPORA_CANVAS_PORT: "8742", OPORA_CANVAS_DATA: ".data/e2e-live-return-" + Date.now().toString(36) },
    reuseExistingServer: false,
    timeout: 60000,
  },
});
