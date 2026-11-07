import { list, rec, str } from "./view-common";

/** Cesta práce z `GET /api/pletor/linie/trace/{mark}` (docs/navrhy/2026-11-06-linie-vodotisk-cesty.md, API). */
export type EdgeStatus = "verified" | "claimed" | "inferred" | "missing";
const STATUSES: EdgeStatus[] = ["verified", "claimed", "inferred", "missing"];
const LABEL: Record<EdgeStatus, string> = { verified: "ověřeno", claimed: "tvrzeno", inferred: "odvozeno", missing: "chybí" };
export const statusLabel = (status: EdgeStatus) => LABEL[status];

export type TraceView = {
  mark: string;
  ticket: { ticketId: string; title: string; stateLabel: string; essence: string; build: string; doneCriteria: string[]; branch: string } | null;
  card: { id: string; name: string; link: string; known: boolean } | null;
  revision: string;
  plan: { id: string; order: number; title: string; acceptance: string }[];
  runs: { runId: string; agent: string; startedAt: string; fromSha7: string; status: EdgeStatus }[];
  commits: { sha: string; sha7: string; title: string; runId: string; status: EdgeStatus }[];
  code: { path: string; line: string; symbol: string; step: string; status: EdgeStatus }[];
  pr: { number: string; state: string; url: string } | null;
  checks: { name: string; status: string; sha7: string }[];
  acceptance: { sha7: string; note: string } | null;
  merged: { sha7: string; target: string; at: string } | null;
  preview: { url: string; state: string } | null;
  gaps: string[];
  sentence: string;
};

const opt = (value: unknown) => (value && typeof value === "object" && !Array.isArray(value) ? rec(value) : null);
const status = (value: unknown, fallback: EdgeStatus): EdgeStatus => (STATUSES.includes(value as EdgeStatus) ? (value as EdgeStatus) : fallback);
const sha7 = (value: unknown) => str(value).slice(0, 7);

export function traceView(raw: unknown): TraceView {
  const root = rec(raw);
  const t = opt(root.ticket), card = opt(root.card), pr = opt(root.pr), acc = opt(root.acceptance), merged = opt(root.merged), preview = opt(root.preview);
  const body = rec(t?.body), work = rec(t?.work);
  return {
    mark: str(root.mark),
    ticket: t && {
      ticketId: str(t.ticketId), title: str(t.title) || str(body.essence).split("\n")[0], stateLabel: str(t.stateLabel) || str(t.state),
      essence: str(body.essence), build: str(body.build), doneCriteria: list(body.doneCriteria).map(str), branch: str(work.branch),
    },
    card: card && { id: str(card.id), name: str(card.name), link: str(card.link), known: card.known !== false },
    revision: str(root.revision),
    plan: list(root.plan).map((s) => ({ id: str(rec(s).id), order: Number(rec(s).order) || 0, title: str(rec(s).title), acceptance: str(rec(s).acceptance) }))
      .sort((a, b) => a.order - b.order),
    runs: list(root.runs).map((r) => ({ runId: str(rec(r).runId), agent: str(rec(r).agent), startedAt: str(rec(r).startedAt), fromSha7: sha7(rec(r).fromSha), status: status(rec(r).status, "claimed") })),
    commits: list(root.commits).map((c) => ({ sha: str(rec(c).sha), sha7: str(rec(c).sha7) || sha7(rec(c).sha), title: str(rec(c).title), runId: str(rec(c).runId), status: status(rec(c).status, "inferred") })),
    code: list(root.code).map((c) => ({ path: str(rec(c).path), line: str(rec(c).line), symbol: str(rec(c).symbol), step: str(rec(c).step), status: status(rec(c).status, "claimed") })),
    pr: pr && { number: str(pr.number), state: str(pr.state), url: str(pr.url) },
    checks: list(root.checks).map((c) => ({ name: str(rec(c).name), status: str(rec(c).status), sha7: sha7(rec(c).sha) })),
    acceptance: acc && { sha7: sha7(acc.sha), note: str(acc.note) },
    merged: merged && { sha7: sha7(merged.sha), target: str(merged.target), at: str(merged.at) },
    preview: preview && { url: str(preview.url), state: str(preview.state) },
    gaps: list(root.gaps).map((g) => str(rec(g).text)).filter(Boolean),
    sentence: str(root.sentence),
  };
}
