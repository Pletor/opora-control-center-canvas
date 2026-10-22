import { describe, expect, it, vi } from "vitest";
import { connectEvents, createEventsClient, type EventsEnvironment, type EventsSnapshot, type OporaEvent } from "./events-client";

const event = (id: number, kind = "step.done"): OporaEvent => ({ id, at: "2026-10-22T10:00:00.000Z", kind, projectId: "p", workspaceId: "w",
  nodeId: "a", executionId: null, stepId: null, prNumber: null, stage: null, health: null, actor: { kind: "agent", name: "x" }, data: {} });
const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

function fakeEnv(pages: Record<string, { events: OporaEvent[]; head: number; gap?: boolean }>, stream = true) {
  const urls: string[] = [];
  const sources: { url: string; source: { onmessage: ((e: { data: string }) => void) | null; onerror: (() => void) | null; onopen: (() => void) | null; close: () => void } }[] = [];
  const timers: (() => void)[] = [];
  const env: EventsEnvironment = {
    fetchJson: async (url) => {
      urls.push(url);
      const since = new URLSearchParams(url.split("?")[1]).get("since")!;
      const page = pages[since] ?? { events: [], head: 0 };
      return { events: page.events, cursor: page.events.at(-1)?.id ?? Number(since), head: page.head, gap: !!page.gap };
    },
    openStream: stream ? (url) => { const source = { onmessage: null, onerror: null, onopen: null, close: vi.fn() }; sources.push({ url, source }); return source; } : null,
    later: (fn) => { timers.push(fn); return () => {}; },
    poller: (run) => ({ start: () => { void run(); }, stop: vi.fn(), refresh: async () => {}, poke: async () => {}, running: () => false }),
  };
  return { env, urls, sources, timers };
}

describe("klient toku událostí", () => {
  it("načte posledních 200 od head a pak otevře SSE od kurzoru", async () => {
    const { env, urls, sources } = fakeEnv({ [String(Number.MAX_SAFE_INTEGER)]: { events: [], head: 250 }, "50": { events: [event(249), event(250)], head: 250 } });
    const seen: EventsSnapshot[] = [];
    connectEvents("p", "w", env, (s) => seen.push(s));
    await flush(); await flush();
    expect(urls[1]).toContain("since=50");
    expect(sources[0].url).toContain("/api/oporahub/events/stream?project=p&workspace=w&since=250");
    sources[0].source.onopen?.();
    sources[0].source.onmessage?.({ data: JSON.stringify(event(251, "lease.claimed")) });
    sources[0].source.onmessage?.({ data: JSON.stringify(event(250)) });
    const last = seen.at(-1)!;
    expect(last.transport).toBe("sse");
    expect(last.events.map((item) => item.id)).toEqual([249, 250, 251]);
  });

  it("po chybě spojení dočte stránku, pozná gap a připojí se od nového kurzoru", async () => {
    const { env, sources, timers } = fakeEnv({ [String(Number.MAX_SAFE_INTEGER)]: { events: [], head: 0 }, "0": { events: [], head: 900, gap: true } });
    const seen: EventsSnapshot[] = [];
    connectEvents("p", "w", env, (s) => seen.push(s));
    await flush(); await flush();
    sources[0].source.onerror?.();
    expect(sources[0].source.close).toHaveBeenCalled();
    timers.shift()!();
    await flush(); await flush();
    expect(seen.at(-1)!.gaps).toBeGreaterThan(0);
    expect(sources[1].url).toContain("since=900");
  });

  it("bez EventSource zůstane u pollingu a klient sdílí spojení mezi odběrateli", async () => {
    const make = vi.fn(() => fakeEnv({}, false).env);
    const client = createEventsClient(make);
    const a = vi.fn(), b = vi.fn();
    const offA = client.subscribe("p", "w", a);
    const offB = client.subscribe("p", "w", b);
    await flush(); await flush();
    expect(make).toHaveBeenCalledTimes(1);
    expect(a.mock.calls.at(-1)![0].transport).toBe("poll");
    offA(); offB();
  });
});
