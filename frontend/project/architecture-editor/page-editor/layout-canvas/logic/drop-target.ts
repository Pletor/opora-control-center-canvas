// Kam míří puštění na plátně 2: čte jen DOM pod ukazatelem (atributy, které kreslí `LayoutCanvas`), nic nepočítá.
// `data-grid-parent` = mřížka boxů (prázdné = stránka), `data-drop-section` = cíl prvku logiky (prázdné = Celá stránka).
import type { Point } from "./layout-grid";

/** Nejhlubší mřížka pod ukazatelem mimo vynechané boxy (tažený box a jeho potomci); `null` = mimo stránku. */
export function gridAt(point: Point, skip: ReadonlySet<string> = new Set()): { parent: string | null; rect: DOMRect } | null {
  for (const element of document.elementsFromPoint(point.x, point.y)) {
    const parent = element instanceof HTMLElement ? element.dataset.gridParent : undefined;
    if (parent === undefined || skip.has(parent)) continue;
    return { parent: parent || null, rect: element.getBoundingClientRect() };
  }
  return null;
}

/** Box (id), Celá stránka (`null`), nebo `undefined`, když pod ukazatelem cíl prvku logiky není. */
export function sectionAt(point: Point): string | null | undefined {
  const target = document.elementFromPoint(point.x, point.y)?.closest<HTMLElement>("[data-drop-section]");
  return target ? target.dataset.dropSection || null : undefined;
}
