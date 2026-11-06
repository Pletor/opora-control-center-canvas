import { list, rec, str } from "./view-common";

/** Detail commitu z `GET /api/pletor/linie/commit/{sha}` (docs/navrhy/2026-11-06-linie-detail-commitu.md, Kontrakt). */
export type CommitDetail = {
  commit: { sha: string; sha7: string; title: string; body: string; at: string; author: string; files: string; stat: string; branches: string[] };
  ticket: {
    ticketId: string; title: string; state: string; stateLabel: string; next: string;
    essence: string; build: string; doneCriteria: string[]; branch: string;
    card: { id: string; name: string; link: string } | null;
    office: { worker: string; role: string; department: string; profile: string; executionId: string } | null;
    plan: { id: string; order: number; title: string; acceptance: string; kind: string }[];
  } | null;
  pr: { number: string; state: string; url: string } | null;
  preview: { url: string; state: string; sha: string } | null;
  sentence: string;
};

const opt = (value: unknown) => (value && typeof value === "object" && !Array.isArray(value) ? rec(value) : null);

export function commitView(raw: unknown): CommitDetail {
  const root = rec(raw), c = rec(root.commit);
  const t = opt(root.ticket), pr = opt(root.pr), preview = opt(root.preview);
  const body = rec(t?.body), work = rec(t?.work), card = opt(t?.card), office = opt(t?.office);
  return {
    commit: {
      sha: str(c.sha), sha7: str(c.sha7), title: str(c.title), body: str(c.body), at: str(c.at), author: str(c.author),
      files: str(c.files), stat: str(c.stat), branches: list(c.branches).map(str),
    },
    ticket: t && {
      ticketId: str(t.ticketId), title: str(t.title) || str(body.essence).split("\n")[0], state: str(t.state), stateLabel: str(t.stateLabel), next: str(t.next),
      essence: str(body.essence), build: str(body.build), doneCriteria: list(body.doneCriteria).map(str), branch: str(work.branch),
      card: card && { id: str(card.id), name: str(card.name), link: str(card.link) },
      office: office && { worker: str(office.worker), role: str(office.role), department: str(office.department), profile: str(office.profile), executionId: str(office.executionId) },
      plan: list(t.plan).map((s) => ({ id: str(rec(s).id), order: Number(rec(s).order) || 0, title: str(rec(s).title), acceptance: str(rec(s).acceptance), kind: str(rec(s).kind) }))
        .sort((a, b) => a.order - b.order),
    },
    pr: pr && { number: str(pr.number), state: str(pr.state), url: str(pr.url) },
    preview: preview && { url: str(preview.url), state: str(preview.state), sha: str(preview.sha) },
    sentence: str(root.sentence),
  };
}
