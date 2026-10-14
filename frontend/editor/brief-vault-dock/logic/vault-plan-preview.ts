// Náhled plánu struktury od serveru (POST /api/brief-vault/plan, docs/schranka-neurony.md §4): dávka canvas-plan
// už ověřená dryRun. Tady se jen čte pro člověka: které karty vzniknou, kolik bloků a které nové oblasti a sektory.
// Odmítnutí 409 kvůli nezařazeným fragmentům nebo chybějící bráně `synthesized` (§9 bod 7) se rozloží na výčet
// fragmentů, aby je člověk mohl otevřít; nic neselže potichu. Bez Reactu.
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

/** Proč server plán odmítl a kterých fragmentů se to týká (z textu 409 `„název“ (id), …`). */
export type PlanBlocker = { reason: "unassigned" | "unsynthesized"; text: string; fragments: { id: string; title: string }[]; more: number };

const BLOCKERS: { reason: PlanBlocker["reason"]; marker: string; text: string }[] = [
  { reason: "unassigned", marker: "nezařazené fragmenty:", text: "Tyto fragmenty nemají disciplínu (ani po předcích). Bez ní server nesloží oblast a sektor; přiřaď ji v detailu fragmentu." },
  { reason: "unsynthesized", marker: "chybí platná brána synthesized", text: "Těmto fragmentům chybí platná brána 3. Mikrokrok (kritérium hotovo pro kartu). Navrhni a potvrď ji v detailu fragmentu." },
];

export function planBlocker(message: string): PlanBlocker | null {
  const found = BLOCKERS.find((item) => message.includes(item.marker));
  if (!found) return null;
  const fragments = [...message.matchAll(/„(.*?)“ \(([A-Za-z0-9_-]{1,80})\)/g)].map(([, title, id]) => ({ id, title }));
  const more = Number(/a dalších (\d+)/.exec(message)?.[1] ?? 0);
  return { reason: found.reason, text: found.text, fragments, more };
}
