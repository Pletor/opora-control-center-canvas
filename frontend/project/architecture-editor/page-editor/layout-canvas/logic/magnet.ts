// Magnet při tahu boxu na plátně 2: hrana taženého boxu blíž než jedna buňka k hraně souseda nebo rodiče se k ní
// přitáhne (zarovná se nebo přilne), jinak se poloha zaokrouhlí na celou buňku. Pracuje s necelou polohou pod
// ukazatelem, ještě před zaokrouhlením; kolize pak řeší `settleLayout`. Bez Reactu, test vedle.
import type { SectionBox } from "@/shared/types/logic/types";
import { clampBox, COLUMNS } from "./layout-grid";

/** Nejbližší hrana blíž než jedna buňka, jinak zaokrouhlená hodnota. */
function pull(value: number, edges: number[]): number {
  let best = Math.round(value), distance = 1;
  for (const edge of edges) if (Math.abs(edge - value) < distance) { distance = Math.abs(edge - value); best = edge; }
  return best;
}

/** `move`: levá i pravá hrana (a horní i dolní) se hledají společně; `resize`: jen pravá a dolní hrana, poloha zůstává. */
export function magnet(box: SectionBox, siblings: SectionBox[], mode: "move" | "resize"): SectionBox {
  const columns = siblings.flatMap((other) => [other.x, other.x + other.w]);
  const rows = siblings.flatMap((other) => [other.y, other.y + other.h]);
  if (mode === "resize") {
    const x = Math.round(box.x), y = Math.round(box.y);
    return clampBox({ x, y, w: Math.min(COLUMNS, pull(box.x + box.w, [COLUMNS, ...columns])) - x, h: pull(box.y + box.h, rows) - y });
  }
  const w = Math.round(box.w), h = Math.round(box.h);
  return clampBox({ x: pull(box.x, [0, COLUMNS - w, ...columns, ...columns.map((edge) => edge - w)]), y: pull(box.y, [0, ...rows, ...rows.map((edge) => edge - h)]), w, h });
}
