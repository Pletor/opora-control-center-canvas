// Náhled plánu struktury od serveru (POST /api/brief-vault/plan, docs/schranka-neurony.md §4): dávka canvas-plan
// už ověřená dryRun. Tady se jen čte pro člověka: které karty vzniknou, kolik bloků a které nové oblasti a sektory.
// Odmítnutí 409 (nezařazené fragmenty, chybějící brána `synthesized`, §9 bod 7) nese server strukturovaně
// v `fragments: [{id, title, reason}]`; tady se seskupí podle důvodu, aby je člověk mohl otevřít. Text chyby se
// neparsuje. Nic neselže potichu. Bez Reactu.
import { api, ApiError } from "@/shared/types/logic/types";
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

/** Proč server plán odmítl (`reason` z 409) a kterých fragmentů se to týká, seskupeno podle důvodu. */
export type PlanBlockedFragment = { id: string; title: string };
export type PlanBlocker = { groups: { reason: string; text: string; fragments: PlanBlockedFragment[] }[] };

const REASONS: Record<string, string> = {
  "no-discipline": "Tyto fragmenty nemají disciplínu (ani po předcích). Bez ní server nesloží oblast a sektor; přiřaď ji v detailu fragmentu.",
  "no-synthesized": "Těmto fragmentům chybí platná brána 3. Mikrokrok (kritérium hotovo pro kartu). Navrhni a potvrď ji v detailu fragmentu.",
  "not-live": "Tyto fragmenty nejsou živé zadání (smazané, nebo poznámka místo zadání); do plánu nepatří.",
};
const OTHER = "Tyto fragmenty brání složení plánu.";

/** Strukturované odmítnutí plánu (409 s `fragments`), jinak `null` (jiná chyba se ukáže jako text serveru). */
export function planBlocker(error: unknown): PlanBlocker | null {
  if (!(error instanceof ApiError) || error.status !== 409 || !Array.isArray(error.body.fragments)) return null;
  const groups: PlanBlocker["groups"] = [];
  for (const item of error.body.fragments as unknown[]) {
    if (!item || typeof item !== "object") continue;
    const { id, title, reason } = item as Record<string, unknown>;
    if (typeof id !== "string") continue;
    const key = typeof reason === "string" ? reason : "";
    let group = groups.find((entry) => entry.reason === key);
    if (!group) groups.push(group = { reason: key, text: REASONS[key] ?? OTHER, fragments: [] });
    group.fragments.push({ id, title: typeof title === "string" && title ? title : id });
  }
  return groups.length ? { groups } : null;
}
