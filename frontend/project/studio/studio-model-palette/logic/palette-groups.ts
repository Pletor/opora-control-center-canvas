// Katalog vlevo (prototyp, levý panel LIBRARY): typy komponent ve skupinách Web, Data, Control, Event, Deployment,
// Adapter, hledání v názvu, kategorii, poskytovateli i typech portů. Řízený Pod se samostatně nenabízí, vzniká uvnitř
// Kubernetes Deployment (stejně jako nabídka cílů vazby). Čistá logika bez Reactu.
import { catalog } from "../../model/logic/catalog";
import { groupInOrder, matchesWords, searchWords } from "@/shared/flow-editor/node-palette/logic/palette-search";
import type { ComponentType } from "../../model/logic/model-types";

export const PALETTE_GROUPS = ["Web", "Data", "Control", "Event", "Deployment", "Adapter"] as const;

export type PaletteItem = { id: string; name: string; icon: string; provider: string; summary: string };
export type PaletteGroup = { id: string; items: PaletteItem[] };

function summary(type: ComponentType): string {
  const kinds = [...new Set(type.ports.map((port) => port.type))];
  return `${type.ports.length} ${type.ports.length === 1 ? "port" : type.ports.length < 5 ? "porty" : "portů"} · ${kinds.join(" · ")}`;
}

const haystack = (type: ComponentType) => [type.id, type.name, type.category, type.provider ?? "", ...type.ports.map((port) => port.type)].join(" ");

export function paletteGroups(query = "", types: readonly ComponentType[] = catalog): PaletteGroup[] {
  const words = searchWords(query);
  // Obecné typy (bez poskytovatele) jako první, cloudové a technologické profily za nimi; jinak pořadí katalogu.
  const shown = types.filter((type) => type.id !== "pod" && matchesWords(haystack(type), words)).sort((a, b) => Number(!!a.provider) - Number(!!b.provider));
  return groupInOrder(shown, PALETTE_GROUPS).map((group) => ({ id: group.id, items: group.items
    .map((type) => ({ id: type.id, name: type.name, icon: type.icon, provider: type.provider ?? "", summary: summary(type) })) }));
}
