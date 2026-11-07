import type { Board, BoardBall, BoardLayout, BoardRow } from "./linie-board";
import { branchColor } from "./linie-color";
import { descendants } from "./linie-fold";
import { plural } from "./linie-queues";
import { hhmm } from "./linie-summary";
import type { Tip } from "./linie-tip";
import { PAD, xOf } from "./linie-zoom";

/**
 * Skládání sloučených větví do rodiče (docs/navrhy/2026-11-06-linie-rebrand.md §10.3). Co je uzavřené, říká služba
 * (`row.closed`, §10.2); frontend jen rozhodne, co kreslit: uzavřený řádek s celým podstromem zmizí z editoru (ne z dat)
 * a na ose rodiče v čase uzavření leží značka ⊕/⊖. Rozbalené řádky (`unfolded`, pro aplikaci), vrstva „Sloučené větve“
 * a řetěz k vybrané kuličce (nebo zaměřené větvi) větev otevřou. Kuličky v boardu zůstávají, aby se rozsah času
 * při skládání nehnul (layout kreslí jen kuličky zobrazených řádků). Čistá logika bez Reactu.
 */
export const UNFOLD_KEY = "pletor.linie.unfolded";

/** Značka složené větve na rodiči: `rowId` = uzavřený řádek, `parentId` = řádek, na jehož ose leží; `open` = rozbaleno. */
export type Knot = { rowId: string; parentId: string; label: string; at: string; sha7: string; target: string; open: boolean; color: string };
export type LaidKnot = Knot & { x: number; y: number };

const parentOf = (row: BoardRow, byBranch: Map<string, BoardRow>) => byBranch.get(row.parent) ?? (row.closed ? byBranch.get(row.closed.target) : undefined);

/** Uzavřené řádky na cestě od řádku ke kořeni: výběr uvnitř složené větve otevře každou úroveň nad sebou. */
export function chainOf(rows: BoardRow[], rowId: string): string[] {
  const byBranch = new Map(rows.filter((r) => r.branch).map((r) => [r.branch, r]));
  const out: string[] = [];
  for (let row = rows.find((r) => r.id === rowId), steps = 0; row && steps < 20; row = parentOf(row, byBranch), steps += 1) if (row.closed) out.push(row.id);
  return out;
}

/** Řádky otevřené mimo `unfolded`: řetěz vybrané kuličky a zaměřené větve (`?ticket=`, `?branch=`, fronta, deník). */
export function forcedOpen(board: Board, picked: string, focus: string): string[] {
  const ballRow = board.balls.find((b) => b.ticketId === picked)?.rowId ?? "";
  const focusRow = (focus && board.rows.find((r) => r.branch === focus)?.id) || "";
  return [...chainOf(board.rows, ballRow), ...chainOf(board.rows, focusRow)];
}

/** Čas značky: `closed.at`, jinak čas merge commitu `sha` (skutečný merge nebo commit kuličky), jinak neznámý. */
function atOf(row: BoardRow, board: Board): string {
  const c = row.closed!;
  if (c.at || !c.sha) return c.at;
  return board.realMerges.find((m) => m.sha === c.sha)?.at
    ?? board.balls.flatMap((b) => b.commits).find((commit) => commit.sha === c.sha)?.at ?? "";
}

/** Uzavřený řádek se složí, když má rodiče a není otevřený (`open`) ani zapnutá vrstva (`all`); značka zůstává vždy. */
export function foldClosed(board: Board, open: Set<string>, all: boolean): { board: Board; knots: Knot[] } {
  const byBranch = new Map(board.rows.filter((r) => r.branch).map((r) => [r.branch, r]));
  const shut = all ? [] : board.rows.filter((r) => r.closed && parentOf(r, byBranch) && !open.has(r.id));
  const hidden = new Set(shut.flatMap((r) => [r.id, ...descendants(r, board.rows).map((d) => d.id)]));
  const knots = board.rows.flatMap((row): Knot[] => {
    const up = row.closed && parentOf(row, byBranch);
    if (!up || hidden.has(up.id)) return [];
    // Kaskáda: uzavřený rodič s uzavřenými dětmi nese součet větví pod sebou (bez sebe) a kuliček celého podstromu.
    const kids = descendants(row, board.rows).filter((d) => d.closed);
    const balls = plural([row, ...kids].reduce((sum, r) => sum + (r.closed?.balls ?? 0), 0), "kulička", "kuličky", "kuliček");
    return [{ rowId: row.id, parentId: up.id, label: [row.name, ...(kids.length ? [plural(kids.length, "větev", "větve", "větví")] : []), balls].join(" · "),
      at: atOf(row, board), sha7: row.closed!.sha.slice(0, 7), target: row.closed!.target, open: !hidden.has(row.id), color: branchColor(row.branch || row.name, board.rows) }];
  });
  return { board: { ...board, rows: board.rows.filter((r) => !hidden.has(r.id)) }, knots };
}

/** Značka leží na ose rodiče v `x(at)` (nikdy vlevo za okrajem, aby větev zůstala dosažitelná); bez času na konci osy. */
export function placeKnots(knots: Knot[], layout: BoardLayout): LaidKnot[] {
  const scale = { t0: layout.t0, k: layout.k };
  return knots.flatMap((knot) => {
    const row = layout.rows.find((r) => r.id === knot.parentId);
    if (!row || row.collapsed) return [];
    const t = Date.parse(knot.at);
    return [{ ...knot, label: Number.isNaN(t) ? `${knot.label} · uzavřeno ?` : knot.label, x: Number.isNaN(t) ? xOf(scale, layout.t1) : Math.max(PAD, xOf(scale, t)), y: row.y }];
  });
}

export function knotTip(knot: LaidKnot): Tip {
  return { x: knot.x, y: knot.y, title: knot.label, rows: [
    { k: "uzavřeno", v: `${knot.at ? hhmm(knot.at) : "?"} do ${knot.target}` }, ...(knot.sha7 ? [{ k: "merge", v: knot.sha7 }] : []),
  ], hint: knot.open ? "klik = složit" : "klik = rozbalit" };
}

/** Další klik na značku: otevřená se složí (zmizí z `unfolded`), složená se otevře. */
export function toggleKnot(unfolded: Set<string>, knot: Pick<Knot, "rowId" | "open">): Set<string> {
  const next = new Set(unfolded);
  if (knot.open) next.delete(knot.rowId); else next.add(knot.rowId);
  return next;
}

/** Formulář kuličky: větev, která už existuje jako uzavřený řádek, se znovu otevře pod cílem toho řádku. */
export const reopenOf = (rows: BoardRow[], branch: string) => rows.find((r) => r.closed && branch.trim() && r.branch === branch.trim());

/** Kolik začleněných kuliček téže větve předchází nezačleněné kuličce (navazuje na ně); začleněná sama nenavazuje. */
export const followsOf = (balls: BoardBall[], ball: BoardBall | undefined) =>
  !ball || ball.state === "merged" ? 0 : balls.filter((b) => b.rowId === ball.rowId && b.ticketId !== ball.ticketId && b.state === "merged").length;
