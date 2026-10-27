// Katalog vlevo (prototyp, levý panel LIBRARY): typy komponent ve skupinách Web, Data, Control, Event, Deployment,
// Adapter, hledání v názvu, kategorii, poskytovateli i typech portů. Řízený Pod se samostatně nenabízí, vzniká uvnitř
// Kubernetes Deployment (stejně jako nabídka cílů vazby). Čistá logika bez Reactu.
import { catalog } from "../../model/logic/catalog";
import type { ComponentType } from "../../model/logic/model-types";

export const PALETTE_GROUPS = ["Web", "Data", "Control", "Event", "Deployment", "Adapter"] as const;
/** Typ komponenty přetahovaný z katalogu na plátno (HTML drag and drop). */
export const PALETTE_DRAG_TYPE = "application/x-opora-studio-type";

export type PaletteItem = { id: string; name: string; icon: string; provider: string; summary: string };
export type PaletteGroup = { id: string; items: PaletteItem[] };

function summary(type: ComponentType): string {
  const kinds = [...new Set(type.ports.map((port) => port.type))];
  return `${type.ports.length} ${type.ports.length === 1 ? "port" : type.ports.length < 5 ? "porty" : "portů"} · ${kinds.join(" · ")}`;
}

const haystack = (type: ComponentType) => [type.id, type.name, type.category, type.provider ?? "", ...type.ports.map((port) => port.type)].join(" ").toLowerCase();

export function paletteGroups(query = "", types: readonly ComponentType[] = catalog): PaletteGroup[] {
  const words = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const shown = types.filter((type) => type.id !== "pod" && words.every((word) => haystack(type).includes(word)));
  const order = [...PALETTE_GROUPS, ...new Set(shown.map((type) => type.group).filter((group) => !(PALETTE_GROUPS as readonly string[]).includes(group)))];
  // Obecné typy (bez poskytovatele) jako první, cloudové a technologické profily za nimi; jinak pořadí katalogu.
  const ranked = [...shown].sort((a, b) => Number(!!a.provider) - Number(!!b.provider));
  return order.map((id) => ({ id, items: ranked.filter((type) => type.group === id)
    .map((type) => ({ id: type.id, name: type.name, icon: type.icon, provider: type.provider ?? "", summary: summary(type) })) }))
    .filter((group) => group.items.length > 0);
}
