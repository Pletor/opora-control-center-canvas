import React from "react";
import { createRoot } from "react-dom/client";
import "@xyflow/react/dist/style.css";
import "@/app/styles/style.css";
import App from "@/app/components/App";
import AccessGate from "@/app/access-gate/components/AccessGate";
import { ProjectMemoryPanel, NodeWorkflowPanel, AgentPacketPanel, LiveWorkspacePanel } from "@/app/logic/desktop-panels";
(window as Window & { EXCALIDRAW_ASSET_PATH?: string }).EXCALIDRAW_ASSET_PATH =
  "/drawing-assets/";
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AccessGate>
      <App v3={{
        projectMemory: (scope) => <ProjectMemoryPanel key={JSON.stringify([scope.project, scope.workspace])} {...scope} />,
        nodeWorkflow: (scope) => <NodeWorkflowPanel key={JSON.stringify([scope.project, scope.workspace, scope.nodeId])} {...scope} />,
        agentPacket: (scope) => <AgentPacketPanel {...scope} />,
        liveWorkspace: (scope) => <LiveWorkspacePanel key={JSON.stringify([scope.project, scope.workspace])} {...scope} />,
      }} />
    </AccessGate>
  </React.StrictMode>,
);
