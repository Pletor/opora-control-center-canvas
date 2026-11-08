import { describe, expect, it } from "vitest";
import { acceptanceSentence, failureText, workDetail } from "./linie-work";

const raw = {
  ticketId: "tk_1", status: "issued", state: "accepted_unmerged", stateLabel: "hotovo, ještě nezačleněno", next: "allow-merge",
  body: { essence: "Panel detailu\nvíc", build: "panel", doneCriteria: ["testy", "build"] },
  work: { rowId: "row_k", branch: "feat/detail", baseBranch: "develop", baseSha: "b".repeat(40), headSha: "h".repeat(40), target: "develop",
    checks: [{ name: "npm test", status: "green", sha: "h".repeat(40) }], acceptance: { sha: "h".repeat(40), note: "ok", at: "", revision: "3" },
    mergeAllowed: null, merged: null, blocked: null },
  trial: { state: "stale", url: "http://x/", sha: "o".repeat(40), head: "h".repeat(40), tried: null, triedCurrent: false, news: [], newsMore: 0, steps: [] },
};

describe("workDetail", () => {
  it("plochý ticket i obálka {ticket, work}", () => {
    expect(workDetail(raw)).toMatchObject({ ticketId: "tk_1", title: "Panel detailu", doneCriteria: "testy\nbuild", target: "develop", checks: [{ name: "npm test", status: "green" }] });
    const wrapped = workDetail({ ticket: { id: "tk_1", title: "T", body: raw.body }, work: raw.work, state: "open" });
    expect([wrapped.ticketId, wrapped.title, wrapped.branch]).toEqual(["tk_1", "T", "feat/detail"]);
    expect(workDetail(null).acceptance).toBeNull();
  });
  it("zkouška z ticketu, bez ní none; přijetí s revizí", () => {
    const d = workDetail(raw);
    expect([d.trial.state, d.trial.url]).toEqual(["stale", "http://x/"]);
    expect(workDetail({ ticketId: "tk_2" }).trial.state).toBe("none");
    expect(acceptanceSentence(d)).toBe("přijato hhhhhhh (platí pro hlavu) · ok");
  });
  it("409 ukáže message z těla", () => {
    expect(failureText(Object.assign(new Error("head_moved"), { body: { message: "Hlava se posunula." } }))).toBe("Hlava se posunula.");
    expect(failureText(new Error("x"))).toBe("x");
    expect(failureText(Object.assign(new Error("not_tried"), { body: { error: "Nejdřív vyzkoušej hlavu." } }))).toBe("Nejdřív vyzkoušej hlavu.");
  });
});
