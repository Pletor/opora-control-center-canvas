import { branchColor } from "./linie-color";
import { commitTail, glyphOf, type Glyph } from "./linie-glyph";
import { LANE, laneRows, placeLanes, placeTags, type LaidLane, type LaidTag } from "./linie-marks";
import { placeLabels, type Labels } from "./linie-labels";
import { judgementOf, snapshotOf, type Judgement, type Snapshot, type SummaryKey } from "./linie-summary";
import { PAD, ticks as axisTicks, xOf as scaleX } from "./linie-zoom";
import { list, rec, str } from "./view-common";

export { PAD, LANE };
export type { LaidLane, LaidTag };

/**
 * Editor Linie (docs/navrhy/2026-11-06-linie-editor-a-vynuceni.md §3, §6; rebrand §5, §6): odpověď `GET /board` na
 * bezpečný pohled a rozložení řádků a kuliček. Čas běží zleva doprava na společné ose (`linie-zoom.ts`), řádek = svislá
 * pozice; kulička leží vždy přesně na svém čase, kolize řeší jen popisky (`linie-labels.ts`). Čistá geometrie bez Reactu.
 * Skutečná data L7c (tagy, worktree s vazbou relace, nasazení s původem, opuštěné commity, PR s posledním známým
 * stavem) se čtou z boardu; co board nenese, se nekreslí.
 */
export type RowType = "main" | "develop" | "items" | "work" | "experiment" | "fix" | "dir" | "plan";
export type BallState = "open" | "awaiting_checks" | "blocked" | "deferred" | "accepted_unmerged" | "merged" | "stale";
export type LinkKind = "follows" | "planned" | "merged";
/** `auto` = řádek odvozený z větve bez ručního záznamu, `planned` = ruční řádek bez větve. `git` = řádek odvozený ze skutečné větve bez ticketu (jen ke čtení), `ahead` = commity před rodičem. `dir`/`plan` = řádky pohledu „podle plánu“ (`parent` je id řádku směru). */
export type BoardRow = { id: string; name: string; type: RowType; branch: string; baseBranch: string; baseSha: string; target: string; collapsed: boolean; fixed: boolean; git: boolean; ahead: number; parent: string; depth: number; auto: boolean; planned: boolean; cardId: string };
export type BallCommit = { sha: string; sha7: string; title: string; at: string; abandoned: { why: string; at: string; by: string } | null };
/** Poslední známý PR; `unconfirmed` = z paměti po výpadku GitHubu (stav je poslední známý, ne ověřený). */
export type BallPr = { number: string; state: string; url: string; unconfirmed: boolean };
export type BoardBall = {
  ticketId: string; mark: string; rowId: string; title: string; state: BallState; stateLabel: string; branch: string; headSha7: string;
  createdAt: string; mergedAt: string; counts: { commits: number; prs: number; merges: number }; links: { to: string; kind: LinkKind }[];
  /** Souhrn, osy a akce z jednoho vyhodnocení backendu (§2a); `openPr` jen z `pr.state`, nikdy z počtu. */
  judgement: Judgement; openPr: boolean; pr: BallPr | null; commits: BallCommit[];
  /** Fronty odpovědnosti, do kterých kulička patří (`humanDecisions`, `ticketsTodo`, `officeTasks`, `gitQueue`). */
  queues: string[];
};
export type Tag = { name: string; sha: string; at: string };
export type WorktreeBinding = { ticketId: string; agent: string; from: string; to: string; live: boolean };
export type Worktree = { path: string; branch: string; sha: string; binding: WorktreeBinding | null };
export type DeployEnv = { env: string; sha: string; at: string; origin: string };
/** Počty front z boardu; `null` = zdroj nedostupný (graf plánu nejde přečíst). */
export type BoardQueues = { plansWaiting: number | null; ticketsTodo: number | null; humanDecisions: number | null; officeTasks: number | null; gitQueue: number | null };
export type Board = {
  rows: BoardRow[]; balls: BoardBall[]; mapping: { main: string; develop: string }; realMerges: { sha: string; target: string; at: string; title: string }[];
  snapshot: Snapshot | null; group: "branch" | "plan"; tags: Tag[]; worktrees: Worktree[]; deploy: DeployEnv[]; queues: BoardQueues | null;
};

