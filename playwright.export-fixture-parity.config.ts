import { defineConfig } from "@playwright/test";

// Izolovaná konfigurace pro export-fixture-parity lane: vlastní port 8793 (stejný jako
// export-scope lane, ale nikdy spuštěná souběžně — workers:1 a exkluzivní worktree tuto lane vlastní).
// Znovu používá harness i fixture z e2e-v3-panels; port přepisuje přes CLI Vite jako export-scope.config.ts.
export default defineConfig({
  testDir: "e2e-v3-panels",
  testMatch: /(export-fixture-parity|export-scope|agent-packet|live-workspace)\.spec\.ts$/,
  workers: 1,
  use: { baseURL: "http://127.0.0.1:8793" },
  webServer: {
    command: "npx vite --config vite.desktop-v3.config.ts --port 8793 --strictPort",
    url: "http://127.0.0.1:8793/",
    reuseExistingServer: false,
    timeout: 60000,
  },
});
