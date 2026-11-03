import { describe, expect, it } from "vitest";
import { cardTrailUrl, parseCardTrail } from "./card-trail";

const sample = {
  nodeId: "n0",
  now: { owner: "agent:builder", since: "2026-10-31T11:00:00Z", until: "2026-10-31T12:00:00Z", stepId: "s2", source: "det" },
  runs: [{ executionId: "e1", ticketId: null, owner: "agent:builder", createdAt: "2026-10-31T11:00:00Z", until: null, state: "reported",
    summary: "Doplnil test.", source: "agent", attempts: 1, reported: true,
    steps: [{ stepId: "s1", title: "Test modulu", status: "done", checks: [{ name: "npm test", status: "green" }, { status: "red" }],
      commits: ["abc1234"], notes: "test x", source: "agent", files: ["backend/x/a.py"], allowed: ["backend/x/**"] }] }, "rozbité"],
  pr: { number: 7, state: "open" },
  missing: ["merged", 3],
  recent: [{ at: "2026-10-31T11:05:00Z", who: "builder", label: "Krok hotový", kind: "step.done", source: "det" }, { who: "bez času" }],
  ports: [{ edgeId: "e1", targetId: "n1", targetName: "Karta 1", summary: "Hotové API", handoff: "Použij /x", by: "builder",
    updatedAt: "2026-10-31T11:06:00Z", source: "weird" }],
  judgment: [{ code: "files_mismatch", stepId: "s1", executionId: "e1", outside: ["docs/a.md"], reason: "Mimo soubory.", source: "det" }],
  filesKnown: true,
};

describe("card-trail", () => {
  it("čte odpověď a vynechá položky v jiném tvaru", () => {
    const trail = parseCardTrail(sample);
    expect(trail.runs).toHaveLength(1);
    expect(trail.runs[0].steps[0].checks).toEqual([{ name: "npm test", status: "green" }]);
    expect(trail.recent).toHaveLength(1);
    expect(trail.missing).toEqual(["merged"]);
    expect(trail.ports[0].source).toBe("det");
    expect(trail.now).toEqual({ owner: "agent:builder", since: "2026-10-31T11:00:00Z", until: "2026-10-31T12:00:00Z", stepId: "s2" });
    expect(trail.pr).toEqual({ number: 7, state: "open" });
  });

  it("odmítne celek bez nodeId a pozná soubory, které server nezná", () => {
    expect(() => parseCardTrail({ runs: [] })).toThrow();
    const trail = parseCardTrail({ nodeId: "n", runs: [{ createdAt: "x", state: "running", steps: [{ stepId: "s1" }] }] });
    expect(trail.runs[0].steps[0].files).toBeNull();
    expect(trail.filesKnown).toBe(false);
    expect(trail.now).toBeNull();
  });

  it("adresa nese projekt, prostor a kartu", () => {
    expect(cardTrailUrl("p", "w", "n 1")).toBe("/api/oporahub/card-trail?project=p&workspace=w&node=n+1");
  });
});
