// Usazení layoutu stránky (vrstva 1 plátna 2): sourozenci (boxy se stejným `parent`) se nikdy nepřekrývají a rodič
// pod hlavičkou (jeden řádek) pojme všechny své děti. Jako svislá kolize v react-grid-layout: boxy se berou shora dolů
// (y, pak x) a box, který narazí na už umístěného sourozence, sjede těsně pod něj. Mění jen `box`. Bez Reactu, test vedle.
import type { SectionBox } from "@/shared/types/logic/types";
import { bottomOf, clampBox, settle, type LayoutSection } from "./layout-grid";

const same = (a: SectionBox, b: SectionBox) => a.x === b.x && a.y === b.y && a.w === b.w && a.h === b.h;

/**
 * Usazený layout; bez překryvu vrací tentýž seznam (idempotentní, stejné pořadí i objekty nezměněných sekcí).
 * `first` = box, který má na své úrovni přednost (právě tažený, zvětšený nebo puštěný): zůstane, kam ho člověk dal,
 * a kolidující sourozenci uhnou dolů. Úrovně se usazují zdola, aby rodič znal výšku dětí dřív než své sourozence.
 */
export function settleLayout<T extends LayoutSection>(sections: T[], first?: string): T[] {
  const boxes = new Map(sections.map((section) => [section.id, section.box]));
  const kids = new Map<string | null, T[]>();
  for (const section of sections) kids.set(section.parent ?? null, [...(kids.get(section.parent ?? null) ?? []), section]);
  const level = (parent: string | null) => {
    const children = kids.get(parent) ?? [];
    for (const child of children) level(child.id);
    const at = (section: T) => boxes.get(section.id)!;
    const order = [...children].sort((a, b) => Number(b.id === first) - Number(a.id === first) || at(a).y - at(b).y || at(a).x - at(b).x);
    const placed: SectionBox[] = [];
    for (const child of order) { const box = settle(at(child), placed); boxes.set(child.id, box); placed.push(box); }
    const own = parent === null ? undefined : boxes.get(parent);
    if (own && placed.length && 1 + bottomOf(placed) > own.h) boxes.set(parent!, clampBox({ ...own, h: 1 + bottomOf(placed) }));
  };
  level(null);
  let changed = false;
  const next = sections.map((section) => {
    const box = boxes.get(section.id)!;
    if (same(box, section.box)) return section;
    changed = true;
    return { ...section, box };
  });
  return changed ? next : sections;
}
