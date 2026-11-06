import { branchColor } from "./linie-color";
import { list, rec, str } from "./view-common";

/**
 * Editor Linie (docs/navrhy/2026-11-06-linie-editor-a-vynuceni.md §3, §6): odpověď `GET /board` na bezpečný pohled
 * a rozložení řádků a kuliček. Čas běží zleva doprava na společné ose, řádek = svislá pozice. Čistá geometrie bez Reactu.
 */
export type RowType = "main" | "develop" | "items" | "work" | "experiment" | "fix";
export type BallState = "open" | "awaiting_checks" | "blocked" | "deferred" | "accepted_unmerged" | "merged" | "stale";
export type LinkKind = "follows" | "planned" | "merged";
/** `auto` = řádek odvozený z větve bez ručního záznamu, `planned` = ruční řádek bez větve. `git` = řádek odvozený ze skutečné větve bez ticketu (jen ke čtení), `ahead` = commity před rodičem. */
export type BoardRow = { id: string; name: string; type: RowType; branch: string; baseBranch: string; baseSha: string; target: string; collapsed: boolean; fixed: boolean; git: boolean; ahead: number; parent: string; depth: number; auto: boolean; planned: boolean };
export type BoardBall = {
  ticketId: string; mark: string; rowId: string; title: string; state: BallState; stateLabel: string; branch: string; headSha7: string;
  createdAt: string; mergedAt: string; counts: { commits: number; prs: number; merges: number }; links: { to: string; kind: LinkKind }[];
};
export type Board = { rows: BoardRow[]; balls: BoardBall[]; mapping: { main: string; develop: string }; realMerges: { sha: string; target: string; at: string; title: string }[] };

/** Výplň kuličky: plná = začleněno, s prstencem = hotovo nezačleněno, prázdná = otevřeno, tečka = ověření, červený střed = blok. */
export type Fill = "merged" | "done" | "open" | "verify" | "blocked" | "parked" | "stale";
export const FILL: Record<BallState, Fill> = { merged: "merged", accepted_unmerged: "done", open: "open", awaiting_checks: "verify", blocked: "blocked", deferred: "parked", stale: "stale" };
export const STATE_LABEL: Record<BallState, string> = {
  merged: "začleněno", accepted_unmerged: "hotovo, ještě nezačleněno", open: "otevřeno", awaiting_checks: "čeká na ověření",
  blocked: "blokováno", deferred: "odloženo", stale: "zastaralé přijetí",
};
export const TYPE_LABEL: Record<RowType, string> = { main: "pevný", develop: "pevný", items: "univerzální díl", work: "práce", experiment: "experiment", fix: "oprava" };

const TYPES = Object.keys(TYPE_LABEL) as RowType[];
const STATES = Object.keys(FILL) as BallState[];
const KINDS: LinkKind[] = ["follows", "planned", "merged"];
const num = (value: unknown) => (typeof value === "number" && Number.isFinite(value) ? value : 0);
const pick = <T extends string>(value: unknown, allowed: T[], fallback: T): T => (allowed.includes(value as T) ? (value as T) : fallback);

export function boardView(raw: unknown): Board {
  const root = rec(raw);
  const mapping = { main: str(rec(root.mapping).main) || "main", develop: str(rec(root.mapping).develop) || "develop" };
  const rows: BoardRow[] = list(root.rows).map((item) => {
    const r = rec(item);
    const type = pick(r.type === "topic" ? "items" : r.type, TYPES, "work"); // topic zanikl, čte se jako items
    return { id: str(r.id), name: str(r.name), type, branch: str(r.branch), baseBranch: str(rec(r.base).branch), baseSha: str(rec(r.base).sha),
      target: str(r.target), collapsed: r.collapsed === true, fixed: r.fixed === true || type === "main" || type === "develop", git: r.git === true, ahead: num(r.ahead), parent: str(r.parent), depth: num(r.depth), auto: r.auto === true, planned: r.planned === true };
  }).filter((row) => row.id);
  const balls: BoardBall[] = list(root.balls).map((item) => {
    const b = rec(item), c = rec(b.counts);
    const state = pick(b.state, STATES, "open");
    return {
      ticketId: str(b.ticketId), mark: str(b.mark), rowId: str(b.rowId), title: str(b.title), state, stateLabel: str(b.stateLabel) || STATE_LABEL[state],
      branch: str(b.branch), headSha7: str(b.headSha7), createdAt: str(b.createdAt), mergedAt: str(b.mergedAt),
      counts: { commits: num(c.commits), prs: num(c.prs), merges: num(c.merges) },
      links: list(b.links).map((link) => ({ to: str(rec(link).to), kind: pick(rec(link).kind, KINDS, "follows") })).filter((link) => link.to),
    };
  }).filter((ball) => ball.ticketId);
  const realMerges = list(root.realMerges).map((item) => ({ sha: str(rec(item).sha), target: str(rec(item).target), at: str(rec(item).at), title: str(rec(item).title) }));
  return { rows, balls, mapping, realMerges };
}

