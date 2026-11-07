import { list, rec, str, unavailable, type Raw } from "./view-common";

/** Linie (docs/navrhy/2026-11-06-velin-git-linie.md §5): odpověď `GET /api/pletor/linie/graph` (Git graf a karta MAIN) na bezpečný pohled. */
export type LiniePreview = { slug: string; state: string; url: string; sha: string };
export type LinieAcceptance = { sha: string; target: string; at: string; note: string; valid: boolean };
export type LinieCommit = { sha: string; sha7: string; title: string; at: string; parents: string[] };
export type LiniePr = { number: number; state: string; url: string; base: string };
export type LinieLane = {
  name: string; role: string; parent: string; depth: number; sha: string; remote: string; base: string;
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
    name: str(b.name), role: str(b.role), parent: str(b.parent), depth: num(b.depth) || 2, sha, remote: str(b.remote), base: str(b.base), commits,
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
