import type { Board, LaidRow, Worktree } from "./linie-board";

/**
 * Značky nad geometrií kuliček (docs/navrhy/2026-11-06-linie-rebrand.md §5, L7c): pruhy worktree pod osou větve
 * (jméno agenta jen z vazby relace, od–do), tagy a nasazení `env@sha` s původem. Řádek kreslení volí frontend:
 * tag patří commitu kuličky, jinak cíli skutečného merge, jinak main; nasazení řádku cíle začlenění s touž revizí.
 */
/** Pruh worktree pod osou: každý agent jeden pruh. */
export const LANE = 20;
/** Pruh worktree pod osou větve: jméno agenta jen z vazby relace, od–do; bez `to` dosud pracuje. Pruh začíná 14 px za
 * odbočkou z osy (`dIn`); vrácený se vrací na osu (`dOut`) a nese tečku „vrácen“ (`back`). */
export type LaidLane = {
  rowId: string; ticketId: string; agent: string; state: "pracuje" | "vrácen"; x1: number; x2: number; y: number; color: string;
  dIn: string; dOut: string | null; back: { x: number; y: number } | null;
};
const TURN = 14;
/** Svislá značka tagu nebo nasazení (`env@sha`) na řádku; `title` nese původ. */
export type LaidTag = { x: number; y: number; text: string; kind: "tag" | "deploy"; title: string };

type Geometry = { xOf: (iso: string) => number; xEnd: number; rowById: Map<string, LaidRow>; byBranch: Map<string, LaidRow> };
const time = (iso: string) => !Number.isNaN(Date.parse(iso));

/** Worktree s vazbou relace podle řádku kuličky z vazby (náhradou řádku své větve); bez vazby se pruh nekreslí (agent není znám). */
export function laneRows(board: Board): Map<string, Worktree[]> {
  const byBranch = new Map(board.rows.map((row) => [row.branch, row.id]));
  const byTicket = new Map(board.balls.map((ball) => [ball.ticketId, ball.rowId]));
  const found = new Map<string, Worktree[]>();
  for (const w of board.worktrees) {
    const id = w.binding && (byTicket.get(w.binding.ticketId) ?? byBranch.get(w.branch));
    if (id) found.set(id, [...(found.get(id) ?? []), w]);
  }
  return found;
}

export function placeLanes(rows: LaidRow[], lanes: Map<string, Worktree[]>, g: Geometry): LaidLane[] {
  return rows.flatMap((row) => (row.lanes ? lanes.get(row.id) ?? [] : []).map((w, index) => {
    const b = w.binding!;
    const from = g.xOf(b.from), x2 = b.to ? g.xOf(b.to) : g.xEnd;
    const y = row.top + (row.height - LANE * row.lanes) + LANE * index + LANE / 2; // pod osou: osa = base/2, pruhy od base dolů
    return { rowId: row.id, ticketId: b.ticketId, agent: b.agent || "agent", state: b.to ? "vrácen" as const : "pracuje" as const, x1: from + TURN, x2, y, color: row.color,
      dIn: `M${from} ${row.y} L${from + TURN} ${y}`, dOut: b.to ? `M${x2} ${y} L${x2 + TURN} ${row.y}` : null, back: b.to ? { x: x2 + TURN, y: row.y } : null };
  }));
}

export function placeTags(board: Board, g: Geometry): LaidTag[] {
  const main = g.byBranch.get(board.mapping.main);
  const rowOfSha = (sha: string) => {
    const owner = board.balls.find((b) => b.commits.some((c) => c.sha === sha));
    const merged = board.realMerges.find((m) => m.sha === sha);
    // Tag kuličky složené nebo sbalené větve se nekreslí jinde (zůstává jen značka ⊕), proto bez náhrady na main.
    return owner ? g.rowById.get(owner.rowId) : (merged && g.byBranch.get(merged.target)) || main;
  };
  const tags: LaidTag[] = board.tags.flatMap((tag) => {
    const row = rowOfSha(tag.sha);
    return row && !row.collapsed && time(tag.at) ? [{ x: g.xOf(tag.at), y: row.y, text: tag.name, kind: "tag" as const, title: `tag ${tag.name} na ${tag.sha.slice(0, 7)} · git` }] : [];
  });
  for (const e of board.deploy) {
    const owner = board.balls.find((b) => b.judgement.axes?.integration.sha && e.sha.startsWith(b.judgement.axes.integration.sha));
    const row = (owner && g.byBranch.get(owner.judgement.axes!.integration.target)) || rowOfSha(e.sha);
    if (row && !row.collapsed && time(e.at)) {
      tags.push({ x: g.xOf(e.at), y: row.y, text: `${e.env}@${e.sha.slice(0, 7)}`, kind: "deploy", title: e.origin === "environment" ? "nasazení potvrzené prostředím" : "nasazení hlášené člověkem" });
    }
  }
  return tags;
}
