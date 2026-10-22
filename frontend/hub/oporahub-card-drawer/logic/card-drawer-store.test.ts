import { describe, expect, it } from "vitest";
import { createCardDrawerStore, parseDrawerLink, writeDrawerLink } from "./card-drawer-store";

function memoryLocation(search: string) {
  const box = { search };
  return { box, location: { read: () => box.search, write: (next: string) => { box.search = next; } } };
}

describe("card drawer deep link", () => {
  it("reads card and tab, falling back to Zadání for unknown tabs", () => {
    expect(parseDrawerLink("?ohCard=c1&ohTab=run")).toEqual({ nodeId: "c1", tab: "run" });
    expect(parseDrawerLink("?ohCard=c1&ohTab=lens")).toEqual({ nodeId: "c1", tab: "lens" });
    expect(parseDrawerLink("?ohCard=c1&ohTab=bogus")).toEqual({ nodeId: "c1", tab: "spec" });
    expect(parseDrawerLink("?environment=hub")).toBeNull();
  });
  it("writes and clears only its own parameters", () => {
    expect(writeDrawerLink("?environment=hub&layer=x", { nodeId: "c1", tab: "steps", nonce: 1 })).toBe("?environment=hub&layer=x&ohCard=c1&ohTab=steps");
    expect(writeDrawerLink("?environment=hub&ohCard=c1&ohTab=steps", null)).toBe("?environment=hub");
    expect(writeDrawerLink("?ohCard=c1", null)).toBe("");
  });
});

describe("card drawer store", () => {
  it("opens from the URL, switches tabs, keeps the tab when reopening the same card and closes", () => {
    const { box, location } = memoryLocation("?ohCard=c1&ohTab=review");
    const store = createCardDrawerStore(location);
    expect(store.get()).toMatchObject({ nodeId: "c1", tab: "review" });
    let calls = 0; store.subscribe(() => { calls++; });
    store.setTab("history");
    expect(box.search).toBe("?ohCard=c1&ohTab=history");
    store.open("c1");
    expect(store.get()?.tab).toBe("history");
    store.open("c2");
    expect(store.get()).toMatchObject({ nodeId: "c2", tab: "spec" });
    store.open("c2", "run");
    expect(store.get()?.tab).toBe("run");
    store.open("c2", "lens");
    expect(box.search).toBe("?ohCard=c2&ohTab=lens");
    store.close();
    expect(store.get()).toBeNull();
    expect(box.search).toBe("");
    expect(calls).toBe(6);
  });
  it("ignores empty ids and every open bumps the nonce", () => {
    const store = createCardDrawerStore();
    store.open("  ");
    expect(store.get()).toBeNull();
    store.open("a"); store.open("a");
    expect(store.get()?.nonce).toBe(2);
  });
});
