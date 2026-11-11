// Kontext prvku pro plátno toku v projektu: jen u plátna `opora:project-flow:<nodeId>` tohoto projektu se načte
// graf prostoru (`/api/view`) a najde prvek. Chyba čtení nebo jiný uzel = žádný kontext, hlavička zůstane obecná.
import { useEffect, useState } from "react";
import { api, type View } from "@/shared/types/logic/types";
import { flowNodeOf } from "@/project/project-flows/logic/project-flows";
import { elementContext, type ElementContext } from "./element-context";

export function useElementContext(flow: { ownerRef: string; projectId: string | null } | null, project: string, workspace: string): ElementContext | null {
  const nodeId = flow?.projectId === project ? flowNodeOf(flow.ownerRef) : null;
  const [context, setContext] = useState<ElementContext | null>(null);
  useEffect(() => {
    setContext(null);
    if (!nodeId) return;
    let alive = true;
    api<View>(`/api/view?${new URLSearchParams({ project, workspace })}`)
      .then((view) => { if (alive) setContext(elementContext(view.graph, nodeId)); }, () => {});
    return () => { alive = false; };
  }, [nodeId, project, workspace]);
  return context;
}
