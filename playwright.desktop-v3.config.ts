import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "e2e-v3-panels",
  workers: 1,
  use: { baseURL: "http://127.0.0.1:8782" },
  webServer: {
    command: "npx vite --config vite.desktop-v3.config.ts",
    url: "http://127.0.0.1:8782/",
    reuseExistingServer: false,
    timeout: 60000,
  },
});
