import { describe, expect, it } from "vitest";
import { acceptanceSentence, failureText, previewSentence, workActions, workDetail } from "./linie-work";

const raw = {
  ticketId: "tk_1", status: "issued", state: "accepted_unmerged", stateLabel: "hotovo, ještě nezačleněno", next: "allow-merge",
  body: { essence: "Panel detailu\nvíc", build: "panel", doneCriteria: ["testy", "build"] },
  work: { rowId: "row_k", branch: "feat/detail", baseBranch: "develop", baseSha: "b".repeat(40), headSha: "h".repeat(40), target: "develop",
    checks: [{ name: "npm test", status: "green", sha: "h".repeat(40) }], acceptance: { sha: "h".repeat(40), note: "ok", at: "", revision: "3" },
    mergeAllowed: null, merged: null, preview: { slug: "p", sha: "o".repeat(40) }, blocked: null },
};

describe("workDetail", () => {
  it("plochý ticket i obálka {ticket, work}", () => {
    expect(workDetail(raw)).toMatchObject({ ticketId: "tk_1", title: "Panel detailu", doneCriteria: "testy\nbuild", target: "develop", checks: [{ name: "npm test", status: "green" }] });
    const wrapped = workDetail({ ticket: { id: "tk_1", title: "T", body: raw.body }, work: raw.work, state: "open" });
    expect([wrapped.ticketId, wrapped.title, wrapped.branch]).toEqual(["tk_1", "T", "feat/detail"]);
    expect(workDetail(null).acceptance).toBeNull();
  });
  it("náhled s revizí a přiznaný chybějící náhled", () => {
    const d = workDetail(raw);
    expect(previewSentence(d)).toBe("náhled zobrazuje ooooooo, hlava je hhhhhhh – náhled není z hlavy");
    expect(previewSentence({ ...d, preview: null })).toBe("náhled této revize není dostupný");
    expect(acceptanceSentence(d)).toBe("přijato hhhhhhh (platí pro hlavu) · ok");
  });
  it("tlačítka podle stavu: přijato → povolit, ne znovu přijmout; nasazení jen po merge do main", () => {
    const d = workDetail(raw);
    expect(workActions(d, "main")).toEqual({ preview: true, accept: false, revoke: true, allow: true, merge: false, deploy: false });
    expect(workActions({ ...d, merged: { sha: "m", target: "main", at: "" } }, "main")).toMatchObject({ deploy: true, merge: false, accept: false });
  });
  it("409 ukáže message z těla", () => {
    expect(failureText(Object.assign(new Error("head_moved"), { body: { message: "Hlava se posunula." } }))).toBe("Hlava se posunula.");
    expect(failureText(new Error("x"))).toBe("x");
  });
});
