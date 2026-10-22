// Jeden sdílený klient toku událostí OporaHubu (docs/oporahub-events.md) pro celý prostor: živý pás, plátno
// i Velín odebírají stejné spojení. Start: `head` z `/events`, posledních až 200 událostí, pak SSE
// `/events/stream?since=<kurzor>`. Při chybě spojení klient nejdřív dočte `/events?since=` (pozná `gap`),
// pak se připojí znovu od posledního kurzoru; po opakovaném selhání zůstane u pollingu `/events?since=`.
// `gap` (retence smazala události) ohlásí odběratelům, aby znovu načetli agent-state.
import { createPoller, type Poller } from "@/shared/hooks/logic/poller";

export type OporaEvent = {
  id: number; at: string; kind: string; projectId: string; workspaceId: string; nodeId: string | null;
  executionId: string | null; stepId: string | null; prNumber: number | null; stage: string | null; health: string | null;
  actor: { kind: string; name: string }; data: Record<string, unknown>;
};
export type EventsSnapshot = { events: OporaEvent[]; transport: "connecting" | "sse" | "poll"; cursor: number; gaps: number; error: string };
type Page = { events: OporaEvent[]; cursor: number; head: number; gap: boolean };
type Source = { onmessage: ((event: { data: string }) => void) | null; onerror: (() => void) | null; onopen: (() => void) | null; close(): void };
export type EventsEnvironment = {
  fetchJson: (url: string) => Promise<Page>;
  openStream: ((url: string) => Source) | null;
  later: (fn: () => void, ms: number) => () => void;
  poller: (run: () => Promise<unknown>) => Poller;
};

export const KEEP = 300;
const RECENT = 200;
const STREAM_FAILURES = 3;

export const browserEventsEnvironment = (): EventsEnvironment => ({
  fetchJson: async (url) => {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`Tok událostí není dostupný (HTTP ${response.status}).`);
    return response.json();
  },
  openStream: typeof EventSource === "undefined" ? null : (url) => new EventSource(url) as unknown as Source,
  later: (fn, ms) => { const timer = setTimeout(fn, ms); return () => clearTimeout(timer); },
  poller: (run) => createPoller({ run, intervalMs: 5000, immediate: false }),
});

const query = (project: string, workspace: string, extra: Record<string, string>) =>
  new URLSearchParams({ project, workspace, ...extra }).toString();

/** Spojení pro jeden prostor; `notify` dostane nový snímek po každé změně. */
export function connectEvents(project: string, workspace: string, env: EventsEnvironment, notify: (snapshot: EventsSnapshot) => void) {
  let snapshot: EventsSnapshot = { events: [], transport: "connecting", cursor: 0, gaps: 0, error: "" };
  let source: Source | null = null, poller: Poller | null = null, cancel: (() => void) | null = null;
  let failures = 0, closed = false;
  const set = (patch: Partial<EventsSnapshot>) => { snapshot = { ...snapshot, ...patch }; if (!closed) notify(snapshot); };
  const add = (events: OporaEvent[]) => {
    const fresh = events.filter((event) => event.id > snapshot.cursor);
    if (!fresh.length) return;
    set({ events: [...snapshot.events, ...fresh].slice(-KEEP), cursor: fresh[fresh.length - 1].id });
  };
  const page = async (since: number, limit = RECENT) => {
    const result = await env.fetchJson(`/api/oporahub/events?${query(project, workspace, { since: String(since), limit: String(limit) })}`);
    if (result.gap) set({ gaps: snapshot.gaps + 1, cursor: Math.max(snapshot.cursor, since) });
    add(result.events);
    if (result.gap && result.events.length === 0) set({ cursor: result.head });
    return result;
  };
  const poll = () => {
    source?.close(); source = null;
    set({ transport: "poll" });
    poller = env.poller(async () => { try { await page(snapshot.cursor); set({ error: "" }); } catch (error) { set({ error: String(error) }); } });
    poller.start(false);
  };
  const stream = () => {
    if (closed) return;
    if (!env.openStream || failures >= STREAM_FAILURES) { poll(); return; }
    const opened = env.openStream(`/api/oporahub/events/stream?${query(project, workspace, { since: String(snapshot.cursor) })}`);
    source = opened;
    opened.onopen = () => { failures = 0; set({ transport: "sse", error: "" }); };
    opened.onmessage = (message) => { try { add([JSON.parse(message.data) as OporaEvent]); } catch { /* rámec bez JSON (komentář) */ } };
    opened.onerror = () => {
      opened.close(); if (source === opened) source = null;
      failures += 1;
      // Dočíst, co mezitím přibylo (a poznat `gap`), a znovu se připojit od kurzoru.
      cancel = env.later(() => { page(snapshot.cursor).catch(() => undefined).finally(stream); }, 2000);
    };
  };
  (async () => {
    try {
      const head = (await page(Number.MAX_SAFE_INTEGER, 1)).head;
      set({ cursor: 0 });
      await page(Math.max(0, head - RECENT));
      if (!snapshot.events.length) set({ cursor: head });
    } catch (error) { set({ error: String(error) }); }
    stream();
  })();
  return () => { closed = true; source?.close(); poller?.stop(); cancel?.(); };
}

/** Sdílený klient: jedno spojení na prostor, poslední odběratel ho zavře. */
export function createEventsClient(environment: () => EventsEnvironment = browserEventsEnvironment) {
  const entries = new Map<string, { close: () => void; listeners: Set<(s: EventsSnapshot) => void>; latest: EventsSnapshot | null }>();
  return {
    subscribe(project: string, workspace: string, listener: (snapshot: EventsSnapshot) => void) {
      const key = JSON.stringify([project, workspace]);
      let entry = entries.get(key);
      if (!entry) {
        const created = { close: () => {}, listeners: new Set<(s: EventsSnapshot) => void>(), latest: null as EventsSnapshot | null };
        entries.set(key, created);
        created.close = connectEvents(project, workspace, environment(), (next) => { created.latest = next; created.listeners.forEach((item) => item(next)); });
        entry = created;
      }
      const current = entry;
      current.listeners.add(listener);
      if (current.latest) listener(current.latest);
      return () => {
        current.listeners.delete(listener);
        if (!current.listeners.size && entries.get(key) === current) { entries.delete(key); current.close(); }
      };
    },
  };
}

export const eventsClient = createEventsClient();
