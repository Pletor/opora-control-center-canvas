import { defineConfig } from "@playwright/test";

// Izolovaná konfigurace pro export-scope lane: vlastní port 8793 (8782 patří jiné lane).
// Znovu používá harness i fixture z e2e-v3-panels, port přepisuje přes CLI Vite.
export default defineConfig({
  testDir: "e2e-v3-panels",
  // EXPORT_SCOPE_REGRESSION=1 spustí i sousední panelové specy na stejném izolovaném portu.
  testMatch: process.env.EXPORT_SCOPE_REGRESSION ? /(export-scope|agent-packet|live-workspace)\.spec\.ts$/ : /export-scope\.spec\.ts$/,
  workers: 1,
  use: { baseURL: "http://127.0.0.1:8793" },
  webServer: {
    command: "npx vite --config vite.desktop-v3.config.ts --port 8793 --strictPort",
    url: "http://127.0.0.1:8793/",
    reuseExistingServer: false,
    timeout: 60000,
  },
});
