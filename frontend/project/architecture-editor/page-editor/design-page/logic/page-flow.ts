// Pohled Design vrstvy 1 (docs/navrhy/2026-11-10-platno-2.md, Verze 6): stránka jako tok shora dolů, ne mřížka řádků.
// Boxy jednoho rodiče se seskupí do řádků (překrývající se rozsah y) a v řádku do sloupců (překrývající se rozsah x),
// aby vysoký box vlevo a dva nad sebou vpravo zůstaly vedle sebe. Bez Reactu, test vedle.
import { COLUMNS, type LayoutSection } from "../../layout-canvas/logic/layout-grid";

/** Sloupec řádku: `start`/`span` ve sloupcích mřížky, `items` nad sebou podle y. */
export type FlowColumn = { start: number; span: number; items: LayoutSection[] };
/** Řádek toku: sloupce zleva doprava, `gaps[i]` = prázdné sloupce před sloupcem i, `rest` = prázdno vpravo. */
export type FlowRow = { columns: FlowColumn[]; gaps: number[]; rest: number };

/** Seskupí boxy (sourozence) do řádků toku podle (y, x). */
export function pageFlow(boxes: LayoutSection[]): FlowRow[] {
  const sorted = [...boxes].sort((a, b) => a.box.y - b.box.y || a.box.x - b.box.x);
  const rows: { bottom: number; items: LayoutSection[] }[] = [];
  for (const section of sorted) {
    const last = rows.at(-1);
    if (last && section.box.y < last.bottom) { last.items.push(section); last.bottom = Math.max(last.bottom, section.box.y + section.box.h); }
    else rows.push({ bottom: section.box.y + section.box.h, items: [section] });
  }
  return rows.map(({ items }) => {
    const columns: FlowColumn[] = [];
    for (const section of [...items].sort((a, b) => a.box.x - b.box.x || a.box.y - b.box.y)) {
      const last = columns.at(-1);
      if (last && section.box.x < last.start + last.span) { last.items.push(section); last.span = Math.max(last.span, section.box.x + section.box.w - last.start); }
      else columns.push({ start: section.box.x, span: section.box.w, items: [section] });
    }
    columns.forEach((column) => column.items.sort((a, b) => a.box.y - b.box.y));
    const gaps = columns.map((column, index) => column.start - (index ? columns[index - 1].start + columns[index - 1].span : 0));
    const end = columns.at(-1)!;
    return { columns, gaps, rest: Math.max(0, COLUMNS - end.start - end.span) };
  });
}
