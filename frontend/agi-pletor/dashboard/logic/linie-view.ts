import { list, rec, str, unavailable, type Raw } from "./view-common";

/** Linie (docs/navrhy/2026-11-06-velin-git-linie.md §5): odpovědi `GET /api/pletor/linie/graph` a `/diff` na bezpečný pohled. */
export type LiniePreview = { slug: string; state: string; url: string; sha: string };
export type LinieAcceptance = { sha: string; target: string; at: string; note: string; valid: boolean };
export type LinieCommit = { sha: string; sha7: string; title: string; at: string; parents: string[] };
export type LiniePr = { number: number; state: string; url: string; base: string };
export type LinieLane = {
  name: string; role: string; parent: string; sha: string; remote: string; base: string;
  commits: LinieCommit[]; acceptance: LinieAcceptance | null; preview: LiniePreview | null; pr: LiniePr | null;
};
export type LinieGraphView = {
  lanes: LinieLane[];
  active: string;
  server: { branch: string; sha: string; dirty: boolean };
  deployed: { sha: string; at: string } | null;
  enforcement: string;
  problem: string;
};
export type DiffView = { commits: { sha7: string; title: string }[]; stat: string; files: number };

const num = (value: unknown) => (typeof value === "number" && Number.isFinite(value) ? value : 0);
/** Sekce bez dat nebo s `{error}` je null; problém se hlásí zvlášť v `problem`. */
const section = (value: unknown): Raw | null => (value && typeof value === "object" && !Array.isArray(value) && !("error" in value) ? (value as Raw) : null);

export const shortSha = (sha: string) => sha.slice(0, 7);

function acceptanceOf(value: unknown, head: string): LinieAcceptance | null {
  const a = section(value);
  if (!a) return null;
  const sha = str(a.sha);
  return { sha, target: str(a.target), at: str(a.at), note: str(a.note), valid: typeof a.valid === "boolean" ? a.valid : sha === head };
}

function previewOf(value: unknown): LiniePreview | null {
  const p = section(value);
  return p ? { slug: str(p.slug), state: str(p.state), url: str(p.url), sha: str(p.sha) } : null;
}

function laneOf(item: unknown): LinieLane {
  const b = rec(item);
  const sha = str(b.sha);
  const pr = section(b.pr);
  const commits = list(b.commits).map((entry) => {
    const c = rec(entry);
    const commitSha = str(c.sha);
    return { sha: commitSha, sha7: str(c.sha7) || shortSha(commitSha), title: str(c.title), at: str(c.at), parents: list(c.parents).map(str) };
  });
  return {
    // `remote` (origin) graf zatím neposílá; když přibude, karta MAIN ho ukáže.
    name: str(b.name), role: str(b.role), parent: str(b.parent), sha, remote: str(b.remote), base: str(b.base), commits,
    acceptance: acceptanceOf(b.acceptance, sha), preview: previewOf(b.preview),
    pr: pr ? { number: num(pr.number), state: str(pr.state), url: str(pr.url), base: str(pr.base) } : null,
  };
}

export function graphView(raw: unknown): LinieGraphView {
  const root = rec(raw);
  const server = section(root.server), deployed = section(root.deployed);
  return {
    lanes: list(root.lanes).map(laneOf).filter((lane) => lane.name),
    active: str(root.active),
    server: { branch: str(server?.branch), sha: str(server?.sha), dirty: server?.dirty === true },
    deployed: deployed ? { sha: str(deployed.sha), at: str(deployed.at) } : null,
    enforcement: str(root.enforcement) || "nevynuceno",
    problem: [root.lanes, root.server, root.deployed].map(unavailable).filter(Boolean).join(" · "),
  };
}

export function diffView(raw: unknown): DiffView {
  const root = rec(raw);
  return { commits: list(root.commits).map((item) => ({ sha7: str(rec(item).sha7), title: str(rec(item).title) })), stat: str(root.stat), files: num(root.files) };
}

const ROLES: Record<string, string> = { main: "stabilní základ", develop: "společná vývojová", topic: "téma", feat: "pracovní", experiment: "experiment", fix: "oprava", hotfix: "hotfix", other: "jiná" };
export const roleLabel = (role: string) => ROLES[role] ?? ROLES.other;

export function acceptanceLabel(lane: LinieLane): string {
  const a = lane.acceptance;
  if (!a) return "nepřijato";
  return a.valid ? `přijato ${shortSha(a.sha)} do ${a.target}` : `zastaralé (přijato ${shortSha(a.sha)}, teď ${shortSha(lane.sha)})`;
}

const PREVIEW: Record<string, string> = { building: "sestavuje se…", running: "běží", failed: "selhal", stopped: "zastaven" };
export const previewLabel = (preview: LiniePreview | null) => (preview ? PREVIEW[preview.state] ?? preview.state : "bez náhledu");

/** Pracovní větev = vše kromě main a develop; ty jsou cíle, ne kandidáti přijetí. */
export const isWork = (lane: LinieLane) => !["main", "develop"].includes(lane.role) && !["main", "develop"].includes(lane.name);
export const canAccept = (lane: LinieLane) => isWork(lane) && !!lane.sha && !!lane.parent;

/** Karta PRACOVNÍ VĚTEV: vybraná, jinak aktivní (server na ní stojí), jinak poslední pracovní větev. */
export function workLane(lanes: LinieLane[], picked: string, active: string): LinieLane | null {
  const work = lanes.filter(isWork);
  return work.find((lane) => lane.name === picked) ?? work.find((lane) => lane.name === active) ?? work[work.length - 1] ?? null;
}

export const diffSentence = (target: string, diff: DiffView) => `Do ${target} by přešlo ${diff.files} souborů, ${diff.commits.length} commitů.`;

/** Posledních `count` řádků logu náhledu (sestavení, pak server). */
export function logTail(raw: unknown, count = 40): string {
  const root = rec(raw);
  const lines = [str(root.build), str(root.server)].filter(Boolean).join("\n").split("\n");
  return lines.slice(-count).join("\n");
}
