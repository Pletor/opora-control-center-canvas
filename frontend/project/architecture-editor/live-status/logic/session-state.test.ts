import { describe, expect, it } from "vitest";
import { normalizeWorkStatus } from "./live-model";
import { mainSessionsSummary, relativeAge, sessionTitle, sessionView, stateChanges } from "./session-state";

const NOW = Date.parse("2026-10-14T12:00:00Z");
const s = (state: string) => ({ source: "assistant" as const, id: state, state, nodeId: null, lastSeenAt: null });

describe("stavy relací", () => {
  it("relace má zdroj, slovo, ikonu a title s posledním signálem", () => {
    const view = sessionView({ source: "assistant", id: "s1", state: "waiting_approval", nodeId: null, lastSeenAt: "2026-10-14T11:57:00Z" }, NOW);
    expect(view).toMatchObject({ source: "Asistent", label: "čeká na schválení", tone: "waiting", icon: "⏸" });
    expect(view.title).toBe("Asistent: čeká na schválení · poslední signál před 3 min");
  });
  it("neznámý stav se ukáže slovem a neutrálně", () => {
    expect(sessionView({ source: "hook", id: "h", state: "odd", nodeId: null, lastSeenAt: null }, NOW)).toMatchObject({ label: "odd", tone: "none" });
  });
  it("relativní čas i bez zóny (UTC)", () => {
    expect(relativeAge("2026-10-14T11:59:30", NOW)).toBe("před chvílí");
    expect(relativeAge("2026-10-14T10:00:00Z", NOW)).toBe("před 2 h");
    expect(relativeAge("nesmysl", NOW)).toBe("neznámo kdy");
  });
  it("souhrn hlavních relací nepočítá zavřené", () => {
    expect(mainSessionsSummary([s("idle"), s("running"), s("closed")])).toBe("Hlavní relace: 1 běží · 1 čeká");
    expect(mainSessionsSummary([s("closed")])).toBe("Hlavní relace: žádná");
    expect(mainSessionsSummary([])).toBe("Hlavní relace: žádná");
  });
  it("aria-live hlásí jen změny stavu, první čtení mlčí", () => {
    const status = (state: string) => normalizeWorkStatus({ domains: [{ id: "d", name: "D", worktrees: [{ id: "w1", branch: "work/w1", state }] }] });
    expect(stateChanges(null, status("running"))).toBe("");
    expect(stateChanges(status("running"), status("running"))).toBe("");
    expect(stateChanges(status("running"), status("waiting"), "d")).toBe("Worktree work/w1: čeká.");
    expect(stateChanges(status("running"), status("waiting"), "other")).toBe("");
  });
});

describe("název nové relace", () => {
  it("říká, odkud relace vznikla, a drží strop 120 znaků", () => {
    expect(sessionTitle("main")).toBe("Hlavní relace");
    expect(sessionTitle("worktree", "work/a1")).toBe("Worktree work/a1");
    expect(sessionTitle("card", "x".repeat(200))).toHaveLength(120);
  });
});