export const STATE_LABEL: Record<BallState, string> = {
  merged: "začleněno", accepted_unmerged: "hotovo, ještě nezačleněno", open: "otevřeno", awaiting_checks: "čeká na ověření",
  blocked: "blokováno", deferred: "odloženo", stale: "zastaralé přijetí",
};
export const TYPE_LABEL: Record<RowType, string> = { main: "pevný", develop: "pevný", items: "univerzální díl", work: "práce", experiment: "experiment", fix: "oprava", dir: "plátno 2", plan: "plátno 3" };

const TYPES = Object.keys(TYPE_LABEL) as RowType[];
const STATES = Object.keys(STATE_LABEL) as BallState[];
const KINDS: LinkKind[] = ["follows", "planned", "merged"];
const QUEUE_KEYS = ["plansWaiting", "ticketsTodo", "humanDecisions", "officeTasks", "gitQueue"] as const;
const num = (value: unknown) => (typeof value === "number" && Number.isFinite(value) ? value : 0);
const count = (value: unknown) => (typeof value === "number" && Number.isFinite(value) ? value : null);
const pick = <T extends string>(value: unknown, allowed: T[], fallback: T): T => (allowed.includes(value as T) ? (value as T) : fallback);

/** PR z boardu (`pr`), náhradou první z dřívějšího `prs[]`; stav velkými písmeny jako GitHub (`OPEN`, `MERGED`, `CLOSED`). */
function prOf(b: Record<string, unknown>): BallPr | null {
  const raw = rec(b.pr ?? list(b.prs)[0]);
  if (!str(raw.number)) return null;
  return { number: str(raw.number), state: str(raw.state).toUpperCase(), url: str(raw.url), unconfirmed: raw.unconfirmed === true };
}

export function boardView(raw: unknown): Board {
  const root = rec(raw);
  const mapping = { main: str(rec(root.mapping).main) || "main", develop: str(rec(root.mapping).develop) || "develop" };
  const rows: BoardRow[] = list(root.rows).map((item) => {
    const r = rec(item);
    const type = pick(r.type === "topic" ? "items" : r.type, TYPES, "work"); // topic zanikl, čte se jako items
    return { id: str(r.id), name: str(r.name), type, branch: str(r.branch), baseBranch: str(rec(r.base).branch), baseSha: str(rec(r.base).sha),
      target: str(r.target), collapsed: r.collapsed === true, fixed: r.fixed === true || type === "main" || type === "develop" || type === "dir", git: r.git === true, ahead: num(r.ahead),
      parent: str(r.parent), depth: num(r.depth), auto: r.auto === true, planned: r.planned === true, cardId: str(r.cardId) };
  }).filter((row) => row.id);
  const balls: BoardBall[] = list(root.balls).map((item) => {
    const b = rec(item), c = rec(b.counts);
    const state = pick(b.state, STATES, "open");
    const pr = prOf(b);
    return {
      ticketId: str(b.ticketId), mark: str(b.mark), rowId: str(b.rowId), title: str(b.title), state, stateLabel: str(b.stateLabel) || STATE_LABEL[state],
      branch: str(b.branch), headSha7: str(b.headSha7), createdAt: str(b.createdAt), mergedAt: str(b.mergedAt),
      counts: { commits: num(c.commits), prs: num(c.prs), merges: num(c.merges) },
      links: list(b.links).map((link) => ({ to: str(rec(link).to), kind: pick(rec(link).kind, KINDS, "follows") })).filter((link) => link.to),
      judgement: judgementOf(b), openPr: pr?.state === "OPEN", pr,
      commits: list(b.commits).map((entry) => {
        const commit = rec(entry), gone = rec(commit.abandoned);
        return { sha: str(commit.sha), sha7: str(commit.sha7) || str(commit.sha).slice(0, 7), title: str(commit.title), at: str(commit.at),
          abandoned: Object.keys(gone).length ? { why: str(gone.why), at: str(gone.at), by: str(gone.by) } : null };
      }).filter((commit) => commit.sha),
      queues: list(b.queues).map(str).filter(Boolean),
    };
  }).filter((ball) => ball.ticketId);
  const realMerges = list(root.realMerges).map((item) => ({ sha: str(rec(item).sha), target: str(rec(item).target), at: str(rec(item).at), title: str(rec(item).title) }));
  const tags = list(root.tags).map((item) => ({ name: str(rec(item).name), sha: str(rec(item).sha), at: str(rec(item).at) })).filter((tag) => tag.name && tag.sha);
  const worktrees = list(root.worktrees).map((item) => {
    const w = rec(item), bind = rec(w.binding);
    return { path: str(w.path), branch: str(w.branch), sha: str(w.sha),
      binding: Object.keys(bind).length ? { ticketId: str(bind.ticketId), agent: str(bind.agent), from: str(bind.from), to: str(bind.to), live: bind.live === true } : null };
  }).filter((w) => w.path);
  const deploy = Object.entries(rec(rec(root.deploy).envs)).map(([env, value]) => ({ env, sha: str(rec(value).sha), at: str(rec(value).at), origin: str(rec(value).origin) })).filter((e) => e.sha);
  const q = rec(root.queues);
  const queues = Object.keys(q).length ? (Object.fromEntries(QUEUE_KEYS.map((key) => [key, count(q[key])])) as BoardQueues) : null;
  return { rows, balls, mapping, realMerges, snapshot: snapshotOf(root.snapshot), group: root.group === "plan" ? "plan" : "branch", tags, worktrees, deploy, queues };
}

