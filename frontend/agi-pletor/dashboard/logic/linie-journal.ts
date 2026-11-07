import { list, rec, str } from "./view-common";

/**
 * Deník Linie z `GET /api/pletor/linie/journal?after=&limit=` (docs/navrhy/2026-11-06-linie-rebrand.md §6, L7e):
 * události `linie.*` s časem, druhem, původcem, odkazy a textem. Stránky se skládají podle `id` (nikdy podle času),
 * „nových“ se počítá od posledního zobrazeného id. Čistá logika bez Reactu.
 */
export type JournalEvent = { id: number; kind: string; kindText: string; at: string; who: string; ticketId: string; text: string; failed: boolean };
export type Journal = { events: JournalEvent[]; lastId: number };

const KIND: Record<string, string> = {
  "work.created": "kulička", "work.attached": "kulička", attempt: "pokus", "attempt.published": "pokus", report: "hlášení", accept: "přijetí",
  "accept.revoked": "přijetí", "merge.allowed": "povolení", "merge.started": "merge", "merge.finished": "merge", abandon: "opuštěno", block: "blok",
  unblock: "odblokováno", defer: "odloženo", resume: "obnoveno", deploy: "nasazení", "request.accepted": "žádost", "request.step": "žádost",
  "request.failed": "selhání", "revert.started": "revert", "revert.finished": "revert", "revert.conflict": "revert", "revert.failed": "revert", "rebase.noted": "rebase",
};
const FAILED = new Set(["linie.request.failed", "linie.revert.conflict", "linie.revert.failed"]);

export const whoText = (by: string) => (by === "human" ? "člověk" : by.startsWith("agent:") ? by.slice(6) || "agent" : "služba OPORY");

/** Věta události z odkazů a dat: druh, sha, prostředí, krok žádosti nebo důvod. */
function textOf(kind: string, refs: Record<string, unknown>, data: Record<string, unknown>): string {
  const sha = str(refs.sha).slice(0, 7), bits: string[] = [];
  if (str(data.k)) bits.push(`krok ${str(data.k)}`);
  if (str(refs.env)) bits.push(str(refs.env));
  if (sha) bits.push(sha);
  if (str(refs.request)) bits.push(str(refs.request));
  if (str(data.why) || str(data.reason)) bits.push(str(data.why) || str(data.reason));
  return bits.join(" · ") || kind.replace(/^linie\./, "");
}

export function journalView(raw: unknown): Journal {
  const root = rec(raw);
  const events = list(root.events).map((item) => {
    const e = rec(item), refs = rec(e.refs), data = rec(e.data), kind = str(e.kind);
    const id = typeof e.id === "number" ? e.id : Number(e.id);
    return { id, kind, kindText: KIND[kind.replace(/^linie\./, "")] ?? kind.replace(/^linie\./, ""), at: str(e.at), who: whoText(str(e.by)),
      ticketId: str(refs.ticket), text: textOf(kind, refs, data), failed: FAILED.has(kind) };
  }).filter((e) => Number.isFinite(e.id) && e.kind);
  const lastId = typeof root.lastId === "number" ? root.lastId : events.at(-1)?.id ?? 0;
  return { events, lastId };
}

/** Další stránka deníku navazuje na dosavadní: stejné id se nezdvojí, pořadí podle id. */
export function appendJournal(known: Journal, next: Journal): Journal {
  const seen = new Set(known.events.map((e) => e.id));
  const events = [...known.events, ...next.events.filter((e) => !seen.has(e.id))].sort((a, b) => a.id - b.id);
  return { events, lastId: Math.max(known.lastId, next.lastId) };
}

/** Počet událostí novějších než naposledy zobrazené id. */
export const unseenCount = (journal: Journal, seenId: number) => journal.events.filter((e) => e.id > seenId).length;
