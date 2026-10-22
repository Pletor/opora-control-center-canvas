import { isObject, isText } from "@/hub/oporahub-mirror/logic/hub-read";

// Události karty z toku OporaHubu (docs/oporahub-events.md). API `GET /api/oporahub/events` filtr
// podle karty nemá (jen `project`, `workspace`, `since`, `limit`), proto se stránkuje kurzorem a karta
// se vybírá na klientovi. Strop stránek drží čtení malé; `truncated` to poctivě přizná.
export type HubEvent = {
  id: number; at: string; kind: string; nodeId: string | null; executionId: string | null; stepId: string | null;
  prNumber: number | null; stage: string | null; health: string | null; actor: { kind: string; name: string }; data: Record<string, unknown>;
};
export type EventPage = { events: HubEvent[]; cursor: number; head: number; gap: boolean };
export const EVENTS_PAGE = 500;
export const EVENTS_MAX_PAGES = 10;

const num = (value: unknown) => Number.isSafeInteger(value) ? Number(value) : null;
const opt = (value: unknown) => isText(value) ? value : null;

function event(raw: unknown): HubEvent | null {
  if (!isObject(raw) || num(raw.id) === null || !isText(raw.kind) || !isText(raw.at)) return null;
  const actor = isObject(raw.actor) ? raw.actor : {};
  return { id: num(raw.id)!, at: raw.at, kind: raw.kind, nodeId: opt(raw.nodeId), executionId: opt(raw.executionId), stepId: opt(raw.stepId),
    prNumber: num(raw.prNumber), stage: opt(raw.stage), health: opt(raw.health),
    actor: { kind: isText(actor.kind) ? actor.kind : "system", name: isText(actor.name) ? actor.name : "opora" },
    data: isObject(raw.data) ? raw.data : {} };
}
export function parseEventPage(raw: unknown): EventPage {
  if (!isObject(raw) || !Array.isArray(raw.events)) throw new Error("Tok událostí má neplatný tvar.");
  return { events: raw.events.map(event).filter((item): item is HubEvent => item !== null),
    cursor: num(raw.cursor) ?? 0, head: num(raw.head) ?? 0, gap: raw.gap === true };
}
export const eventsUrl = (project: string, workspace: string, since: number) =>
  `/api/oporahub/events?${new URLSearchParams({ project, workspace, since: String(since), limit: String(EVENTS_PAGE) })}`;

/** Všechny události karty (do stropu stránek); vrací i kurzor hlavy pro export a hlášení zkrácení. */
export async function readCardEvents(fetchPage: (since: number) => Promise<EventPage>, nodeId: string, maxPages = EVENTS_MAX_PAGES) {
  const mine: HubEvent[] = [];
  let since = 0, head = 0, truncated = false, gap = false;
  for (let page = 0; ; page++) {
    if (page >= maxPages) { truncated = true; break; }
    const result = await fetchPage(since);
    head = result.head; gap = gap || result.gap;
    mine.push(...result.events.filter(item => item.nodeId === nodeId));
    if (!result.events.length || result.cursor <= since || result.cursor >= result.head) break;
    since = result.cursor;
  }
  return { events: mine.sort((a, b) => b.id - a.id), head, truncated, gap };
}

export const EVENT_FILTERS = ["all", "spec", "run", "review", "people"] as const;
export type EventFilter = typeof EVENT_FILTERS[number];
export const FILTER_LABEL: Record<EventFilter, string> = { all: "Vše", spec: "Zadání", run: "Běh", review: "Review", people: "Lidé" };

export function eventCategory(item: HubEvent): Exclude<EventFilter, "all" | "people"> {
  if (item.kind.startsWith("changeset.") || item.kind.startsWith("autorebase.")) return "spec";
  if (["pr.linked", "review.round", "review.finding", "gate.changed", "formal.result", "merge.done", "writeback.done"].includes(item.kind)) return "review";
  return "run";
}
export const matchesFilter = (item: HubEvent, filter: EventFilter) =>
  filter === "all" || (filter === "people" ? item.actor.kind === "human" || item.kind.startsWith("decision.") || item.kind === "card.closed" : eventCategory(item) === filter);

const str = (value: unknown) => typeof value === "string" ? value : "";
/** Lidský nadpis události; neznámý druh se ukáže doslova. */
export function eventTitle(item: HubEvent): string {
  const d = item.data, step = item.stepId ?? str(d.stepId);
  const titles: Record<string, string> = {
    "step.started": `${step} zahájen`, "step.done": `${step} hotov`, "step.failed": `${step} selhal`,
    "lease.claimed": `Lease převzata${d.epoch !== undefined ? ` · epocha ${d.epoch}` : ""}`, "lease.heartbeat": "Heartbeat lease", "lease.expired": "Lease vypršela",
    "result.reported": "Výsledek běhu nahlášen", "pr.linked": `PR #${item.prNumber ?? "?"} propojen`,
    "review.round": `Kolo review ${str(d.round) || String(d.round ?? "")}`.trim(), "review.finding": `Nález ${str(d.severity)} · ${str(d.status)}`,
    "gate.changed": `Brána: ${isObject(d.gate) ? str(d.gate.status) : "zrušena"}`, "formal.result": `Formální ověření: ${str(d.outcome)}`,
    "decision.created": `Rozhodnutí čeká: ${str(d.decision)}`, "decision.resolved": `Rozhodnuto: ${str(d.decision)}`,
    "changeset.proposed": `Návrh zadání${str(d.subject) ? ` · ${str(d.subject)}` : ""}`, "changeset.accepted": "Zadání přijato",
    "autorebase.done": "Auto-rebase hotov", "autorebase.conflict": "Auto-rebase: konflikt", "merge.done": "PR sloučeno",
    "writeback.done": "Plán zapsán", "card.closed": "Karta uzavřena člověkem",
    "stage.changed": `Etapa ${item.stage ?? "?"}${item.health ? ` · ${item.health}` : ""}`,
  };
  return titles[item.kind] ?? item.kind;
}
export type EventTone = "ok" | "warn" | "bad" | "acc";
export function eventTone(item: HubEvent): EventTone {
  if (item.kind.endsWith(".failed") || item.kind.endsWith(".conflict") || item.kind === "lease.expired" || (item.kind === "review.finding" && item.data.status === "open")) return "bad";
  if (item.kind.startsWith("changeset.") || item.kind.startsWith("decision.") || item.actor.kind === "human") return "warn";
  if (item.kind.endsWith(".done") || item.kind === "merge.done" || item.kind === "card.closed") return "ok";
  return "acc";
}
export const eventTime = (at: string) => { const time = Date.parse(at); return Number.isFinite(time)
  ? new Date(time).toLocaleTimeString("cs-CZ", { hour: "2-digit", minute: "2-digit" }) : "—"; };
