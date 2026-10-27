import { relatesLines, type CatalogItem } from "./library-catalog";
import { catalogLayer } from "./catalog-families";
import type { CatalogPort } from "./catalog-agent-context";
import type { CanvasNode, CardAgentFields, EdgeCarries } from "@/shared/types/logic/types";

export type CatalogPlacement = { parentId: string | null; position?: { x: number; y: number } };
export type CanvasPlanResult = { ok: boolean; dryRun: boolean; refs: Record<string, string>; digest: string; revision: number; summary: string };
/**
 * Cílené vložení: existující karta, se kterou se nová spojí. `source` = existující karta je zdroj a vazba vede
 * do nové (první vstupní port nové dá `carries`); `target` = nová karta je zdroj (první výstupní port).
 */
export type CatalogLink = { nodeId: string; side: "source" | "target" };
type PlanEdge = { from: string; to: string; port: "next"; carries?: EdgeCarries };

/** Dropping on a component creates a child. An area is an explicit geometric target for the API. */
export function catalogPlacement(nodes: CanvasNode[], layer: string | null, targetId: string | null, point?: { x: number; y: number }): CatalogPlacement {
  const target = targetId ? nodes.find((node) => node.id === targetId) : undefined;
  if (targetId && !target) throw new Error("Cíl vložení již neexistuje. Obnovte plátno.");
  if (target?.kind === "comment") throw new Error("Komentář není cílem komponenty. Pusťte prvek na plátno nebo do části projektu.");
  if (target?.kind === "node" || target?.kind === "sector") return { parentId: target.id };
  return { parentId: target?.id ?? layer, ...(point ? { position: { x: Math.round(point.x), y: Math.round(point.y) } } : {}) };
}

/**
 * Kontext pro agenta z položky (docs/zive-zobrazeni-a-knihovna.md §5) do karty: `tech`, `states`, `fetch` a `fill`
 * jen když jsou; prázdný seznam `fetch` se vynechá, aby se nic nedoplňovalo (backend prázdný seznam odmítne).
 */
export function catalogCardContext(item: CatalogItem): { tech?: string; states?: string[] } & CardAgentFields {
  const files = item.fetch?.files ?? [];
  const docs = item.fetch?.docs ?? [];
  return {
    ...(item.tech ? { tech: item.tech } : {}),
    ...(item.states?.length ? { states: [...item.states] } : {}),
    ...(files.length || docs.length ? { fetch: { ...(files.length ? { files: [...files] } : {}), ...(docs.length ? { docs: [...docs] } : {}) } } : {}),
    ...(item.fill?.length ? { fill: [...item.fill] } : {}),
  };
}

/** Navržená vazba cíleného vložení; bez `link` žádná (porty zůstanou jen v textu karty). */
export function catalogEdges(item: CatalogItem, ref: string, link?: CatalogLink): PlanEdge[] {
  if (!link) return [];
  const direction = link.side === "source" ? "in" : "out";
  const port = (item.ports ?? []).find((entry) => entry.direction === direction);
  const ends = link.side === "source" ? { from: `@${link.nodeId}`, to: ref } : { from: ref, to: `@${link.nodeId}` };
  return [{ ...ends, port: "next", ...(port ? { carries: port.carries } : {}) }];
}

function portLine(port: CatalogPort): string {
  return `- ${port.direction === "in" ? "vstup" : "výstup"} \`${port.id}\`: ${port.carries}`;
}

/** One atomic canvas plan owns graph, saved specification, context blocks, rules and the proposed link. */
export function catalogPlan(item: CatalogItem, placement: CatalogPlacement, link?: CatalogLink) {
  const relates = relatesLines(item.relates);
  const text = [
    ...(relates.length ? ["## Souvisí s\n" + relates.map((line) => "- " + line).join("\n")] : []),
    ...(item.ports?.length ? ["## Porty\n" + item.ports.map(portLine).join("\n")] : []),
    ...(item.steps ?? []).map((step) => `## ${step.title}\n${step.text}`),
    ...(item.template?.trim() ? ["## Šablona\n" + item.template] : []),
  ].join("\n\n");
  const layer = catalogLayer(item);
  const edges = catalogEdges(item, "component", link);
  return { nodes: [{
    ref: "component", kind: "node" as const, parent: placement.parentId ? `@${placement.parentId}` : null,
    name: item.label, purpose: item.purpose,
    spec: { goal: item.purpose, non_goals: "", acceptance: item.done.join("\n") },
    card: { status: "draft" as const, ...(layer ? { layer } : {}), ...catalogCardContext(item) },
    ...(placement.position ? { position: placement.position } : {}),
    text, blocks: [], rules: item.invariants.map((rule) => ({ ...rule })),
  }], ...(edges.length ? { edges } : {}) };
}
