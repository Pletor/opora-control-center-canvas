import { describe, expect, it, vi } from "vitest";
import { createVaultStore } from "./brief-vault-store";
import type { VaultTree } from "./brief-vault-model";

const tree = (n: number): VaultTree => ({ readOnly: false, roots: [], feedback: [{ id: String(n) } as never] });

function setup() {
  let calls = 0;
  let release: (() => void) | null = null;
  const fetchTree = vi.fn(() => new Promise<VaultTree>((resolve) => { calls += 1; const n = calls; release = () => resolve(tree(n)); }));
  vi.useFakeTimers();
  const store = createVaultStore({ fetchTree, pollMs: 15000, debounceMs: 200 });
  return { store, fetchTree, finish: async () => { release?.(); await vi.advanceTimersByTimeAsync(0); } };
}

describe("brief vault store", () => {
  it("shares one request between three panels of the same workspace", async () => {
    const { store, fetchTree, finish } = setup();
    const seen: number[] = [];
    const listeners = [0, 1, 2].map((i) => () => seen.push(i));
    const off = listeners.map((listener) => store.subscribe("p", "w", listener));
    expect(fetchTree).toHaveBeenCalledTimes(1);
    await finish();
    expect(store.snapshot("p", "w").tree?.feedback?.[0].id).toBe("1");
    expect(seen.sort()).toEqual([0, 1, 2]);
    off.forEach((stop) => stop());
    vi.useRealTimers();
  });

  it("coalesces refresh requests from one state change into one fetch", async () => {
    const { store, fetchTree, finish } = setup();
    const off = store.subscribe("p", "w", () => {});
    await finish();
    fetchTree.mockClear();
    store.refresh("p", "w"); store.refresh("p", "w"); store.refresh("p", "w");
    await vi.advanceTimersByTimeAsync(200);
    expect(fetchTree).toHaveBeenCalledTimes(1);
    off();
    vi.useRealTimers();
  });

  it("polls once for all subscribers and stops when the last one leaves", async () => {
    const { store, fetchTree, finish } = setup();
    const a = store.subscribe("p", "w", () => {});
    const b = store.subscribe("p", "w", () => {});
    await finish();
    fetchTree.mockClear();
    await vi.advanceTimersByTimeAsync(15000);
    expect(fetchTree).toHaveBeenCalledTimes(1);
    await finish();
    a(); b();
    fetchTree.mockClear();
    await vi.advanceTimersByTimeAsync(60000);
    expect(fetchTree).not.toHaveBeenCalled();
    vi.useRealTimers();
  });

  it("runs a refresh requested during a fetch right after it, and keeps the last tree on error", async () => {
    vi.useFakeTimers();
    let fail = false;
    let n = 0;
    const fetchTree = vi.fn(async () => { n += 1; if (fail) throw new Error("síť"); return tree(n); });
    const store = createVaultStore({ fetchTree, pollMs: 0, debounceMs: 10 });
    const first = store.reload("p", "w");
    void store.reload("p", "w");
    await first;
    await vi.runAllTimersAsync();
    expect(fetchTree).toHaveBeenCalledTimes(2);
    fail = true;
    await store.reload("p", "w");
    expect(store.snapshot("p", "w")).toMatchObject({ error: "síť", tree: { feedback: [{ id: "2" }] } });
    vi.useRealTimers();
  });
});
