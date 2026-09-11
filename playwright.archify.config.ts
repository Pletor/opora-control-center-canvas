import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'e2e',testMatch:/archify-map\.spec\.ts$/,workers:1,
  use:{baseURL:'http://127.0.0.1:8783',viewport:{width:1600,height:1000}},
  webServer:{command:'uv run python -m uvicorn backend.app:create_app --factory --host 127.0.0.1 --port 8783',url:'http://127.0.0.1:8783/api/health',reuseExistingServer:false,
    env:{OPORA_CANVAS_PORT:'8783',OPORA_CANVAS_DATA:'.data/e2e-archify-'+Date.now().toString(36),OPORA_HERMES_API_KEY:''}},
});
