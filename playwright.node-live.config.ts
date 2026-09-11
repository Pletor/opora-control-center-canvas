import {defineConfig} from '@playwright/test';
export default defineConfig({
  testDir:'e2e', testMatch:/node-live-sessions\.spec\.ts$/, workers:1,
  use:{baseURL:'http://127.0.0.1:8782',viewport:{width:1440,height:1000}},
  webServer:{
    command:'uv run python -m uvicorn backend.app:create_app --factory --host 127.0.0.1 --port 8782',
    url:'http://127.0.0.1:8782/api/health',reuseExistingServer:false,
    env:{OPORA_CANVAS_PORT:'8782',OPORA_CANVAS_DATA:'.data/e2e-node-live-'+Date.now().toString(36),OPORA_HERMES_API_KEY:''},
  },
});
