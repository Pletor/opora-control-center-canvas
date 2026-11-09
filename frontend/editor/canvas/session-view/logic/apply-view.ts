import type { Graph } from "@/shared/types/logic/types";
import type { SessionView } from "./use-session-view";

export function visibleSelection(view: SessionView, graph: Graph, parent: string | null) {
  const filter = view.filter.trim().toLocaleLowerCase();
  return view.selection.every(id => graph.nodes.some(node => node.id === id && node.parentId === parent && (!filter || node.name.toLocaleLowerCase().includes(filter))));
}
export function sameSelection(actual: string[], expected: string[]) {
  return actual.length === expected.length && [...actual].sort().every((id, index) => id === [...expected].sort()[index]);
}
