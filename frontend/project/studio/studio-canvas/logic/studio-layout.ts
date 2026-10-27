// Rozložení karet jedné úrovně Studia: deterministické, nic se neukládá (docs/studio.md §2). Vrstvy zleva doprava
// podle směru vazeb (nejdelší cesta od karty bez vstupu; cyklus se zastaví stropem), uvnitř vrstvy pořadí grafu.
// Karty skupiny „bez sekce“ leží pod hlavním blokem v mřížce a dostanou rám skupiny. Čistá funkce bez Reactu.

export const CARD_WIDTH = 260;
export const CARD_HEIGHT = 150;
const COLUMN = CARD_WIDTH + 120;
const ROW = CARD_HEIGHT + 64;
const GROUP_COLUMNS = 4;
const GROUP_PAD = { left: 22, top: 40, right: 22, bottom: 22 };

export type LayoutCard = { id: string; grouped?: boolean };
export type LayoutLink = { source: string; target: string };
export type LayoutGroup = { id: string; x: number; y: number; width: number; height: number };
export type StudioLayout = { positions: Map<string, { x: number; y: number }>; group: LayoutGroup | null };

/** Vrstva karty = nejdelší cesta k ní po vazbách mezi kartami hlavního bloku, strop počet karet − 1. */
export function layerRanks(ids: string[], links: LayoutLink[]): Map<string, number> {
  const rank = new Map(ids.map((id) => [id, 0]));
  const inner = links.filter((link) => rank.has(link.source) && rank.has(link.target) && link.source !== link.target);
  const cap = Math.max(0, ids.length - 1);
  for (let pass = 0; pass < ids.length; pass++) {
    let changed = false;
    for (const { source, target } of inner) {
      const next = Math.min(cap, rank.get(source)! + 1);
      if (next > rank.get(target)!) { rank.set(target, next); changed = true; }
    }
    if (!changed) break;
  }
  return rank;
}

export function layoutLevel(cards: LayoutCard[], links: LayoutLink[]): StudioLayout {
  const main = cards.filter((card) => !card.grouped).map((card) => card.id);
  const grouped = cards.filter((card) => card.grouped).map((card) => card.id);
  const ranks = layerRanks(main, links);
  const rows = new Map<number, number>();
  const positions = new Map<string, { x: number; y: number }>();
  let bottom = 0;
  for (const id of main) {
    const column = ranks.get(id)!;
    const row = rows.get(column) ?? 0;
    rows.set(column, row + 1);
    positions.set(id, { x: column * COLUMN, y: row * ROW });
    bottom = Math.max(bottom, row * ROW + CARD_HEIGHT);
  }
  if (!grouped.length) return { positions, group: null };
  const top = (main.length ? bottom + 70 : 0) + GROUP_PAD.top;
  grouped.forEach((id, index) => positions.set(id, { x: GROUP_PAD.left + (index % GROUP_COLUMNS) * COLUMN, y: top + Math.floor(index / GROUP_COLUMNS) * ROW }));
  const columns = Math.min(GROUP_COLUMNS, grouped.length);
  const rowsUsed = Math.ceil(grouped.length / GROUP_COLUMNS);
  return { positions, group: {
    id: "studio-group-unsectioned", x: 0, y: top - GROUP_PAD.top,
    width: GROUP_PAD.left + (columns - 1) * COLUMN + CARD_WIDTH + GROUP_PAD.right,
    height: GROUP_PAD.top + (rowsUsed - 1) * ROW + CARD_HEIGHT + GROUP_PAD.bottom,
  } };
}
