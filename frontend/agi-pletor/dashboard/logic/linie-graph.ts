import { shortSha, type LinieLane } from "./linie-view";

/**
 * Graf Linie jako vodorovný git-flow: linie větví pod sebou (main nahoře), commity všech větví ve sloupcích podle času
 * (nejstarší vlevo), odbočení a návrat větve obloukem, štítky přijetí, náhledu a PR za špičkou. Čistá geometrie bez Reactu.
 */
export type Point = { x: number; y: number };
export type GraphLane = { name: string; role: string; y: number; color: string; x1: number; x2: number; label: string };
/** `above` střídá popisek nad a pod bodem, aby se sousední tituly nepřekryly. */
export type GraphDot = { sha: string; sha7: string; title: string; x: number; y: number; lane: string; above: boolean };
export type GraphLink = { from: Point; to: Point; kind: "fork" | "merge"; color: string };
export type BadgeKind = "accepted" | "stale" | "preview" | "pr";
export type GraphBadge = { x: number; y: number; kind: BadgeKind; text: string; lane: string };
export type GraphLayout = { width: number; height: number; lanes: GraphLane[]; dots: GraphDot[]; links: GraphLink[]; badges: GraphBadge[] };

export const COL = 72;
export const LANE_GAP = 110;
export const HEAD = 190; // sloupec hlaviček větví vlevo
const PAD_Y = 60;
const LABEL_DX = 14;
const TITLE_MAX = 20;
/** Odhad šířky znaku 11px mono; stačí na šířku SVG a skládání štítků vedle sebe. */
export const textWidth = (text: string) => Math.ceil(text.length * 6.6);
export const badgeWidth = (text: string) => textWidth(text) + 16;

const COLORS: Record<string, string> = { main: "#4ade80", develop: "#60a5fa", experiment: "#c084fc" };
export const laneColor = (role: string) => COLORS[role] ?? "#fb923c";

export function laneSubtitle(lane: { name: string; role: string }): string {
  if (lane.role === "main") return "Stabilní přijaté vydání";
  if (lane.role === "develop") return "Společné ověření";
  return `Téma: ${lane.name.slice(lane.name.indexOf("/") + 1)}`;
}

export const clip = (text: string, max = TITLE_MAX) => (text.length > max ? `${text.slice(0, max - 1)}…` : text);

export function layoutGraph(lanes: LinieLane[]): GraphLayout {
  const order = new Map(lanes.map((lane, index) => [lane.name, index]));
  const seen = new Set<string>();
  // Commit sdílený víc liniemi patří první (main před develop před tématy).
  const columns = lanes.flatMap((lane, index) => lane.commits.map((commit) => ({ commit, lane, index })))
    .filter(({ commit }) => !seen.has(commit.sha) && seen.add(commit.sha))
    .sort((a, b) => a.commit.at.localeCompare(b.commit.at) || a.index - b.index);
  const yOf = (name: string) => PAD_Y + (order.get(name) ?? 0) * LANE_GAP;
  const dots: GraphDot[] = columns.map(({ commit, lane }, column) => ({
    sha: commit.sha, sha7: commit.sha7, title: clip(commit.title), x: HEAD + COL / 2 + column * COL, y: yOf(lane.name), lane: lane.name, above: column % 2 === 0,
  }));
  const bySha = new Map(dots.map((dot) => [dot.sha, dot]));
  const right = HEAD + columns.length * COL + 40;

  const graphLanes: GraphLane[] = lanes.map((lane) => {
    const own = dots.filter((dot) => dot.lane === lane.name);
    const full = lane.role === "main" || lane.role === "develop" || !own.length;
    return {
      name: lane.name, role: lane.role, y: yOf(lane.name), color: laneColor(lane.role), label: laneSubtitle(lane),
      x1: full ? HEAD : own[0].x, x2: full ? right - 16 : own[own.length - 1].x,
    };
  });

  const links: GraphLink[] = [];
  for (const lane of lanes) {
    const first = dots.find((dot) => dot.lane === lane.name);
    if (!lane.parent || !order.has(lane.parent) || !first) continue;
    const base = bySha.get(lane.base);
    const from = base && base.lane === lane.parent ? { x: base.x, y: base.y } : { x: HEAD, y: yOf(lane.parent) };
    links.push({ from, to: { x: first.x, y: first.y }, kind: "fork", color: laneColor(lane.role) });
  }
  for (const { commit, lane } of columns) {
    const source = bySha.get(commit.parents[1] ?? "");
    const target = bySha.get(commit.sha)!;
    if (!source || source.lane === lane.name) continue;
    const sourceRole = lanes[order.get(source.lane)!].role;
    links.push({ from: { x: source.x, y: source.y }, to: { x: target.x, y: target.y }, kind: "merge", color: laneColor(sourceRole) });
  }

  // Štítky sedí na linii za špičkou větve, vedle sebe; za špičkou už žádný commit té větve není.
  const badges: GraphBadge[] = [];
  for (const lane of lanes) {
    const own = dots.filter((dot) => dot.lane === lane.name);
    const tip = own[own.length - 1];
    let x = (tip ? tip.x : HEAD) + LABEL_DX + 8;
    const y = yOf(lane.name);
    const add = (kind: BadgeKind, text: string) => { badges.push({ x, y, kind, text, lane: lane.name }); x += badgeWidth(text) + 22; }; // +22: mezera a ikona, kterou kreslí komponenta
    const a = lane.acceptance;
    if (a?.valid) add("accepted", `PR: přijato do ${a.target}`);
    else if (a) add("stale", `přijetí zastaralé (${shortSha(a.sha)})`);
    if (lane.preview?.state === "running") add("preview", "Náhled (ukázka v aplikaci)");
    if (lane.pr) add("pr", `PR #${lane.pr.number} ${lane.pr.state}`);
  }

  const width = Math.max(right, ...badges.map((badge) => badge.x + badgeWidth(badge.text) + 20));
  const height = PAD_Y + Math.max(lanes.length - 1, 0) * LANE_GAP + PAD_Y;
  return { width, height, lanes: graphLanes, dots, links, badges };
}
