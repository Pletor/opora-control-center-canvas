// Vlastní Vite konfigurace pro WU-DESKTOP-V3 workflow-drafts lane (Sonnet).
// Znovupoužívá sdílený harness a fixturePlugin z e2e-v3-panels beze změny; pouze vlastní port
// 8794, aby neinterferovala s ostatními souběžnými lanami (8782 aj. jsou rezervované jinde).
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fixturePlugin } from "./e2e-v3-panels/fixture-plugin";

export default defineConfig({
  root: "e2e-v3-panels",
  plugins: [react(), fixturePlugin()],
  server: { host: "127.0.0.1", port: 8794, strictPort: true },
});
