import React from "react";
import { createRoot } from "react-dom/client";
import "@xyflow/react/dist/style.css";
import "@/app/styles/style.css";
import App from "@/app/components/App";
import AccessGate from "@/app/access-gate/components/AccessGate";
(window as Window & { EXCALIDRAW_ASSET_PATH?: string }).EXCALIDRAW_ASSET_PATH =
  "/drawing-assets/";
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AccessGate>
      <App />
    </AccessGate>
  </React.StrictMode>,
);
