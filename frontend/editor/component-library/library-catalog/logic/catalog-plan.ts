import { relatesLines, type CatalogItem } from "./library-catalog";
import { catalogLayer } from "./catalog-families";
import type { CanvasNode } from "@/shared/types/logic/types";

export type CatalogPlacement = { parentId: string | null; position?: { x: number; y: number } };
export type CanvasPlanResult = { ok: boolean; dryRun: boolean; refs: Record<string, string>; digest: string; revision: number; summary: string };

/** Dropping on a component creates a child. An area is an explicit geometric target for the API. */
export function catalogPlacement(nodes: CanvasNode[], layer: string | null, targetId: string | null, point?: { x: number; y: number }): CatalogPlacement {
  const target = targetId ? nodes.find((node) => node.id === targetId) : undefined;
  if (targetId && !target) throw new Error("Cíl vložení již neexistuje. Obnovte plátno.");
  if (target?.kind === "comment") throw new Error("Komentář není cílem komponenty. Pusťte prvek na plátno nebo do části projektu.");
  if (target?.kind === "node" || target?.kind === "sector") return { parentId: target.id };
  return { parentId: target?.id ?? layer, ...(point ? { position: { x: Math.round(point.x), y: Math.round(point.y) } } : {}) };
}

/** One atomic canvas plan owns graph, saved specification, context blocks and rules. */
export function catalogPlan(item: CatalogItem, placement: CatalogPlacement) {
  const relates = relatesLines(item.relates);
  const text = [
    ...(relates.length ? ["## Souvisí s\n" + relates.map((line) => "- " + line).join("\n")] : []),
    ...(item.steps ?? []).map((step) => `## ${step.title}\n${step.text}`),
    ...(item.template?.trim() ? ["## Šablona\n" + item.template] : []),
  ].join("\n\n");
  const layer = catalogLayer(item);
  return { nodes: [{
    ref: "component", kind: "node" as const, parent: placement.parentId ? `@${placement.parentId}` : null,
    name: item.label, purpose: item.purpose,
    spec: { goal: item.purpose, non_goals: "", acceptance: item.done.join("\n") },
    card: { status: "draft" as const, ...(layer ? { layer } : {}) },
    ...(placement.position ? { position: placement.position } : {}),
    text, blocks: [], rules: item.invariants.map((rule) => ({ ...rule })),
  }] };
}
