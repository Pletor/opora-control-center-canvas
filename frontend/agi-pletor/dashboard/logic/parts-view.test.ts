import { describe, expect, it } from "vitest";
import { contextView } from "./context-view";
import { heartView } from "./heart-view";
import { messagesUrl, messagesView } from "./messages-view";
import { monitoringView } from "./monitoring-view";

describe("heartView", () => {
  it("mapuje karty, frontu a dávky", () => {
    const view = heartView({ status: { running: true, pending: 2, sleeping: true, sleepingUntil: "10:00" }, queue: [{ workspace: "main", pending: 2 }],
      batches: [{ at: "t", ok: true, summary: "s", costUsd: 0.1234 }], gate: true, brain: { version: "m10" } });
    expect(view.cards.find((c) => c.id === "spi")?.value).toBe("spí do 10:00");
    expect(view.cards.find((c) => c.id === "verze")?.value).toBe("m10");
    expect(view.queue).toEqual([{ workspace: "main", pending: "2" }]);
    expect(view.batches[0]).toMatchObject({ status: "ok", cost: "0.123 USD" });
  });
  it("chybějící pole a {error} sekce", () => {
    const view = heartView({ status: { error: "boom" }, queue: { error: "x" } });
    expect(view.queue).toEqual([]);
    expect(view.problem).toBe("nedostupné: boom · nedostupné: x");
    expect(heartView(null).cards).toHaveLength(6);
  });
});

describe("contextView / messagesView / monitoringView", () => {
  it("podklady", () => {
    const view = contextView({ text: "abc", sections: [{ title: "A", chars: 5, cap: 10, truncated: true }] });
    expect(view.sections[0]).toEqual({ title: "A", size: "5 / 10", truncated: true });
    expect(contextView({ text: { error: "e" } }).problem).toBe("nedostupné: e");
  });
  it("rozhovor", () => {
    expect(messagesView({ messages: [{ role: "human", text: "a", at: "t" }], total: 7 })).toMatchObject({ total: 7, messages: [{ role: "Člověk" }] });
    expect(messagesUrl("p", "w", 50, " ")).not.toContain("q=");
    expect(messagesUrl("p", "w", 50, "x")).toContain("q=x");
  });
  it("monitoring", () => {
    const view = monitoringView({ enabled: true, hosts: [{ host: "h", state: "ok" }], events: [{ ts: "1", type: "a", payload: { actor: "bob" } }, { ts: "2", type: "b", payload: {} }] });
    expect(view.events[0].type).toBe("b");
    expect(view.events[1].author).toBe("bob");
    expect(monitoringView({ hosts: { error: "e" } }).problem).toBe("nedostupné: e");
  });
});
