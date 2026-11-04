// Plátna toku převzatá do projektu (kontrakt knihovny §1, rozhodnutí člověka: vidět u domény i u stránky). Kopie je
// workflow `library_flow` s `project_id` projektu a `owner_ref = opora:project-flow:<nodeId|slug>`; patří uzlu,
// jehož id je v `owner_ref` (doména nebo stránka). Řádek odkazu nese název, „vychází z <prvek>@<verze>“ a upozornění
// na novější verzi v knihovně (`library-canvas/logic/lineage.ts`).
import type { FlowWorkflow } from "@/shared/flow-editor/logic/flow-types";
import type { LibraryFlowDetail } from "@/project/library-canvas/logic/library-api";
import { lineageOf } from "@/project/library-canvas/logic/lineage";

export type ProjectFlow = { id: string; name: string; from: string | null; newer: string | null };
const PREFIX = "opora:project-flow:";

/** Kopie projektu podle uzlu (seznam `/api/flow/workflows?project=` vrací i plátna knihovny bez projektu). */
export function copiesByNode(workflows: readonly FlowWorkflow[], project: string): Map<string, FlowWorkflow[]> {
  const byNode = new Map<string, FlowWorkflow[]>();
  for (const flow of workflows) {
    if (flow.kind !== "library_flow" || flow.project_id !== project || !flow.owner_ref?.startsWith(PREFIX)) continue;
    const node = flow.owner_ref.slice(PREFIX.length);
    byNode.set(node, [...(byNode.get(node) ?? []), flow]);
  }
  return byNode;
}

export function projectFlow(copy: Pick<LibraryFlowDetail, "id" | "title" | "derivedFrom">, source: LibraryFlowDetail | null): ProjectFlow {
  const { from, newer } = lineageOf(copy, source);
  return { id: copy.id, name: copy.title, from, newer };
}
