import { afterEach, describe, expect, it, vi } from "vitest";
import { createEtagCache, notModifiedValue } from "@/shared/types/logic/etag-cache";
import { api } from "@/shared/types/logic/types";

describe("etag cache", () => {
  it("sends If-None-Match only for a remembered URL and forgets a response without ETag", () => {
    const cache = createEtagCache();
    expect(cache.headers("/api/view?project=a")).toEqual({});
    cache.remember("/api/view?project=a", '"t1"', '{"digest":"x"}');
    expect(cache.headers("/api/view?project=a")).toEqual({ "If-None-Match": '"t1"' });
    expect(cache.headers("/api/view?project=b")).toEqual({});
    cache.remember("/api/view?project=a", null, "{}");
    expect(cache.headers("/api/view?project=a")).toEqual({});
    expect(cache.cached("/api/view?project=a")).toBeNull();
  });

  it("keeps at most the limit and drops the least recently used URL", () => {
    const cache = createEtagCache(2);
    cache.remember("/a", '"1"', "1");
    cache.remember("/b", '"2"', "2");
    expect(cache.cached("/a")).toBe("1"); // /a je teď nejnovější
    cache.remember("/c", '"3"', "3");
    expect(cache.size()).toBe(2);
    expect(cache.cached("/b")).toBeNull();
    expect(cache.cached("/a")).toBe("1");
  });

  it("returns a fresh object for 304 and stamps observedAt as now", () => {
    const raw = '{"digest":"x","observedAt":"2026-01-01T00:00:00Z","graph":{"nodes":[]}}';
    const first = notModifiedValue(raw, () => "2026-10-10T10:00:00Z") as { observedAt: string; graph: { nodes: unknown[] } };
    expect(first.observedAt).toBe("2026-10-10T10:00:00Z");
    first.graph.nodes.push(1);
    const second = notModifiedValue(raw) as { graph: { nodes: unknown[] } };
    expect(second.graph.nodes).toEqual([]);
    expect(notModifiedValue("[1,2]")).toEqual([1, 2]);
  });
});

describe("api conditional GET", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("sends the last ETag, serves 304 from memory and never caches writes", async () => {
    const calls: Array<{ url: string; init?: RequestInit }> = [];
    const replies = [
      new Response('{"revision":3,"state":{}}', { status: 200, headers: { ETag: '"r3"' } }),
      new Response(null, { status: 304, headers: { ETag: '"r3"' } }),
      new Response('{"revision":4,"item":null}', { status: 200, headers: { ETag: '"w"' } }),
      new Response('{"revision":4,"state":{"x":1}}', { status: 200, headers: { ETag: '"r4"' } }),
    ];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      if (url === "/api/access/ui-session") return new Response("{}", { status: 200 });
      return replies.shift()!;
    }));
    const url = "/api/desktop-v3/state?project=p1&workspace=draft";
    expect(await api(url)).toEqual({ revision: 3, state: {} });
    expect(await api(url)).toEqual({ revision: 3, state: {} });
    const conditional = calls.filter((call) => call.url === url).map((call) => (call.init?.headers as Record<string, string>)["If-None-Match"]);
    expect(conditional).toEqual([undefined, '"r3"']);
    await api("/api/desktop-v3/decision", { id: "d" });
    const post = calls.find((call) => call.url === "/api/desktop-v3/decision");
    expect((post?.init?.headers as Record<string, string>)["If-None-Match"]).toBeUndefined();
    expect(await api(url)).toEqual({ revision: 4, state: { x: 1 } });
    expect((calls.at(-1)?.init?.headers as Record<string, string>)["If-None-Match"]).toBe('"r3"');
  });

  it("repeats the request unconditionally when 304 arrives without a remembered body", async () => {
    const replies = [new Response(null, { status: 304 }), new Response('{"ok":true}', { status: 200 })];
    const fetch = vi.fn(async () => replies.shift()!);
    vi.stubGlobal("fetch", fetch);
    expect(await api("/api/canvas-versions/head?project=never-seen")).toEqual({ ok: true });
    expect(fetch).toHaveBeenCalledTimes(2);
  });
});

describe("api human session", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("initializes a fresh research deep link before reading scoped events", async () => {
    vi.resetModules();
    const { api: freshApi } = await import("@/shared/types/logic/types");
    const calls: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      calls.push(url);
      return new Response(url === "/api/access/ui-session" ? "{}" : '{"events":[]}', { status: 200 });
    }));
    const url = "/api/research/events?project=p&workspace=w";
    expect(await freshApi(url)).toEqual({ events: [] });
    expect(calls).toEqual(["/api/access/ui-session", url]);
  });

  it("renews an expired research session once without swallowing authorization errors", async () => {
    vi.resetModules();
    const { api: freshApi } = await import("@/shared/types/logic/types");
    const calls: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      calls.push(url);
      return new Response(url === "/api/access/ui-session" ? "{}" : '{"error":"Denied"}',
        { status: url === "/api/access/ui-session" ? 200 : 401 });
    }));
    const url = "/api/research?project=p&workspace=w";
    await expect(freshApi(url)).rejects.toThrow("Denied");
    expect(calls).toEqual(["/api/access/ui-session", url, "/api/access/ui-session", url]);
  });

  it("renews the UI session after a restart and repeats a human-only read once", async () => {
    const calls: string[] = [];
    const replies = [
      new Response('{"error":"Otázky srdce čte jen člověk v UI.","humanRequired":true}', { status: 428 }),
      new Response('{"escalations":[]}', { status: 200 }),
    ];
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      calls.push(url);
      if (url === "/api/access/ui-session") return new Response("{}", { status: 200 });
      return replies.shift()!;
    }));
    const url = "/api/brain/heart/escalations?project=p1&workspace=w1";
    expect(await api(url)).toEqual({ escalations: [] });
    expect(calls).toEqual([url, "/api/access/ui-session", url]);
  });
});
