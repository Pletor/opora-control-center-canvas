import base from "./playwright.config";
import { defineConfig } from "@playwright/test";
export default defineConfig({
  ...base,
  use: { ...base.use, baseURL: "http://127.0.0.1:8742" },
  webServer: {
    ...(base.webServer as object),
    command: "uv run python -m scripts.prepare_e2e && uv run uvicorn backend.app:create_app --factory --host 127.0.0.1 --port 8742",
    url: "http://127.0.0.1:8742/api/health",
    env: { OPORA_CANVAS_PORT: "8742", OPORA_CANVAS_DATA: (process.env.LOCALAPPDATA || "C:/Users/Admin/AppData/Local") + "/Temp/opora-map-regression-" + Date.now().toString(36) },
    reuseExistingServer: false,
  },
});
