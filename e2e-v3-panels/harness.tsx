import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ProjectMemoryPanel,
  NodeWorkflowPanel,
  AgentPacketPanel,
  LiveWorkspacePanel,
} from "../src/desktop-v3/index";

const params = new URLSearchParams(window.location.search);
const panel = params.get("panel") || "";
const project = params.get("project") || "";
const workspace = params.get("workspace") || "";

// Scope fields (nodeId/path/note/references/sessionId) can additionally be driven by the URL
// hash so tests can change them WITHOUT a full page navigation/remount — the only way to
// exercise "same mounted component, scope changes via props (A→B→A)" instead of the unrelated
// unmount-driven scope switch that page.goto already covers.
function readScope() {
  const hash = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  const get = (key: string) => hash.get(key) ?? params.get(key) ?? "";
  let references: string[] = [];
  try {
    references = JSON.parse(get("references") || "[]");
  } catch {
    references = [];
  }
  return { nodeId: get("nodeId"), path: get("path"), note: get("note"), sessionId: get("sessionId"), references };
}

function Harness() {
  const [scope, setScope] = useState(readScope());
  useEffect(() => {
    const onHashChange = () => setScope(readScope());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  if (panel === "memory") return <ProjectMemoryPanel project={project} workspace={workspace} path={scope.path} />;
  if (panel === "workflow")
    return <NodeWorkflowPanel project={project} workspace={workspace} nodeId={scope.nodeId} />;
  if (panel === "packet")
    return (
      <AgentPacketPanel
        project={project}
        workspace={workspace}
        nodeId={scope.nodeId}
        path={scope.path}
        references={scope.references}
        note={scope.note}
        sessionId={scope.sessionId}
      />
    );
  if (panel === "live")
    return <LiveWorkspacePanel project={project} workspace={workspace} nodeId={scope.nodeId || undefined} />;
  return <p>Neznámý panel. Použijte ?panel=memory|workflow|packet|live</p>;
}

const root = createRoot(document.getElementById("root")!);
root.render(<Harness />);
