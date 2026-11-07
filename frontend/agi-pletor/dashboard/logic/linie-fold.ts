import type { Board, BoardRow } from "./linie-board";

/**
 * Sbalení podstromu a zaměření na větev (docs/navrhy/2026-11-06-linie-barvy-a-zamereni.md §3). Strom se čte řetězem
 * `parent` (jméno větve rodiče); hlavička Items bez větve drží pod sebou větve `items/*`. Čistá logika bez Reactu.
 */
export const FOLD_KEY = "pletor.linie.folded";

/** Ruční řádek si sbalení ukládá na server (`PATCH /rows`), automatické, pevné a gitové v prohlížeči. */
export const manualRow = (row: BoardRow) => !row.fixed && !row.git && !row.auto;

/** Je `row` pod `above`? Hlavička Items (bez větve) vlastní větve items/* a sama visí pod develop. */
function under(row: BoardRow, above: BoardRow, byBranch: Map<string, BoardRow>): boolean {
  if (row.parent && row.parent === above.id) return true; // pohled podle plánu: `parent` je id řádku směru
  if (!above.branch) return above.type === "items" && row.branch.startsWith("items/");
  const start = row.parent || (row.type === "items" && !row.branch ? "develop" : "");
  for (let up = start, steps = 0; up && steps < 20; up = byBranch.get(up)?.parent ?? "", steps += 1) if (up === above.branch) return true;
  return false;
}

export function descendants(row: BoardRow, rows: BoardRow[]): BoardRow[] {
  const byBranch = new Map(rows.filter((r) => r.branch).map((r) => [r.branch, r]));
  return rows.filter((other) => other.id !== row.id && under(other, row, byBranch));
}

/** Sbalený řádek (`collapsed` ze serveru nebo id ve `folded`) zůstane se `collapsed: true`, jeho potomci zmizí. */
export function visibleRows(rows: BoardRow[], folded: Set<string>): BoardRow[] {
  const shut = rows.filter((row) => row.collapsed || folded.has(row.id));
  const hidden = new Set(shut.flatMap((row) => descendants(row, rows).map((r) => r.id)));
  return rows.filter((row) => !hidden.has(row.id)).map((row) => (folded.has(row.id) ? { ...row, collapsed: true } : row));
}

/** Zaměření: cesta ke kořeni (`path`, tenké řádky bez kuliček) a zaměřený podstrom; neznámá větev = vše. */
export function focusRows(rows: BoardRow[], branch: string): { rows: BoardRow[]; path: string[] } {
  const target = rows.find((row) => row.branch === branch);
  if (!target) return { rows, path: [] };
  const byBranch = new Map(rows.filter((r) => r.branch).map((r) => [r.branch, r]));
  const path: string[] = [];
  for (let up = byBranch.get(target.parent); up && path.length < 20; up = byBranch.get(up.parent)) path.push(up.id);
  const keep = new Set([...path, target.id, ...descendants(target, rows).map((r) => r.id)]);
  return { rows: rows.filter((row) => keep.has(row.id)), path };
}

/** Chip sbaleného řádku: kolik větví a kuliček pod ním (včetně jeho vlastních kuliček) je schováno. */
export function foldChip(row: BoardRow, rows: BoardRow[], balls: Board["balls"]): string {
  const ids = new Set([row.id, ...descendants(row, rows).map((r) => r.id)]);
  return `${ids.size - 1} větví · ${balls.filter((ball) => ids.has(ball.rowId)).length} kuliček`;
}

/** Board, jak ho editor kreslí: zaměření, pak sbalení; kuličky řádků cesty se nekreslí (řádek zůstane tenký). */
export function shownBoard(board: Board, folded: Set<string>, focus: string): { board: Board; chips: Record<string, string> } {
  const focused = focus ? focusRows(board.rows, focus) : { rows: board.rows, path: [] };
  const rows = visibleRows(focused.rows, folded);
  const chips = Object.fromEntries(rows.filter((row) => row.collapsed).map((row) => [row.id, foldChip(row, focused.rows, board.balls)]));
  return { board: { ...board, rows, balls: board.balls.filter((ball) => !focused.path.includes(ball.rowId)) }, chips };
}

export function readFolded(storage: Pick<Storage, "getItem"> | undefined): Set<string> {
  try {
    const value: unknown = JSON.parse(storage?.getItem(FOLD_KEY) ?? "[]");
    return new Set(Array.isArray(value) ? value.filter((id): id is string => typeof id === "string") : []);
  } catch {
    return new Set();
  }
}