export type Point = { x: number; y: number };
export type Hover = { mark: string; title: string; state: string; created: string; merged: string; counts: string; branch: string };
export type LaidRow = BoardRow & { top: number; height: number; y: number; color: string; branchText: string; mappingText: string };
/** `toColor` = barva řádku, kam se kulička začlení (plán nebo merge), jinak vlastní barva; kreslí se jako vnitřní puntík. */
export type LaidBall = { ticketId: string; rowId: string; title: string; label: string; stateLabel: string; fill: Fill; x: number; y: number; color: string; toColor: string; hover: Hover };
/** `openEnd` = cíl plánu bez kuličky: kreslí se přerušovaný kroužek. Bod merge má jen `merged`. Gradient vede od `fromColor` k `toColor`. */
export type LaidLink = { kind: LinkKind; from: Point; to: Point; fromColor: string; toColor: string; openEnd: boolean };
export type LaidMerge = Point & { sha7: string; title: string; color: string };
export type BoardLayout = { width: number; height: number; rows: LaidRow[]; balls: LaidBall[]; links: LaidLink[]; merges: LaidMerge[]; ticks: { x: number; text: string }[] };

/** Řádek s kuličkami nese čtyři řádky textu, sbalený dva, tenký (bez kuliček) jen název; výška je musí pojmout celé. */
export const ROW_OPEN = 96;
export const ROW_FOLDED = 52;
export const ROW_THIN = 36;
export const PAD = 70;
export const SPAN = 820;
export const MIN_GAP = 140;
export const PLAN_DX = 110;
const TITLE_MAX = 22;

