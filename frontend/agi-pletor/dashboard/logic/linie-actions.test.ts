import { describe, expect, it } from "vitest";
import { boardFixture } from "./linie-fixture";
import { boardView } from "./linie-board";
import { judgementOf } from "./linie-summary";
import { workDetail } from "./linie-work";
import { actionRequest, actionsOf, sameRevision } from "./linie-actions";

const ball = boardView(boardFixture).balls[0]; // tk_1, board HEAD 9c8050f
const detail = (headSha: string) => workDetail({ ticketId: "tk_1", work: { headSha, target: "topic/knihovna" } });

describe("jedna cesta pro akce", () => {
  it("povolené z allowed, zakázané s důvodem z blocked", () => {
    expect(actionsOf(ball.judgement, "tk_1", ball.headSha7, detail("9c8050f1a2b3"))).toEqual([
      { id: "allow_merge", label: "Povolit začlenění", enabled: true, why: "" },
      { id: "block", label: "Blokovat", enabled: true, why: "" },
      { id: "preview", label: "Spustit náhled", enabled: true, why: "" },
      { id: "revoke_accept", label: "Zrušit přijetí", enabled: true, why: "" },
      { id: "accept", label: "Přijmout 9c8050f", enabled: false, why: "acceptance.accepted(HEAD) – už přijato" },
      { id: "merge", label: "Začlenit", enabled: false, why: "mergeAllowed chybí – nejdřív povolit začlenění" },
    ]);
  });
  it("nesoulad revize boardu a detailu (nebo detail ještě nenačtený) zablokuje vše", () => {
    const stale = actionsOf(ball.judgement, "tk_1", ball.headSha7, detail("1111111aaaa"));
    expect(stale.filter((a) => a.enabled)).toEqual([]);
    expect(stale[0].why).toBe("načítám aktuální revizi");
    expect(actionsOf(ball.judgement, "tk_1", ball.headSha7, null)[1].why).toBe("načítám aktuální revizi");
    expect(actionsOf(ball.judgement, "tk_9", ball.headSha7, detail("9c8050f1a2b3"))[0].enabled).toBe(false); // detail jiné kuličky
    expect([sameRevision("9c8050f", "9c8050f1a2b3"), sameRevision("", ""), sameRevision("9c8050f", "")]).toEqual([true, true, false]);
  });
  it("akce bez trasy zakázané; bez allowed nic", () => {
    const j = judgementOf({ allowed: ["unblock", "resume"] });
    expect(actionsOf(j, "tk_1", "", detail("")).map((a) => [a.id, a.enabled, a.why])).toEqual([["unblock", false, "operace zatím bez API (L7 PR 5)"], ["resume", true, ""]]);
    expect(actionsOf(judgementOf({}), "tk_1", "", null)).toEqual([]);
  });
  it("trasy akcí", () => {
    const d = detail("9c8050f1a2b3");
    expect(actionRequest("accept", "tk_1", d)).toEqual({ path: "/work/tk_1/accept", body: { sha: "9c8050f1a2b3", note: "" }, method: "POST", done: "Přijato 9c8050f." });
    expect(actionRequest("accept", "tk_1", d, "vypadá dobře")?.body).toEqual({ sha: "9c8050f1a2b3", note: "vypadá dobře" });
    expect(actionRequest("allow_merge", "tk_1", d)?.body).toEqual({ target: "topic/knihovna" });
    expect(actionRequest("revoke_accept", "tk_1", d)).toEqual({ path: "/work/tk_1/accept", body: {}, method: "DELETE", done: "Přijetí zrušeno." });
    expect(actionRequest("preview", "tk_1", d)?.path).toBe("/work/tk_1/preview");
    expect(actionRequest("park", "tk_1", d)?.path).toBe("/work/tk_1/defer");
    expect(actionRequest("unblock", "tk_1", d)).toBeNull();
  });
});
