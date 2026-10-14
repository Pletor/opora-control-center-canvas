import { describe, expect, it } from "vitest";
import { normalizeWorkStatus } from "./live-model";
import { assistantTone, mainSessionsSummary, relativeAge, sessionTitle, sessionView, sourceDetail, stateChanges } from "./session-state";

const NOW = Date.parse("2026-10-14T12:00:00Z");
const s = (state: string) => ({ source: "assistant" as const, id: state, state, nodeId: null, lastSeenAt: null });

describe("stavy relací", () => {
  it("hlavní slovo je stav worktree od backendu, surový stav zdroje jen v title", () => {
    const hook = { source: "hook" as const, id: "h1", state: "active", nodeId: null, lastSeenAt: "2026-10-14T11:56:00Z" };
    const view = sessionView(hook, "stopped", NOW);
    expect(view).toMatchObject({ source: "Hook", label: "stojí", tone: "stopped", icon: "■", openable: false });
    expect(view.title).toBe("Hook hlásí „aktivní“ · naposledy před 4 min · stav worktree: stojí");
  });
  it("převzatá karta nikdy nečeká sama od sebe, rozhoduje worktree", () => {
    const lease = { source: "lease" as const, id: "w:n", state: "active", nodeId: "n", lastSeenAt: null };
    expect(sessionView(lease, "none", NOW)).toMatchObject({ label: "bez relace", tone: "none" });
    expect(sourceDetail(lease, NOW)).toBe("Karta hlásí „převzatá“");
  });
  it("otevřít jde jen relace asistenta; neznámý stav zdroje se ukáže slovem", () => {
    expect(sessionView({ source: "assistant", id: "s1", state: "idle", nodeId: null, lastSeenAt: null }, "waiting", NOW).openable).toBe(true);
    expect(sourceDetail({ source: "hook", id: "h", state: "odd", nodeId: null, lastSeenAt: null }, NOW)).toBe("Hook hlásí „odd“");
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
    expect(mainSessionsSummary(null)).toBe("Hlavní relace: nenačteno");
    expect(["running", "waiting_approval", "idle", "error", "closed"].map(assistantTone)).toEqual(["running", "waiting", "waiting", "stopped", "none"]);
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
