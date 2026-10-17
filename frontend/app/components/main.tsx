import React from "react";
import { createRoot } from "react-dom/client";
import "@xyflow/react/dist/style.css";
import "@/app/styles/style.css";
import App from "@/app/components/App";
import AccessGate from "@/app/access-gate/components/AccessGate";
import { ProjectMemoryPanel, NodeWorkflowPanel, AgentPacketPanel } from "@/app/logic/desktop-panels";
import { installEmbedEscape } from "@/app/logic/embed-escape";
(window as Window & { EXCALIDRAW_ASSET_PATH?: string }).EXCALIDRAW_ASSET_PATH =
  "/drawing-assets/";
// Vložená v <iframe> (opora.toml [app] embed_origins) předá neobsloužený Escape rodiči.
installEmbedEscape(window, document.referrer);
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AccessGate>
      <App v3={{
        projectMemory: (scope) => <ProjectMemoryPanel key={JSON.stringify([scope.project, scope.workspace])} {...scope} />,
        nodeWorkflow: (scope) => <NodeWorkflowPanel key={JSON.stringify([scope.project, scope.workspace, scope.nodeId])} {...scope} />,
        agentPacket: (scope) => <AgentPacketPanel {...scope} />,
      }} />
    </AccessGate>
  </React.StrictMode>,
);
