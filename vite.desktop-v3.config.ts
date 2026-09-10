// Vlastní Vite konfigurace pro izolovaný testovací harness Desktop v3 panelů (Sonnet lane).
// Neupravuje sdílený vite.config.ts. Slouží jen e2e-v3-panels/.
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fixturePlugin } from "./e2e-v3-panels/fixture-plugin";

export default defineConfig({
  root: "e2e-v3-panels",
  plugins: [react(), fixturePlugin()],
  server: { host: "127.0.0.1", port: 8782, strictPort: true },
});
