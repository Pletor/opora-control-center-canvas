/// <reference types="vitest/config" />
import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  resolve: { alias: {
    "@": fileURLToPath(new URL("./frontend", import.meta.url)),
    // PR Lens renderer importuje node:crypto jen pro hash manifestu; prohlížeč volá jen render() (frontend/hub/review-lens/README.md).
    ...(process.env.VITEST ? {} : { "node:crypto": fileURLToPath(new URL("./frontend/hub/review-lens/logic/node-crypto-shim.ts", import.meta.url)) }),
  } },
  server: { proxy: { "/api": {
    target: "http://127.0.0.1:8740",
    changeOrigin: true,
    // Backend chce Origin rovný Hostu (factory.py boundary); přepíše se jen Origin samotného dev serveru, cizí stránka dál narazí.
    configure: (proxy) => proxy.on("proxyReq", (proxyReq, req) => {
      if (req.headers.origin === `http://${req.headers.host}`) proxyReq.setHeader("origin", "http://127.0.0.1:8740");
    }),
  } } },
  build: { outDir: "dist", manifest: true },
  // Testy logiky leží vedle modulu jako <name>.test.ts; běží bez DOM.
  test: { include: ["frontend/**/*.test.ts"], environment: "node" },
});
