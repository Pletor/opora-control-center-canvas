// Převzatá plátna projektu pro odkazy u domény a stránky: seznam workflow projektu, detail každé kopie a detail jejího
// zdroje (jednou pro každý zdroj). Čte se při otevření a po změně grafu architektury (`digest`); chyba čtení = žádné
// odkazy, editor architektury pracuje dál.
import { useEffect, useState } from "react";
import type { FlowWorkflow } from "@/shared/flow-editor/logic/flow-types";
import { api } from "@/shared/types/logic/types";
import { libraryUrls, loadFlow, type LibraryFlowDetail } from "@/project/library-canvas/logic/library-api";
import { copiesByNode, projectFlow, type ProjectFlow } from "./project-flows";

export function useProjectFlows(project: string, digest: string | undefined): ReadonlyMap<string, ProjectFlow[]> {
  const [flows, setFlows] = useState<ReadonlyMap<string, ProjectFlow[]>>(new Map());
  useEffect(() => {
    let alive = true;
    api<{ workflows?: FlowWorkflow[] }>(libraryUrls.projectFlows(project)).then(async (raw) => {
      const sources = new Map<string, Promise<LibraryFlowDetail | null>>();
      const source = (id: string) => { if (!sources.has(id)) sources.set(id, loadFlow(id).catch(() => null)); return sources.get(id)!; };
      const entries = await Promise.all([...copiesByNode(raw.workflows ?? [], project)].map(async ([node, copies]) => [node, await Promise.all(copies.map(async (copy) => {
        const detail = await loadFlow(copy.id);
        return projectFlow(detail, detail.derivedFrom ? await source(detail.derivedFrom.workflowId) : null);
      }))] as const));
      if (alive) setFlows(new Map(entries));
    }).catch(() => { if (alive) setFlows(new Map()); });
    return () => { alive = false; };
  }, [project, digest]);
  return flows;
}
