import { describe, expect, it } from "vitest";
import { countsLine, domainLive, normalizeWorkStatus, sortWorktrees, type LiveWorktree } from "./live-model";

const wt = (id: string, state: LiveWorktree["state"], createdAt = "", cards: string[] = [], sessionNode: string | null = null): LiveWorktree => ({
  id, branch: "work/" + id, actor: "a", createdAt, state, reasons: [], cards: cards.map((nodeId) => ({ nodeId, name: nodeId })),
  sessions: sessionNode ? [{ source: "lease", id: "s-" + id, state: "active", nodeId: sessionNode, lastSeenAt: null }] : [],
});

describe("model živého stavu", () => {
  it("nejživější worktree nahoře, uvnitř stavu novější první", () => {
    const sorted = sortWorktrees([wt("a", "none"), wt("b", "waiting", "2026-01-01"), wt("c", "running"), wt("d", "waiting", "2026-02-01")]);
    expect(sorted.map((item) => item.id)).toEqual(["c", "d", "b", "a"]);
  });
  it("normalizuje odpověď API a přepočítá počty z worktree", () => {
    const status = normalizeWorkStatus({ domains: [{ id: "d", name: "D", environment: { name: "Produkce", host: "www.a.cz" }, worktrees: [{ id: "w1", state: "running", cards: [{ nodeId: "c1" }] }, { id: "w2", state: "bogus" }] }], unassigned: [{ id: "u", state: "waiting" }] });
    const domain = domainLive(status, "d")!;
    expect(domain.counts).toEqual({ running: 1, waiting: 0, stopped: 0, none: 1, total: 2 });
    expect(domain.worktrees[0].cards).toEqual([{ nodeId: "c1", name: "c1" }]);
    expect(status.unassigned[0].state).toBe("waiting");
    expect(domainLive(status, "x")).toBeNull();
    expect(normalizeWorkStatus(undefined)).toEqual({ domains: [], unassigned: [] });
  });
  it("věta s počty vynechá nulové stavy", () => {
    expect(countsLine({ running: 1, waiting: 1, stopped: 0, none: 1, total: 3 })).toBe("3 worktree · 1 běží · 1 čeká");
    expect(countsLine({ running: 0, waiting: 0, stopped: 2, none: 0, total: 2 })).toBe("2 worktree · 2 stojí");
    expect(countsLine({ running: 0, waiting: 0, stopped: 0, none: 0, total: 0 })).toBe("Žádný worktree");
  });
});
