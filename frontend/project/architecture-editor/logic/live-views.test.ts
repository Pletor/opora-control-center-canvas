import { describe, expect, it } from "vitest";
import type { Graph } from "@/shared/types/logic/types";
import { normalizeWorkStatus, type WorkStatus } from "../live-status/logic/live-model";
import { emptySlot, slotFailed, slotLoaded } from "../live-status/logic/live-poll";
import type { WebHost } from "../live-status/logic/web-status";
import { pageWork, panelViews } from "./live-views";

const graph = { nodes: [
  { id: "d", parentId: null, kind: "sector", name: "d", purpose: "", x: 0, y: 0, site: { kind: "application", environments: [{ name: "Produkce", host: "www.a.cz" }] } },
  { id: "p1", parentId: "d", kind: "node", name: "p1", purpose: "", x: 0, y: 0, site: { kind: "page", path: "/" } },
  { id: "p2", parentId: "d", kind: "node", name: "p2", purpose: "", x: 0, y: 0, site: { kind: "page", path: "/b" } },
  { id: "c1", parentId: "p1", kind: "node", name: "c1", purpose: "", x: 0, y: 0 },
], edges: [] } as unknown as Graph;
const status = normalizeWorkStatus({ domains: [{ id: "d", name: "D", worktrees: [
  { id: "w1", state: "running", cards: [{ nodeId: "c1", name: "C1" }] },
  { id: "w2", state: "waiting", sessions: [{ source: "assistant", id: "s", state: "idle", nodeId: "p2" }] },
] }] });
const host: WebHost = { domainId: "d", environment: "Produkce", host: "www.a.cz", state: "dns_missing", httpStatus: null, health: null, latencyMs: null, checkedAt: null, detail: "" };
const live = { worktreeLive: true, work: slotLoaded(emptySlot<WorkStatus>(), status, 0), web: slotLoaded(emptySlot<WebHost[]>(), [host], 0) };

describe("data pro živý panel a mapu", () => {
  it("panel dostane host domény a stav práce; bez worktree jen web", () => {
    const views = panelViews(live, "d");
    expect(views.web.host?.state).toBe("dns_missing");
    expect(views.work).toMatchObject({ loaded: true, stale: "" });
    expect(views.work?.domain?.worktrees.map((w) => w.id)).toEqual(["w1", "w2"]);
    expect(panelViews({ ...live, worktreeLive: false }, "d").work).toBeNull();
  });
  it("načtený stav bez domény je prázdný, ne načítání", () => {
    expect(panelViews(live, "jina").work).toMatchObject({ domain: null, loaded: true });
    expect(panelViews({ ...live, work: slotFailed(emptySlot<WorkStatus>(), "síť") }, "d").work).toMatchObject({ loaded: false, error: "síť" });
  });
  it("odznaky stránek a zvýraznění vybraného worktree", () => {
    const work = pageWork(graph, live, "d", "w2")!;
    expect(Object.fromEntries(work.counts)).toEqual({ p1: 1, p2: 1 });
    expect([...work.highlighted]).toEqual(["p2"]);
    expect(pageWork(graph, live, "d", null)!.highlighted.size).toBe(0);
    expect(pageWork(graph, { ...live, worktreeLive: false }, "d", null)).toBeUndefined();
  });
});
