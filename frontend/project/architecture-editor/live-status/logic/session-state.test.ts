import { describe, expect, it } from "vitest";
import { normalizeWorkStatus } from "./live-model";
import { heartText, relativeAge, sessionView, sourceDetail, stateChanges } from "./session-state";

const NOW = Date.parse("2026-10-14T12:00:00Z");

describe("stavy relací", () => {
  it("hlavní slovo je stav worktree od backendu, surový stav zdroje jen v title", () => {
    const lease = { source: "lease" as const, id: "w:n", state: "active", nodeId: "n", lastSeenAt: "2026-10-14T11:56:00Z" };
    const view = sessionView(lease, "stopped", NOW);
    expect(view).toMatchObject({ source: "Karta", label: "stojí", tone: "stopped", icon: "■" });
    expect(view.title).toBe("Karta hlásí „převzatá“ · naposledy před 4 min · stav worktree: stojí");
  });
  it("převzatá karta nikdy nečeká sama od sebe, rozhoduje worktree", () => {
    const lease = { source: "lease" as const, id: "w:n", state: "active", nodeId: "n", lastSeenAt: null };
    expect(sessionView(lease, "none", NOW)).toMatchObject({ label: "bez relace", tone: "none" });
    expect(sourceDetail(lease, NOW)).toBe("Karta hlásí „převzatá“");
  });
  it("neznámý stav zdroje se ukáže slovem", () => {
    expect(sourceDetail({ source: "lease", id: "h", state: "odd", nodeId: null, lastSeenAt: null }, NOW)).toBe("Karta hlásí „odd“");
  });
  it("relativní čas i bez zóny (UTC)", () => {
    expect(relativeAge("2026-10-14T11:59:30", NOW)).toBe("před chvílí");
    expect(relativeAge("2026-10-14T10:00:00Z", NOW)).toBe("před 2 h");
    expect(relativeAge("nesmysl", NOW)).toBe("neznámo kdy");
  });
  it("aria-live hlásí jen změny stavu, první čtení mlčí", () => {
    const status = (state: string) => normalizeWorkStatus({ domains: [{ id: "d", name: "D", worktrees: [{ id: "w1", branch: "work/w1", state }] }] });
    expect(stateChanges(null, status("running"))).toBe("");
    expect(stateChanges(status("running"), status("running"))).toBe("");
    expect(stateChanges(status("running"), status("waiting"), "d")).toBe("Worktree w1: čeká.");
    expect(stateChanges(status("running"), status("waiting"), "other")).toBe("");
  });
});

describe("text pro srdce", () => {
  it("o worktree, nebo o kartě v něm", () => {
    expect(heartText("worktree", "work/a1")).toBe("Worktree «work/a1»: zjisti stav práce na jeho kartách a navrhni další krok.");
    expect(heartText("card", "work/a1", { nodeId: "c1", name: "Login" })).toBe(
      "Ve worktree «work/a1» posaď pracovníka ke kartě «Login» (`c1`): zadej úkol podle jejího `node-brief`.",
    );
  });
});
