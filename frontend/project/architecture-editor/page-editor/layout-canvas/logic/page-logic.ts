// Vrstva 2 plátna 2: prvky logiky stránky rozdělené podle boxů layoutu (`card.section`). Prvek bez sekce nebo se
// sekcí, která na stránce už není, patří celé stránce, aby zůstal vidět. Starší sektory a komponenty bez `element`
// se jen spočítají (žijí v Editoru). Bez Reactu, test vedle.
import type { CanvasNode, Graph } from "@/shared/types/logic/types";
import { pageElements } from "../../logic/plan-progress";

export type PageLogic = { whole: CanvasNode[]; byBox: Map<string, CanvasNode[]>; legacy: number };

export function pageLogic(graph: Graph, pageId: string, boxIds: ReadonlySet<string>): PageLogic {
  const whole: CanvasNode[] = [];
  const byBox = new Map<string, CanvasNode[]>();
  for (const node of pageElements(graph, pageId)) {
    const section = node.card?.section;
    if (section && boxIds.has(section)) byBox.set(section, [...(byBox.get(section) ?? []), node]);
    else whole.push(node);
  }
  const legacy = graph.nodes.filter((node) => node.parentId === pageId && (node.kind === "node" || node.kind === "sector") && !node.element && node.site?.kind !== "page").length;
  return { whole, byBox, legacy };
}
