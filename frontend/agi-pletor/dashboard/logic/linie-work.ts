import { list, rec, str } from "./view-common";

/**
 * Detail kuličky z `GET /api/pletor/linie/work/{ticketId}` (docs/navrhy/2026-11-06-linie-editor-a-vynuceni.md §2, §3).
 * Backend vrací ticket ploše (`{ticketId, body, status, work, state, …}`); obálku `{ticket, work}` bere taky.
 */
export type WorkDetail = {
  ticketId: string; mark: string; title: string; essence: string; build: string; doneCriteria: string; status: string;
  state: string; stateLabel: string; next: string;
  branch: string; baseBranch: string; baseSha: string; headSha: string; target: string;
  checks: { name: string; status: string; sha: string }[];
  acceptance: { sha: string; note: string; at: string; revision: string } | null;
  mergeAllowed: { target: string; targetSha: string } | null;
  merged: { sha: string; target: string; at: string } | null;
  preview: { slug: string; sha: string; url: string } | null;
  blocked: string;
  commits: { sha7: string; title: string; at: string }[];
  pr: { number: string; url: string; state: string } | null;
  /** Pokusy (`work.attempts[]`, L7e): větev z rodiče, agent, `published` po ověření v originu. */
  attempts: { attemptId: string; branch: string; baseRef: string; agent: string; at: string; published: boolean }[];
  /** Relace agentů (`work.runs[]`): vazba na worktree a heartbeat; živost říká backend v osách, tady jen výpis. */
  runs: { runId: string; agent: string; startedAt: string; heartbeat: string; worktree: string }[];
};

const opt = (value: unknown) => (value && typeof value === "object" && !Array.isArray(value) ? rec(value) : null);
export const short = (sha: string) => sha.slice(0, 7);

export function workDetail(raw: unknown): WorkDetail {
  const root = rec(raw);
  const ticket = opt(root.ticket) ?? root;
  const body = rec(ticket.body);
  const w = rec(root.work ?? ticket.work);
  const acceptance = opt(w.acceptance), allowed = opt(w.mergeAllowed), merged = opt(w.merged), preview = opt(w.preview), pr = opt(root.pr ?? ticket.pr);
  return {
    ticketId: str(ticket.ticketId ?? ticket.id), mark: str(w.mark), title: str(w.title) || str(ticket.title) || str(body.essence).split("\n")[0],
    essence: str(body.essence), build: str(body.build), doneCriteria: list(body.doneCriteria).map(str).join("\n") || str(body.doneCriteria), status: str(ticket.status),
    state: str(root.state), stateLabel: str(root.stateLabel), next: str(root.next),
    branch: str(w.branch), baseBranch: str(w.baseBranch), baseSha: str(w.baseSha), headSha: str(w.headSha), target: str(w.target),
    checks: list(w.checks).map((item) => ({ name: str(rec(item).name), status: str(rec(item).status), sha: str(rec(item).sha) })),
    acceptance: acceptance && { sha: str(acceptance.sha), note: str(acceptance.note), at: str(acceptance.at), revision: str(acceptance.revision) },
    mergeAllowed: allowed && { target: str(allowed.target), targetSha: str(allowed.targetSha) },
    merged: merged && { sha: str(merged.sha), target: str(merged.target), at: str(merged.at) },
    preview: preview && { slug: str(preview.slug), sha: str(preview.sha), url: str(preview.url) },
    blocked: str(opt(w.blocked)?.reason),
    commits: list(root.commits).map((item) => ({ sha7: str(rec(item).sha7), title: str(rec(item).title), at: str(rec(item).at) })),
    pr: pr && { number: str(pr.number), url: str(pr.url), state: str(pr.state) },
    attempts: list(w.attempts).map((item) => { const a = rec(item); return { attemptId: str(a.attemptId), branch: str(a.branch), baseRef: str(a.baseRef), agent: str(a.agent), at: str(a.at), published: a.published === true }; }),
    runs: list(w.runs).map((item) => { const r = rec(item); return { runId: str(r.runId), agent: str(r.agent), startedAt: str(r.startedAt), heartbeat: str(r.heartbeat), worktree: str(r.worktree) }; }),
  };
}

/** Náhled se vždy vztahuje k revizi; chybějící náhled se přizná, nevydává se za aktuální. */
export function previewSentence(d: WorkDetail): string {
  if (!d.preview?.sha) return "náhled této revize není dostupný";
  const same = d.preview.sha === d.headSha;
  return `náhled zobrazuje ${short(d.preview.sha)}, hlava je ${short(d.headSha) || "—"}${same ? " – shoda" : " – náhled není z hlavy"}`;
}

export function acceptanceSentence(d: WorkDetail): string {
  const a = d.acceptance;
  if (!a) return "nepřijato";
  const head = a.sha === d.headSha ? "platí pro hlavu" : `zastaralé, hlava je ${short(d.headSha)}`;
  return `přijato ${short(a.sha)} (${head})${a.note ? ` · ${a.note}` : ""}`;
}

/** Text odmítnutí: `message` z těla (409 backendu), jinak text chyby. */
export function failureText(failure: unknown, fallback = "Zápis selhal."): string {
  const body = rec((failure as { body?: unknown } | null)?.body);
  if (typeof body.message === "string" && body.message) return body.message;
  return failure instanceof Error ? failure.message : fallback;
}