export const clip = (text: string, max = TITLE_MAX) => (text.length > max ? `${text.slice(0, max - 1)}…` : text);
export function when(iso: string): string {
  const d = new Date(iso);
  if (!iso || Number.isNaN(d.getTime())) return "—";
  return `${d.getDate()}. ${d.getMonth() + 1}. ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}
const day = (iso: string) => { const d = new Date(iso); return `${d.getDate()}. ${d.getMonth() + 1}.`; };
const time = (iso: string) => { const t = Date.parse(iso); return Number.isNaN(t) ? null : t; };

/** `span` = šířka časové osy; volající ji odvodí z šířky plátna, aby osa vyplnila obrazovku (nejméně SPAN). */
export function layoutBoard(board: Board, span = SPAN): BoardLayout {
  const ok = (t: number | null): t is number => t !== null;
  const ballTimes = board.balls.flatMap((b) => [b.createdAt, b.mergedAt]).map(time).filter(ok);
  const times = [...ballTimes, ...board.realMerges.map((m) => m.at).map(time).filter(ok)];
  // Osa začíná prvním dnem s kuličkou; starší skutečné merge leží vlevo od osy a nekreslí se.
  const min = Math.min(...(ballTimes.length ? ballTimes : times)), max = Math.max(...times);
  const xOf = (iso: string) => { const t = time(iso); return t === null ? PAD : PAD + (max > min ? ((t - min) / (max - min)) * span : span / 2); };

  let top = 0;
  const withBalls = new Set(board.balls.map((ball) => ball.rowId));
  const rows: LaidRow[] = board.rows.map((row) => {
    const height = row.collapsed ? ROW_FOLDED : withBalls.has(row.id) ? ROW_OPEN : ROW_THIN;
    const laid = {
      ...row, top, height, y: top + height / 2, color: branchColor(row.branch || row.name, board.rows),
      branchText: row.git ? `větev: ${row.branch} · ${row.ahead} před ${row.baseBranch} · bez úkolu` : row.branch ? `větev: ${row.branch}` : row.fixed ? "větve items/<díl>" : "bez větve",
      mappingText: !row.fixed ? "" : row.type === "items" ? "cíl: develop nebo feat větev, kde je díl potřeba" : `mapování: ${row.name} → ${row.branch || (row.type === "main" ? board.mapping.main : board.mapping.develop)}`,
    };
    top += height;
    return laid;
  });
  const rowById = new Map(rows.map((row) => [row.id, row]));
  const ballRow = new Map(board.balls.map((ball) => [ball.ticketId, ball.rowId]));
  const targetColor = (ball: BoardBall, own: string) => {
    const out = ball.links.find((link) => link.kind !== "follows");
    return (out && rowById.get(ballRow.get(out.to) ?? out.to)?.color) || own;
  };

  // Čas určuje pořadí; kuličky téhož řádku se rozestoupí aspoň o MIN_GAP, aby se popisky nepřekryly.
  const lastX = new Map<string, number>();
  const balls: LaidBall[] = [];
  for (const ball of [...board.balls].sort((a, b) => (time(a.createdAt) ?? 0) - (time(b.createdAt) ?? 0))) {
    const row = rowById.get(ball.rowId);
    if (!row || row.collapsed) continue;
    const x = Math.max(xOf(ball.createdAt), (lastX.get(row.id) ?? -Infinity) + MIN_GAP);
    lastX.set(row.id, x);
    balls.push({
      ticketId: ball.ticketId, rowId: row.id, title: ball.title, label: clip(ball.title), stateLabel: ball.stateLabel, fill: FILL[ball.state], x, y: row.y, color: row.color, toColor: targetColor(ball, row.color),
      hover: { mark: ball.mark, title: ball.title, state: ball.stateLabel, created: when(ball.createdAt), merged: ball.mergedAt ? when(ball.mergedAt) : "—",
        counts: `${ball.counts.commits} | ${ball.counts.prs} | ${ball.counts.merges}`, branch: ball.branch ? `${ball.branch} @ ${ball.headSha7 || "—"}` : "bez větve" },
    });
  }
  const laidById = new Map(balls.map((ball) => [ball.ticketId, ball]));

  const links: LaidLink[] = [];
  for (const ball of board.balls) {
    const from = laidById.get(ball.ticketId);
    if (!from) continue;
    for (const link of ball.links) {
      const target = laidById.get(link.to);
      const row = rowById.get(link.to);
      if (target) { links.push({ kind: link.kind, from, to: target, fromColor: from.color, toColor: target.color, openEnd: false }); continue; }
      if (!row || row.collapsed) continue;
      const x = link.kind === "merged" ? Math.max(xOf(ball.mergedAt), from.x + 30) : from.x + PLAN_DX;
      links.push({ kind: link.kind, from, to: { x, y: row.y }, fromColor: from.color, toColor: row.color, openEnd: link.kind === "planned" });
    }
  }

  const byBranch = new Map(rows.map((row) => [row.branch, row]));
  const merges = board.realMerges.flatMap((m) => {
    const row = byBranch.get(m.target);
    return row && !row.collapsed && time(m.at) !== null && xOf(m.at) >= PAD ? [{ x: xOf(m.at), y: row.y, sha7: m.sha.slice(0, 7), title: m.title, color: row.color }] : [];
  });

  const seen = new Set<string>();
  const ticks = board.balls.flatMap((b) => {
    if (time(b.createdAt) === null || seen.has(day(b.createdAt))) return [];
    seen.add(day(b.createdAt));
    return [{ x: xOf(b.createdAt), text: day(b.createdAt) }];
  });
  const width = Math.max(PAD + span, ...balls.map((b) => b.x), ...links.map((l) => l.to.x), ...merges.map((m) => m.x)) + PAD;
  return { width, height: top, rows, balls, links, merges, ticks };
}

const LEGEND: { fill: Fill; state: BallState }[] = [
  { fill: "merged", state: "merged" }, { fill: "done", state: "accepted_unmerged" }, { fill: "open", state: "open" }, { fill: "verify", state: "awaiting_checks" },
  { fill: "blocked", state: "blocked" }, { fill: "parked", state: "deferred" }, { fill: "stale", state: "stale" },
];

/** Legenda dole: každá výplň s textem a počtem kuliček; plán = počet plánovaných spojnic. */
export function legend(board: Board): { fill: Fill | "plan"; text: string; count: number }[] {
  return [
    ...LEGEND.map(({ fill, state }) => ({ fill, text: STATE_LABEL[state], count: board.balls.filter((b) => b.state === state).length })),
    { fill: "plan" as const, text: "plán", count: board.balls.reduce((sum, b) => sum + b.links.filter((l) => l.kind === "planned").length, 0) },
  ];
}

/** Věta Pletora „kde pracujeme“ ze stejných dat, jaká vidí člověk. */
export function pletorSentence(board: Board): string {
  const rowName = new Map(board.rows.map((row) => [row.id, row.name]));
  const having = (states: BallState[]) => board.balls.filter((b) => states.includes(b.state));
  const working = having(["open", "awaiting_checks", "stale"]).map((b) => `${b.title} v řádku ${rowName.get(b.rowId) ?? b.rowId}${b.state === "open" ? "" : ` (${b.stateLabel})`}`);
  const done = having(["accepted_unmerged"]).map((b) => b.title);
  const blocked = having(["blocked"]).map((b) => b.title);
  const parts = [
    working.length ? `Pracujeme na ${working.join(", ")}` : "Nic se právě nevyvíjí",
    ...(done.length ? [`hotovo a čeká na začlenění: ${done.join(", ")}`] : []),
    ...(blocked.length ? [`blokováno: ${blocked.join(", ")}`] : []),
  ];
  return `${parts.join("; ")}.`;
}
