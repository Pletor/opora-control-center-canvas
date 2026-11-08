import type { ResearchCard, ResearchHeader, ResearchScope } from "./research-types";

export type DecisionReview = {
  id: string; decision: ResearchCard; problem: ResearchCard; evidence: ResearchCard[];
  rationale: string; assumptions: string; constraints: string; reviewedAt: string;
};
export type ResearchTask = { ref: string; title: string; goal: string; acceptance: string; dependsOn: string[]; nodeId?: string; parentId?: string };
export type TaskProposal = { reviewId: string; proposalId?: string; proposalKind: "graph" | "spec";
  tasks: ResearchTask[]; nodeIds?: Record<string, string>; accepted: boolean; acceptedRevision: string | null; pending?: boolean };
export const decisionEvidence = (cards: ResearchHeader[]) => cards.filter(card => !card.archived
  && ["verified", "observed"].includes(card.verification.status) && card.sourceCount > 0);
export const newResearchTask = (): ResearchTask => ({ ref: "task-" + crypto.randomUUID(), title: "", goal: "", acceptance: "", dependsOn: [] });
export function taskProblem(tasks: ResearchTask[], existing: boolean): string {
  if (!tasks.length) return "Přidejte alespoň jeden konkrétní úkol.";
  if (tasks.some(task => !task.title.trim() || !task.goal.trim() || !task.acceptance.trim())) return "Každý úkol potřebuje název, cíl a ověřitelné kritérium dokončení.";
  if (existing && tasks.some(task => !task.nodeId)) return "Vyberte existující kartu pro každý úkol.";
  if (existing && new Set(tasks.map(task => task.nodeId)).size !== tasks.length) return "Stejnou kartu nelze aktualizovat dvakrát.";
  const pending = new Map(tasks.map(task => [task.ref, new Set(task.dependsOn)]));
  if (tasks.some(task => task.dependsOn.some(ref => !pending.has(ref) || ref === task.ref))) return "Závislost musí ukazovat na jiný úkol tohoto návrhu.";
  while (pending.size) {
    const ready = [...pending].filter(([, deps]) => !deps.size).map(([ref]) => ref);
    if (!ready.length) return "Závislosti úkolů tvoří kruh. Upravte pořadí.";
    for (const ref of ready) { pending.delete(ref); for (const deps of pending.values()) deps.delete(ref); }
  }
  return "";
}
export const decisionHubUrl = (scope: ResearchScope) => `?${new URLSearchParams({ ...scope, environment: "hub", mode: "structure" })}`;
