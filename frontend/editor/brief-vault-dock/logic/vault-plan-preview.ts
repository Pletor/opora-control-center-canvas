// Náhled plánu struktury od serveru (POST /api/brief-vault/plan, docs/schranka-neurony.md §4): dávka canvas-plan
// už ověřená dryRun. Tady se jen čte pro člověka: které karty vzniknou, kolik bloků a které nové oblasti a sektory.
// Bez Reactu.
import { api } from "@/shared/types/logic/types";
import type { VaultScope } from "./vault-actions";

export type PlanNode = {
  ref: string;
  kind: string;
  name: string;
  parent: string | null;
  blocks?: { title: string }[];
};
export type ServerPlan = {
  plan: { nodes: PlanNode[]; edges: unknown[] };
  summary: string;
  hash: string;
  skipped: number;
  digest: string;
};

/** Karty, počet bloků a nové oblasti / sektory (existující, znovu použité se nevypisují). */
export function previewOf(result: ServerPlan): { cards: PlanNode[]; blocks: number; structure: string[] } {
  const cards = result.plan.nodes.filter((node) => node.kind === "node");
  return {
    cards,
    blocks: cards.reduce((sum, card) => sum + (card.blocks?.length ?? 0), 0),
    structure: result.plan.nodes.filter((node) => node.kind === "area" || node.kind === "sector")
      .map((node) => (node.kind === "area" ? "oblast " : "sektor ") + node.name),
  };
}

/** Plán od serveru (jen čtení, nic se nezapíše). */
export function fetchPlan(scope: VaultScope, fragmentIds: string[]): Promise<ServerPlan> {
  return api<ServerPlan>("/api/brief-vault/plan", { ...scope, fragmentIds });
}
