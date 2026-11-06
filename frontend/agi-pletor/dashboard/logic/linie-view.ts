import { list, rec, str, unavailable, type Raw } from "./view-common";

/** Linie (docs/navrhy/2026-11-06-velin-git-linie.md §5): odpovědi `GET /api/pletor/linie/` a `/diff` na bezpečný pohled. */
export type LiniePreview = { slug: string; state: string; url: string; sha: string };
export type LinieAcceptance = { sha: string; target: string; at: string; note: string; valid: boolean };
export type LinieBranch = { name: string; role: string; parent: string; sha: string; ahead: number; behind: number; acceptance: LinieAcceptance | null; preview: LiniePreview | null };
export type LinieView = {
  main: { sha: string; remote: string };
  develop: { sha: string; remote: string } | null;
  server: { branch: string; sha: string; dirty: boolean };
  deployed: { sha: string; at: string } | null;
  branches: LinieBranch[];
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

export function linieView(raw: unknown): LinieView {
  const root = rec(raw);
  const main = section(root.main), develop = section(root.develop), server = section(root.server), deployed = section(root.deployed);
  const branches = list(root.branches).map((item) => {
    const b = rec(item);
    const sha = str(b.sha);
    return { name: str(b.name), role: str(b.role), parent: str(b.parent), sha, ahead: num(b.ahead), behind: num(b.behind), acceptance: acceptanceOf(b.acceptance, sha), preview: previewOf(b.preview) };
  });
  return {
    main: { sha: str(main?.sha), remote: str(main?.remote) },
    develop: develop ? { sha: str(develop.sha), remote: str(develop.remote) } : null,
    server: { branch: str(server?.branch), sha: str(server?.sha), dirty: server?.dirty === true },
    deployed: deployed ? { sha: str(deployed.sha), at: str(deployed.at) } : null,
    branches,
    enforcement: str(root.enforcement) || "nevynuceno",
    problem: [root.main, root.develop, root.server, root.deployed, root.branches].map(unavailable).filter(Boolean).join(" · "),
  };
}

export function diffView(raw: unknown): DiffView {
  const root = rec(raw);
  return { commits: list(root.commits).map((item) => ({ sha7: str(rec(item).sha7), title: str(rec(item).title) })), stat: str(root.stat), files: num(root.files) };
}

const ROLES: Record<string, string> = { main: "stabilní základ", develop: "společná vývojová", topic: "téma", feat: "pracovní", experiment: "experiment", fix: "oprava", hotfix: "hotfix", other: "jiná" };
export const roleLabel = (role: string) => ROLES[role] ?? ROLES.other;

/** Tón štítku přijetí: ok = platné, stale = hlava se od přijetí posunula, none = nepřijato. */
export const acceptanceTone = (branch: LinieBranch): "ok" | "stale" | "none" => (!branch.acceptance ? "none" : branch.acceptance.valid ? "ok" : "stale");

export function acceptanceLabel(branch: LinieBranch): string {
  const a = branch.acceptance;
  if (!a) return "nepřijato";
  return a.valid ? `přijato ${shortSha(a.sha)} do ${a.target}` : `zastaralé (přijato ${shortSha(a.sha)}, teď ${shortSha(branch.sha)})`;
}

const PREVIEW: Record<string, string> = { building: "sestavuje se…", running: "běží", failed: "selhal", stopped: "zastaven" };
export const previewLabel = (preview: LiniePreview | null) => (preview ? PREVIEW[preview.state] ?? preview.state : "bez náhledu");

/** Přijímá se jen pracovní větev s hlavou; main a develop jsou cíle, ne kandidáti. */
export const canAccept = (branch: LinieBranch) => !["main", "develop"].includes(branch.role) && !["main", "develop"].includes(branch.name) && !!branch.sha;
export const targetOf = (branch: LinieBranch) => branch.parent;

export const diffSentence = (target: string, diff: DiffView) => `Do ${target} by přešlo ${diff.files} souborů, ${diff.commits.length} commitů.`;
