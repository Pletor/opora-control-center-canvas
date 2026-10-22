import { describe, expect, it, vi } from "vitest";
import { createAgentStateStore } from "./agent-state-store";
import type { AgentStateSnapshot } from "./agent-state-reader";

describe("shared agent-state poll", () => {
  it("runs one reader per scope for every subscriber and stops after the last one", () => {
    const readers: { publish: (value: AgentStateSnapshot) => void; close: ReturnType<typeof vi.fn> }[] = [];
    const watch = vi.fn((_p: string, _w: string, publish: (value: AgentStateSnapshot) => void) => {
      const reader = { publish, close: vi.fn(), refresh: vi.fn() }; readers.push(reader); return reader;
    });
    const store = createAgentStateStore(() => ({ visible: () => true, now: () => 0, listen: () => () => {} }), watch);
    const hub = vi.fn(), canvas = vi.fn();
    const a = store.subscribe("p", "w", hub), b = store.subscribe("p", "w", canvas);
    expect(watch).toHaveBeenCalledTimes(1);
    readers[0].publish({ state: null, etag: "\"e1\"", busy: false, error: "", loadedAt: 5 });
    expect(hub).toHaveBeenLastCalledWith(expect.objectContaining({ etag: "\"e1\"" }));
    expect(canvas).toHaveBeenLastCalledWith(expect.objectContaining({ etag: "\"e1\"" }));
    a.close(); expect(readers[0].close).not.toHaveBeenCalled();
    b.close(); expect(readers[0].close).toHaveBeenCalledTimes(1); expect(store.size()).toBe(0);
  });
  it("gives a late subscriber the latest snapshot immediately", () => {
    let publish: (value: AgentStateSnapshot) => void = () => {};
    const store = createAgentStateStore(() => ({ visible: () => true, now: () => 0, listen: () => () => {} }),
      (_p, _w, next) => { publish = next; return { close: () => {}, refresh: () => {} }; });
    store.subscribe("p", "w", () => {});
    publish({ state: null, etag: "x", busy: false, error: "", loadedAt: 1 });
    const late = vi.fn(); store.subscribe("p", "w", late);
    expect(late).toHaveBeenCalledWith(expect.objectContaining({ etag: "x" }));
  });
});