export type Point = { x: number; y: number };
export type Hover = { mark: string; title: string; state: string; created: string; merged: string; counts: string; branch: string; reason: string; next: string; target: string };
/** `y` = osa řádku (`top + base/2`), pruhy worktree leží pod ní; `ind` = odsazení názvu podle hloubky stromu; `meta` =
 * druhý řádek ve sloupci názvů (jen u řádku s kuličkou). */
export type LaidRow = BoardRow & { top: number; height: number; y: number; color: string; meta: string; ind: number; lanes: number };
/** `toColor` = barva řádku, kam se kulička začlení (plán nebo merge), jinak vlastní barva; kreslí se jako vnitřní puntík.
 * `stateLabel` = souhrn s příponou commitů („ · 2 c · 1 ✕“), `glyph` = tvar ze `summary.key` (`linie-glyph.ts`). */
export type LaidBall = { ticketId: string; rowId: string; title: string; label: string; stateLabel: string; key: SummaryKey; glyph: Glyph; x: number; y: number; color: string; toColor: string; hover: Hover };
/** Pilulka PR na spojnici: text se stavem; `unverified` = poslední známý stav bez potvrzení GitHubem (čárkovaný rám). */
export type LaidPr = { text: string; state: string; unverified: boolean; url: string; at: Point };
/** `openEnd` = cíl plánu bez kuličky: kreslí se přerušovaný kroužek. Bod merge má jen `merged`. Gradient vede od `fromColor` k `toColor`.
 * `toId` = id cíle (stálý klíč, aby se merge při přiblížení nekreslil znovu), `label` = popisek plánu („plán → cíl“, s „blokováno ·“). */
export type LaidLink = { kind: LinkKind; toId: string; from: Point; to: Point; fromColor: string; toColor: string; openEnd: boolean; ticketId: string; pr: LaidPr | null; label: string };
export type LaidMerge = Point & { sha7: string; title: string; color: string };
/** Commit (kostka) na řádku své kuličky; `abandoned` = opuštěný (✕ s odbočkou), do cíle nejde. `sha` = plná revize pro
 * detail commitu, `color` = barva cíle u začleněné kuličky, jinak řádku; `mark`/`ball`/`agent` nese tip. */
export type LaidCommit = Point & { ticketId: string; sha: string; ref: string; at: string; title: string; abandoned: boolean; color: string; mark: string; ball: string; agent: string };
/** Čára práce od vzniku kuličky k poslednímu commitu; `wip` čárkovaně, odevzdaná nebo začleněná plně. */
export type LaidWork = { ticketId: string; x1: number; x2: number; y: number; color: string; wip: boolean };
export type BoardLayout = {
  width: number; height: number; rows: LaidRow[]; balls: LaidBall[]; links: LaidLink[]; merges: LaidMerge[]; commits: LaidCommit[];
  works: LaidWork[]; lanes: LaidLane[]; tags: LaidTag[]; labels: Labels;
  ticks: { x: number; text: string }[]; t0: number; t1: number; k: number; now: number | null;
};

