import { describe, expect, it } from "vitest";
import { normalizeWorkStatus, type WorkStatus } from "../live-status/logic/live-model";
import { emptySlot, slotFailed, slotLoaded } from "../live-status/logic/live-poll";
import type { WebHost } from "../live-status/logic/web-status";
import { emptyWeb, webLoaded } from "../live-status/logic/web-slots";
import { panelViews } from "./live-views";

const status = normalizeWorkStatus({ domains: [{ id: "d", name: "D", worktrees: [
  { id: "w1", state: "running", cards: [{ nodeId: "c1", name: "C1" }] },
  { id: "w2", state: "waiting", sessions: [{ source: "lease", id: "s", state: "active", nodeId: "p2" }] },
] }] });
const host: WebHost = { domainId: "d", environment: "Produkce", host: "www.a.cz", state: "dns_missing", httpStatus: null, health: null, latencyMs: null, checkedAt: null, detail: "" };
const live = { worktreeLive: true, work: slotLoaded(emptySlot<WorkStatus>(), status, 0), web: webLoaded(emptyWeb(), "*", [host], 0) };

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
});
