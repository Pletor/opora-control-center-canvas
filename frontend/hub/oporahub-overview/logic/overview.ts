import type { GraphContext, GraphSummary } from "@/hub/graph-proposals/logic/graph-proposals";
import type { PlanContext, PlanChangeset } from "@/hub/plan-changes/logic/plan-changes";
import type { ExecutionSummary } from "@/hub/execution-receipts/logic/execution-receipts";
import type { Graph } from "@/shared/types/logic/types";

export type DetailKind = "graph" | "changes" | "executions" | "evidence" | "policy" | "tracking" | "budgets" | "history" | "api";
export type DetailTarget = { kind: DetailKind; title: string; id?: string };
export type Decision = DetailTarget & { author: string; stale: boolean | null; impact: string; createdAt: string };
function graphSnapshot(graph: Graph) {
  return JSON.stringify({ nodes: [...graph.nodes].sort((a, b) => a.id.localeCompare(b.id)).map(node => [node.id, node.kind, node.name,
    node.purpose, node.parentId, node.sourceRef?.origin, node.sourceRef?.kind, node.sourceRef?.path, node.x, node.y, node.size?.w, node.size?.h]),
    edges: [...graph.edges].sort((a, b) => a.id.localeCompare(b.id)).map(edge => [edge.id, edge.source, edge.target, edge.port ?? "next", edge.sourceBlockId, edge.sourcePortId]) });
}
export function pendingDecisions(graph: GraphSummary[], changes: PlanChangeset[], acceptedHead: string | null, basisKnown = true): Decision[] {
  const superseded = new Set(graph.map(item => item.supersedes).filter(Boolean));
  return [
    ...graph.filter(item => !item.accepted && !superseded.has(item.id)).map(item => ({ kind: "graph" as const, id: item.id,
      title: item.subject, author: item.by.name, stale: basisKnown ? item.parentRevision !== acceptedHead : null, createdAt: item.createdAt,
      impact: "Změna grafu · přesný dopad zobrazí kontrola návrhu." })),
    ...changes.filter(item => !item.accepted).map(item => ({ kind: "changes" as const, id: item.id, title: item.subject,
      author: item.by.name, stale: basisKnown ? item.parentRevision !== acceptedHead : null, createdAt: item.createdAt,
      impact: `Změna zadání · ${item.changes.length} dotčených karet.` })),
  ].sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}
export function acceptedPlan(graph: GraphContext | null, changes: PlanContext | null) {
  if (!graph || !changes) return { head: null, basisKnown: false, differs: null, warning: "Přijatý plán není úplně načten. Obnovte podklady." };
  if (graph.acceptedHead !== changes.acceptedHead) return { head: null, basisKnown: false, differs: null, warning: "Podklady mají různé přijaté revize. Obnovte je před rozhodnutím." };
  const graphDiffers = graph.acceptedGraph && graph.workingGraph ? graphSnapshot(graph.acceptedGraph) !== graphSnapshot(graph.workingGraph) : null;
  return { head: graph.acceptedHead, basisKnown: true, differs: changes.workingDiffers || graph.architectureContext?.differs || graphDiffers,
    warning: !graph.acceptedHead ? "Nejprve zkontrolujte a přijměte výchozí plán." : graph.requiresBaseAdoption || !graph.graphManifestId ? "Zadání přijato · graf čeká na převzetí." : "" };
}
/** Running is a read-time observation; elapsed monotonic time can only revoke it. */
export function observedExecutionLabel(item: ExecutionSummary, elapsedSeconds = 0) {
  if (item.state === "running") return Number.isFinite(item.expiresAt) && Number.isFinite(item.serverNow)
    ? item.expiresAt > item.serverNow + elapsedSeconds ? "● Aktivní při načtení" : "□ Oprávnění vypršelo"
    : "? Autorita nedoložena";
  return ({ reported: "◇ Nahlášeno, neověřeno", released: "□ Uvolněno", revoked: "□ Oprávnění neplatí", cancelled: "□ Lidsky zrušeno" } as Record<string, string>)[item.state] ?? "? Neznámý stav";
}
export function nextExecutionStep(item: ExecutionSummary, elapsedSeconds = 0) {
  if (item.state === "reported") return "Člověk zkontroluje výsledek a nezávislé důkazy.";
  if (item.state === "running" && Number.isFinite(item.expiresAt) && Number.isFinite(item.serverNow) && item.expiresAt > item.serverNow + elapsedSeconds) return "Agent odevzdá výsledek v mezích oprávnění.";
  return "Další běh vyžaduje nový claim a dostupné limity.";
}
