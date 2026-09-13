import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": fileURLToPath(new URL("./frontend", import.meta.url)) } },
  server: { proxy: { "/api": "http://127.0.0.1:8740" } },
  build: { outDir: "dist", manifest: true },
});
