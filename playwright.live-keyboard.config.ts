import { defineConfig } from "@playwright/test";

// Izolovaná konfigurace pro live-keyboard lane: vlastní port 8796, nikdy sdílený
// s jinou souběžně běžící lane. Znovu používá harness i fixture z e2e-v3-panels;
// spouští existující vite.desktop-v3.config.ts jen s přepisem portu přes CLI.
export default defineConfig({
  testDir: "e2e-v3-panels",
  testMatch: /live-keyboard\.spec\.ts$/,
  workers: 1,
  use: { baseURL: "http://127.0.0.1:8796" },
  webServer: {
    command: "npx vite --config vite.desktop-v3.config.ts --port 8796 --strictPort",
    url: "http://127.0.0.1:8796/",
    reuseExistingServer: false,
    timeout: 60000,
  },
});
