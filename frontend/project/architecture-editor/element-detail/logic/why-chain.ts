// Řetěz „proč“ u komponenty v Detailu prvku (docs/cesta-zakaznika-a-brief.md §4.1): kým se zákazník stane (bod B
// cesty) → jaký posun nastane na stránce (krok cesty) → čím k němu přispívá sekce, kterou komponenta realizuje
// (`moves`). Čistá logika bez Reactu, čte jen z grafu; co v grafu není, je `null`, nic se nedoplňuje.
import { cardComponent } from "@/shared/card-context/logic/card-context";
import type { Graph } from "@/shared/types/logic/types";
import { ancestry } from "./agent-context";

export type WhyChain = {
  /** Cesta, ze které je bod B a posun: první cesta aplikace, na níž stránka leží; `null` = stránka na cestě není. */
  journey: string | null;
  pointB: string | null;
  shift: string | null;
  moves: string | null;
};

/**
 * Řetěz pro uzel (`kind: "node"`) pod stránkou. Stránka je nejbližší předek se `site.kind = "page"`, aplikace
 * nejbližší předek se `site.kind = "application"`. Leží-li stránka na více cestách, bere se první cesta a v ní
 * první krok s touto stránkou (pořadí jako `journeysOfPage`). Sekce je `card.section`, jen když ji stránka má.
 * Když chybí bod B, posun i `moves`, vrací `null` a řádka se neukáže.
 */
export function whyChain(graph: Graph, nodeId: string): WhyChain | null {
  const [node, ...ancestors] = ancestry(graph, nodeId);
  if (!node || node.kind !== "node" || node.site) return null;
  const page = ancestors.find((item) => item.site?.kind === "page");
  if (page?.site?.kind !== "page") return null;
  const app = ancestors.find((item) => item.site?.kind === "application");
  const journeys = app?.site?.kind === "application" ? app.site.journeys ?? [] : [];
  const journey = journeys.find((item) => item.steps.some((step) => step.page === page.id)) ?? null;
  const step = journey?.steps.find((item) => item.page === page.id) ?? null;
  const sectionId = cardComponent(node).section;
  const section = sectionId ? (page.site.sections ?? []).find((item) => item.id === sectionId) : undefined;
  const chain: WhyChain = { journey: journey?.name ?? null, pointB: journey?.pointB ?? null, shift: step?.shift ?? null, moves: section?.moves ?? null };
  return chain.pointB || chain.shift || chain.moves ? chain : null;
}

/** Jedna řádka: „B: … → stránka: … → sekce: …“; chybějící článek se vynechá. */
export function whyChainText(chain: WhyChain): string {
  return [chain.pointB && "B: " + chain.pointB, chain.shift && "stránka: " + chain.shift, chain.moves && "sekce: " + chain.moves]
    .filter(Boolean).join(" → ");
}