/** Výšky řádku z prototypu Linie v3: s kuličkou 78 (+28 za každé obsazené druhé patro), sbalený 46, tenký 36. */
export const ROW_OPEN = 78;
export const ROW_FOLDED = 46;
export const ROW_THIN = 36;
export const L2 = 28;
export const SPAN = 820;
export const PLAN_DX = 110;
/** Pilulka PR leží u cíle merge oblouku (65 %), ne ve středu, aby nepřekrývala popisek zdrojové kuličky. */
export const PR_AT = 0.65;
const TITLE_MAX = 34;
const PR_STATE: Record<string, string> = { OPEN: "otevřen", MERGED: "sloučen", CLOSED: "zavřen", APPROVED: "schválen" };

export const clip = (text: string, max = TITLE_MAX) => (text.length > max ? `${text.slice(0, max - 1)}…` : text);
export function when(iso: string): string {
  const d = new Date(iso);
  if (!iso || Number.isNaN(d.getTime())) return "—";
  return `${d.getDate()}. ${d.getMonth() + 1}. ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}
const time = (iso: string) => { const t = Date.parse(iso); return Number.isNaN(t) ? null : t; };

/** Časový rozsah osy: od první kuličky po poslední čas (a `now`, je-li dané); starší merge leží vlevo a nekreslí se. */
export function timeRange(board: Board, now?: number): { t0: number; t1: number } {
  const ok = (t: number | null): t is number => t !== null;
  const ballTimes = board.balls.flatMap((b) => [b.createdAt, b.mergedAt]).map(time).filter(ok);
  const times = [...ballTimes, ...board.realMerges.map((m) => m.at).map(time).filter(ok), ...(now === undefined ? [] : [now])];
  if (!times.length) return { t0: now ?? 0, t1: now ?? 0 };
  return { t0: Math.min(...(ballTimes.length ? ballTimes : times)), t1: Math.max(...times) };
}

/** Text pilulky PR: číslo a stav; bez potvrzení GitHubem (`unconfirmed` nebo zdroj `prs` neúplný) „neověřeno“. */
export function prPill(ball: BoardBall): Omit<LaidPr, "at"> | null {
  if (!ball.pr) return null;
  const unverified = ball.pr.unconfirmed || ball.judgement.incomplete.includes("prs");
  return { text: `PR #${ball.pr.number} · ${unverified ? "neověřeno" : PR_STATE[ball.pr.state] ?? ball.pr.state.toLowerCase()}`, state: ball.pr.state.toLowerCase(), unverified, url: ball.pr.url };
}

/** Druhý řádek názvu (prototyp Linie v3): větev a odkud → kam; experiment se vrací nebo zahodí, items míří tam, kde je díl potřeba. */
function metaOf(row: BoardRow, mapping: Board["mapping"]): string {
  if (row.type === "dir") return "plátno 2 · směr";
  if (row.type === "plan") return "plátno 3 · plán";
  if (row.git) return `větev ${row.branch} · ${row.ahead} před ${row.baseBranch} · bez úkolu`;
  const branch = `větev ${row.branch || (row.type === "items" ? "items/<díl>" : "—")}`;
  const from = row.parent || row.baseBranch || "—";
  if (row.type === "items") return `${branch} · cíl: develop nebo feat, kde je díl potřeba`;
  if (row.fixed) return `${branch} · mapování: ${row.name} → ${row.branch || (row.type === "main" ? mapping.main : mapping.develop)}`;
  if (row.type === "experiment") return `${branch} · fork z ${from} · zpět nebo zahodit`;
  return `${branch} · z ${from} → cíl ${row.target || "zatím neurčeno"}`;
}

/** Commity kuličky: z boardu, náhradou z důkazů `evidence` (kind = commit); sdílí je kostky i přípona popisku. */
const commitsOf = (ball: BoardBall) => ball.commits.length ? ball.commits.map((c) => ({ sha: c.sha, ref: c.sha7, at: c.at, title: c.title, abandoned: !!c.abandoned }))
  : ball.judgement.evidence.filter((e) => e.kind === "commit").map((e) => ({ sha: e.ref, ref: e.ref, at: e.at, title: "", abandoned: false }));

/**
 * `k` = px na ms (stav měřítka z `linie-zoom.ts`); bez něj se osa vejde do SPAN. `now` přidá do rozsahu značku „teď“.
 * `lanes` = řádky, u kterých se kreslí pruhy worktree (vrstva zapnutá, nebo řádek vybrané kuličky); `selected` má
 * přednost při rozdělení popisků.
 */
