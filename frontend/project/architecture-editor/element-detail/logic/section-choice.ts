// Výběr „Sekce stránky“ v Detailu prvku (docs/architektura-pro-agenty.md §3.3): kterou sekci nejbližší stránky
// komponenta realizuje (`card.section`). Čistá logika bez Reactu; ukládá rodič přes `setEditorNodeSection`.
import { cardComponent } from "@/shared/card-context/logic/card-context";
import type { Graph } from "@/shared/types/logic/types";
import { SECTION_ROLE_LABELS } from "../../domain-map/logic/page-site";
import { ancestry } from "./agent-context";

export type SectionOption = { id: string; label: string };
export type SectionChoice = {
  /** Sekce nejbližší stránky v jejím pořadí; popisek je role a název („Formulář · Poptávka“). */
  options: SectionOption[];
  /** Zapsaná sekce; prázdný řetězec = neurčeno. */
  value: string;
  /** Zapsaná sekce, kterou stránka už nemá (smazaná nebo karta mimo stránku); jinak `null`. */
  missing: string | null;
};

/**
 * Výběr pro uzel (`kind: "node"`) pod stránkou se sekcemi. Uzel s odkazem na sekci dostane výběr vždy, i mimo
 * stránku nebo pod stránkou bez sekcí, aby šel chybějící odkaz zrušit. Jinak `null` a výběr se neukáže.
 * Nejbližší stránka je první předek se `site.kind = "page"`; uzel sám (ani stránka) se nepočítá.
 */
export function sectionChoice(graph: Graph, nodeId: string): SectionChoice | null {
  const [node, ...ancestors] = ancestry(graph, nodeId);
  if (!node || node.kind !== "node" || node.site) return null;
  const page = ancestors.find((item) => item.site?.kind === "page");
  const sections = page?.site?.kind === "page" ? page.site.sections ?? [] : [];
  const value = cardComponent(node).section ?? "";
  if (!sections.length && !value) return null;
  const options = sections.map((section) => ({
    id: section.id,
    label: `${SECTION_ROLE_LABELS[section.role] ?? section.role} · ${section.name}`,
  }));
  return { options, value, missing: value && !options.some((option) => option.id === value) ? value : null };
}

/** Hodnota z `<select>`: prázdná volba je „neurčeno“ (`null`), jinak id sekce. */
export const parseSection = (value: string): string | null => value || null;
