// Geometrie layoutu stránky na plátně 2 (vrstva 1, docs/navrhy/2026-11-10-platno-2.md): box = sekce stránky na mřížce
// 12 sloupců uvnitř rodiče, box v boxu nejvýš do hloubky 3. Mřížka, kolize jednoho boxu, vnoření a převod starých sekcí bez `box`.
// Bez Reactu, test vedle.
import type { PageSection, SectionBox } from "@/shared/types/logic/types";

export const COLUMNS = 12;
export const MAX_Y = 199;
export const MAX_H = 40;
export const MAX_DEPTH = 3;
/** Výška jednoho řádku mřížky na plátně v px; CSS dílku `layout-canvas` počítá se stejnou hodnotou (`--layout-row`). */
export const ROW_PX = 32;
/** Mezera mezi buňkami mřížky vodorovně i svisle (`--layout-gap` v CSS); krok řádku i sloupce ji započítává. */
export const GAP_PX = 8;
export const ROW_PITCH = ROW_PX + GAP_PX;
/** Krok jednoho sloupce v px: 12 sloupců a 11 mezer vyplní šířku mřížky. */
export const columnPitch = (width: number) => (width + GAP_PX) / COLUMNS;

/** Sekce, jak ji kreslí plátno: vždy s boxem a s platným rodičem (nebo bez něj). */
export type LayoutSection = PageSection & { box: SectionBox };
export type Point = { x: number; y: number };

const whole = (value: number) => Math.round(Number.isFinite(value) ? value : 0);

/** Celá čísla v mezích kontraktu: 1 ≤ w ≤ 12, x + w ≤ 12, 0 ≤ y ≤ 199, 1 ≤ h ≤ 40. */
export function clampBox(box: SectionBox): SectionBox {
  const w = Math.min(COLUMNS, Math.max(1, whole(box.w)));
  const h = Math.min(MAX_H, Math.max(1, whole(box.h)));
  return { x: Math.min(COLUMNS - w, Math.max(0, whole(box.x))), y: Math.min(MAX_Y, Math.max(0, whole(box.y))), w, h };
}

export const overlaps = (a: SectionBox, b: SectionBox) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
export const bottomOf = (boxes: SectionBox[]) => boxes.reduce((max, box) => Math.max(max, box.y + box.h), 0);

/** Kolize: box sjede pod každého souseda, se kterým se překrývá, dokud nestojí volně (nebo nenarazí na spodní mez). */
export function settle(box: SectionBox, siblings: SectionBox[]): SectionBox {
  let next = clampBox(box);
  for (let step = 0; step <= siblings.length; step += 1) {
    const hit = siblings.filter((other) => overlaps(next, other));
    if (!hit.length) break;
    next = clampBox({ ...next, y: bottomOf(hit) });
  }
  return next;
}

/** Nový box na konec: přes celou šířku rodiče (nebo `w`) pod nejnižším sourozencem. */
export const endBox = (siblings: SectionBox[], w: number, h: number): SectionBox => clampBox({ x: 0, y: bottomOf(siblings), w, h });

/** Buňka mřížky pod ukazatelem; `rect` je obdélník mřížky rodiče na obrazovce. */
export function cellAt(rect: { left: number; top: number; width: number }, point: Point): Point {
  const column = rect.width > 0 ? Math.floor((point.x - rect.left) / columnPitch(rect.width)) : 0;
  return { x: Math.min(COLUMNS - 1, Math.max(0, column)), y: Math.min(MAX_Y, Math.max(0, Math.floor((point.y - rect.top) / ROW_PITCH))) };
}

/**
 * Sekce pro kreslení: neznámý, vlastní nebo zacyklený rodič se zahodí (box jde na stránku) a sekce bez `box` (starší data)
 * se v rámci rodiče skládají pod boxy sourozenců na celou šířku po dvou řádcích, v uloženém pořadí.
 */
export function layoutSections(sections: PageSection[]): LayoutSection[] {
  const byId = new Map(sections.map((section) => [section.id, section]));
  const parentOf = (section: PageSection): string | undefined => {
    if (!section.parent || !byId.has(section.parent)) return undefined;
    const seen = new Set([section.id]);
    for (let cursor: string | undefined = section.parent; cursor && byId.has(cursor); cursor = byId.get(cursor)?.parent) {
      if (seen.has(cursor)) return undefined;
      seen.add(cursor);
    }
    return section.parent;
  };
  const parents = new Map(sections.map((section) => [section.id, parentOf(section)]));
  const bottoms = new Map<string | undefined, number>();
  for (const section of sections) if (section.box) {
    const key = parents.get(section.id);
    bottoms.set(key, Math.max(bottoms.get(key) ?? 0, section.box.y + section.box.h));
  }
  return sections.map((section) => {
    const { parent: _parent, ...rest } = section;
    const parent = parents.get(section.id);
    let box = section.box && clampBox(section.box);
    if (!box) { box = clampBox({ x: 0, y: bottoms.get(parent) ?? 0, w: COLUMNS, h: 2 }); bottoms.set(parent, box.y + box.h); }
    return { ...rest, box, ...(parent ? { parent } : {}) };
  });
}

export const childrenOf = (sections: LayoutSection[], parent: string | null) => sections.filter((section) => (section.parent ?? null) === parent);

/** Sekce a všichni její potomci. */
export function subtreeIds(sections: LayoutSection[], id: string): Set<string> {
  const ids = new Set([id]);
  for (let added = true; added; ) {
    added = false;
    for (const section of sections) if (section.parent && ids.has(section.parent) && !ids.has(section.id)) { ids.add(section.id); added = true; }
  }
  return ids;
}

/** Hloubka boxu: box na stránce má 1, stránka sama (`null`) 0. */
export function depthOf(sections: LayoutSection[], id: string | null): number {
  let depth = 0;
  for (let cursor = id; cursor && depth <= sections.length; cursor = sections.find((section) => section.id === cursor)?.parent ?? null) depth += 1;
  return depth;
}

/** Kolik úrovní box se svými potomky zabírá (samotný box 1). */
function heightOf(sections: LayoutSection[], id: string): number {
  return 1 + Math.max(0, ...childrenOf(sections, id).map((child) => heightOf(sections, child.id)));
}

/** Smí box `id` (`null` = nový box) do rodiče `parent`? Ne do sebe ani svého potomka a hloubka nejvýš 3. */
export function canNest(sections: LayoutSection[], id: string | null, parent: string | null): boolean {
  if (parent === null) return true;
  if (id && subtreeIds(sections, id).has(parent)) return false;
  return depthOf(sections, parent) + (id ? heightOf(sections, id) : 1) <= MAX_DEPTH;
}
