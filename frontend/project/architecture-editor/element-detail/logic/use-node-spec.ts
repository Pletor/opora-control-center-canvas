// Pracovní zadání uzlu jen pro čtení: stejné `GET /api/node-spec`, které čte záložka Zadání v Editoru.
// Detail prvku zadání nikdy nezapisuje (docs/architektura-projektu.md, Pravidla).
import { useEffect, useState } from "react";
import { api, type NodeSpec } from "@/shared/types/logic/types";

export type SpecState = { status: "loading" } | { status: "ready"; spec: NodeSpec } | { status: "error"; message: string };

export function useNodeSpec(project: string, workspace: string, nodeId: string): SpecState {
  const [state, setState] = useState<SpecState>({ status: "loading" });
  useEffect(() => {
    let live = true;
    setState({ status: "loading" });
    api<NodeSpec>("/api/node-spec?" + new URLSearchParams({ project, workspace, node: nodeId }))
      .then((spec) => live && setState({ status: "ready", spec }))
      .catch((error: unknown) => live && setState({ status: "error", message: error instanceof Error ? error.message : String(error) }));
    return () => {
      live = false;
    };
  }, [project, workspace, nodeId]);
  return state;
}
