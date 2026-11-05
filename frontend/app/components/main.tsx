import React from "react";
import { createRoot } from "react-dom/client";
import "@xyflow/react/dist/style.css";
import "@/app/styles/style.css";
import Entry from "@/app/intro/components/Entry";
import AccessGate from "@/app/access-gate/components/AccessGate";
import { installEmbedEscape } from "@/app/logic/embed-escape";
(window as Window & { EXCALIDRAW_ASSET_PATH?: string }).EXCALIDRAW_ASSET_PATH =
  "/drawing-assets/";
// Vložená v <iframe> (opora.toml [app] embed_origins) předá neobsloužený Escape rodiči.
installEmbedEscape(window, document.referrer);
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AccessGate>
      <Entry />
    </AccessGate>
  </React.StrictMode>,
);
