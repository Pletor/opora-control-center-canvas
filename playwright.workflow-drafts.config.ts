import { defineConfig } from "@playwright/test";

// WU-DESKTOP-V3 workflow-drafts lane (Sonnet): isolated port 8794, own test file, own Vite
// config. Does not touch the shared playwright.desktop-v3.config.ts (port 8782, reserved by
// another concurrent lane) or its fixture/harness.
export default defineConfig({
  testDir: "e2e-v3-panels",
  testMatch: /workflow-draft-preservation\.spec\.ts$/,
  workers: 1,
  use: { baseURL: "http://127.0.0.1:8794" },
  webServer: {
    command: "npx vite --config vite.workflow-drafts.config.ts",
    url: "http://127.0.0.1:8794/",
    reuseExistingServer: false,
    timeout: 60000,
  },
});
