import { describe, expect, it } from "vitest";
import { commitView } from "./linie-commit";

const full = {
  commit: { sha: "2522dc84aa", sha7: "2522dc8", title: "fix", body: "b", at: "t", author: "Pletor", files: 3, stat: "3 files", branches: ["feat/x"], trailers: { mark: "OP-3F9A1C" } },
  ticket: {
    ticketId: "tk_1", mark: "OP-3F9A1C", state: "open", stateLabel: "otevřeno", next: "n", body: { essence: "E\nx", build: "B", doneCriteria: ["a", "b"] },
    work: { branch: "feat/x" }, card: { id: "hero", name: "Hero", link: "/?node=hero" },
    office: { worker: "office-1", role: "worker", department: "d", profile: "p", executionId: "ex_1" },
    plan: [{ id: "s2", order: 2, title: "B" }, { id: "s1", order: 1, title: "A", acceptance: "ok", kind: "code" }],
  },
  pr: { number: 350, state: "OPEN", url: "u" }, preview: { url: "http://x", state: "running", sha: "2522dc8" }, sentence: "věta",
};

describe("commitView", () => {
  it("plný JSON", () => {
    const v = commitView(full);
    expect(v.commit).toMatchObject({ sha7: "2522dc8", files: "3", branches: ["feat/x"] });
    expect(v.ticket).toMatchObject({ ticketId: "tk_1", title: "E", essence: "E\nx", doneCriteria: ["a", "b"], branch: "feat/x" });
    expect(v.ticket?.card?.link).toBe("/?node=hero");
    expect(v.ticket?.office?.worker).toBe("office-1");
    expect(v.ticket?.plan.map((s) => s.id)).toEqual(["s1", "s2"]);
    expect([v.commit.mark, v.ticket?.mark]).toEqual(["OP-3F9A1C", "OP-3F9A1C"]);
    expect(v.pr?.number).toBe("350");
    expect(v.preview?.url).toBe("http://x");
    expect(v.sentence).toBe("věta");
  });
  it("null nespadne", () => {
    const v = commitView(null);
    expect(v.ticket).toBeNull();
    expect(v.pr).toBeNull();
    expect(v.preview).toBeNull();
    expect(v.commit.branches).toEqual([]);
    expect(v.commit.mark).toBe("");
    expect(v.sentence).toBe("");
  });
  it("chybějící ticket a office", () => {
    expect(commitView({ ...full, ticket: undefined }).ticket).toBeNull();
    expect(commitView({ ...full, ticket: { ticketId: "t", office: null, card: null } }).ticket).toMatchObject({ office: null, card: null, plan: [] });
  });
});