export function layoutBoard(board: Board, opts: { k?: number; now?: number; lanes?: Set<string>; selected?: string } = {}): BoardLayout {
  const { t0, t1 } = timeRange(board, opts.now);
  const k = opts.k ?? (t1 > t0 ? SPAN / (t1 - t0) : 1);
  const xOf = (iso: string) => { const t = time(iso); return t === null ? PAD : t1 > t0 ? scaleX({ t0, k }, t) : PAD + SPAN / 2; };
  const xAt = (t: number) => (t1 > t0 ? scaleX({ t0, k }, t) : PAD + SPAN / 2);

  const lanesOf = laneRows(board);
  const laneCount = (row: BoardRow) => (!row.collapsed && opts.lanes?.has(row.id) ? (lanesOf.get(row.id)?.length ?? 0) : 0);
  const shownRow = new Map(board.rows.filter((row) => !row.collapsed).map((row) => [row.id, row]));
  const shownBalls = [...board.balls].filter((ball) => shownRow.has(ball.rowId)).sort((a, b) => (time(a.createdAt) ?? 0) - (time(b.createdAt) ?? 0));
  const tailOf = (ball: BoardBall) => (ball.judgement.summary.text || ball.stateLabel) + commitTail(commitsOf(ball));
  // OP-123CD1.3: popisky se rozdělí dřív než řádky, protože obsazené druhé patro zvedá výšku řádku (x závisí jen na čase).
  const labels = placeLabels(shownBalls.map((ball) => ({ ticketId: ball.ticketId, rowId: ball.rowId, x: xOf(ball.createdAt), label: clip(ball.title), stateLabel: tailOf(ball) })),
    opts.selected ?? "", new Set(board.rows.filter((row) => laneCount(row) > 0).map((row) => row.id)));

  let top = 0;
  const withBalls = new Set(shownBalls.map((ball) => ball.rowId));
  const rows: LaidRow[] = board.rows.map((row) => {
    const lanes = laneCount(row);
    // Bez pruhů se druhé patro otevře nad i pod osou (+2·L2), s pruhy jen nad ní (+L2); osa = base/2 se tak nikdy nehne kvůli pruhům.
    const base = row.collapsed ? ROW_FOLDED : withBalls.has(row.id) ? ROW_OPEN + (labels.tier2.has(row.id) ? L2 * (lanes ? 1 : 2) : 0) : ROW_THIN;
    const laid = { ...row, top, height: base + LANE * lanes, y: top + base / 2, lanes, color: branchColor(row.branch || row.name, board.rows),
      ind: 8 + 16 * Math.min(row.depth, 5), meta: metaOf(row, board.mapping) };
    top += laid.height;
    return laid;
  });
  const rowById = new Map(rows.map((row) => [row.id, row]));
  const laidByBranch = new Map(rows.map((row) => [row.branch, row]));
  const ballRow = new Map(board.balls.map((ball) => [ball.ticketId, ball.rowId]));
  const targetColor = (ball: BoardBall, own: string) => {
    const out = ball.links.find((link) => link.kind !== "follows");
    return (out && rowById.get(ballRow.get(out.to) ?? out.to)?.color) || own;
  };

  // Kulička leží přesně na svém čase; žádné rozestupy, které by posouvaly čas (kolize řeší jen popisky).
  const balls: LaidBall[] = shownBalls.map((ball) => {
    const row = rowById.get(ball.rowId)!;
    return {
      ticketId: ball.ticketId, rowId: row.id, title: ball.title, label: clip(ball.title), key: ball.judgement.summary.key,
      stateLabel: tailOf(ball), glyph: glyphOf(ball.judgement.summary.key, ball.judgement), x: xOf(ball.createdAt), y: row.y, color: row.color, toColor: targetColor(ball, row.color),
      hover: { mark: ball.mark, title: ball.title, state: ball.stateLabel, created: when(ball.createdAt), merged: ball.mergedAt ? when(ball.mergedAt) : "—",
        counts: `${ball.counts.commits} | ${ball.counts.prs} | ${ball.counts.merges}`, branch: ball.branch ? `${ball.branch} @ ${ball.headSha7 || "—"}` : "bez větve",
        reason: ball.judgement.summary.reason, next: ball.judgement.summary.next, target: row.target },
    };
  });
  const laidById = new Map(balls.map((ball) => [ball.ticketId, ball]));
  const along = (from: Point, to: Point, f: number): Point => ({ x: from.x + (to.x - from.x) * f, y: from.y + (to.y - from.y) * f });
  const liveCommits = (ball: BoardBall) => commitsOf(ball).filter((c) => !c.abandoned && time(c.at) !== null);

  const links: LaidLink[] = [];
  for (const ball of board.balls) {
    const ballPoint = laidById.get(ball.ticketId);
    if (!ballPoint) continue;
    const live = liveCommits(ball);
    for (const link of ball.links) {
      const target = laidById.get(link.to);
      const row = rowById.get(link.to) ?? (target && rowById.get(target.rowId));
      if (!row || row.collapsed) continue;
      // Plán vychází z posledního živého commitu (jinak z kuličky); merge z kuličky na osu cíle v čase merge.
      const from = link.kind === "planned" && live.length ? { x: Math.max(...live.map((c) => xOf(c.at))), y: ballPoint.y } : { x: ballPoint.x, y: ballPoint.y };
      const mergedAt = ball.mergedAt || ball.judgement.axes?.integration.at || "";
      const to = link.kind === "merged" ? { x: time(mergedAt) !== null ? xOf(mergedAt) : from.x + 30, y: row.y }
        : target ?? { x: from.x + PLAN_DX, y: row.y };
      const pill = link.kind === "follows" ? null : prPill(ball);
      const squash = link.kind === "merged" && ball.judgement.axes?.integration.mode === "squash" ? " · squash" : "";
      const name = (row.branch || row.name).replace(/^feat\//, "");
      links.push({ kind: link.kind, toId: link.to, from, to, fromColor: ballPoint.color, toColor: target ? target.color : row.color, openEnd: !target && link.kind === "planned", ticketId: ball.ticketId,
        pr: pill && { ...pill, text: pill.text + squash, at: along(from, to, link.kind === "merged" ? PR_AT : 0.5) },
        label: link.kind === "planned" ? `${ball.judgement.summary.key === "blocked" ? "blokováno · " : ""}plán → ${name}` : "" });
    }
  }

  const merges = board.realMerges.flatMap((m) => {
    const row = laidByBranch.get(m.target);
    return row && !row.collapsed && time(m.at) !== null && xOf(m.at) >= PAD ? [{ x: xOf(m.at), y: row.y, sha7: m.sha.slice(0, 7), title: m.title, color: row.color }] : [];
  });

  // Autor commitu = agent posledního pokusu; board ho zná jen z vazby worktree na ticket.
  const agentOf = new Map(board.worktrees.flatMap((w) => (w.binding?.agent ? [[w.binding.ticketId, w.binding.agent] as const] : [])));
  const commits: LaidCommit[] = [], works: LaidWork[] = [];
  for (const ball of board.balls) {
    const from = laidById.get(ball.ticketId);
    if (!from) continue;
    const merged = ball.judgement.summary.key === "merged";
    const color = merged ? from.toColor : from.color;
    const timed = commitsOf(ball).filter((c) => time(c.at) !== null);
    commits.push(...timed.map((c) => ({ x: xOf(c.at), y: from.y, ticketId: ball.ticketId, ...c, color, mark: ball.mark, ball: ball.title, agent: agentOf.get(ball.ticketId) ?? "" })));
    const live = liveCommits(ball);
    if (live.length) {
      const submitted = ball.judgement.axes?.work.state === "submitted" || merged;
      works.push({ ticketId: ball.ticketId, x1: from.x, x2: Math.max(...live.map((c) => xOf(c.at))), y: from.y, color, wip: !submitted });
    }
  }

  const geometry = { xOf, xEnd: xAt(t1), rowById, byBranch: laidByBranch };
  const lanes = placeLanes(rows, lanesOf, geometry);
  const tags = placeTags(board, geometry);

  const width = Math.max(t1 > t0 ? scaleX({ t0, k }, t1) : PAD + SPAN, ...balls.map((b) => b.x), ...links.map((l) => l.to.x), ...merges.map((m) => m.x), ...tags.map((t) => t.x)) + PAD;
  return { width, height: top, rows, balls, links, merges, commits, works, lanes, tags, labels, ticks: t1 > t0 ? axisTicks({ t0, k }, t0, t1) : [], t0, t1, k, now: opts.now ?? null };
}
