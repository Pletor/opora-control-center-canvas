import { describe, expect, it } from "vitest";
import { decisionEvidence, decisionHubUrl, newResearchTask, taskProblem, type ResearchTask } from "./research-decision";
import type { ResearchHeader } from "./research-types";

const task = (ref: string, dependsOn: string[] = [], nodeId?: string): ResearchTask => ({ ref, title: "Session expiration", goal: "Define provider expiry", acceptance: "Expired session is rejected", dependsOn, ...(nodeId ? { nodeId } : {}) });

describe("reviewed research becomes a concrete native proposal", () => {
  it("generates native graph proposal refs without forbidden underscores", () => {
    expect(newResearchTask().ref).toMatch(/^[a-z][a-z0-9-]{0,79}$/);
  });
  it("allows ordered dependencies but rejects cycles and missing task references", () => {
    expect(taskProblem([task("ui"), task("logic", ["ui"])], false)).toBe("");
    expect(taskProblem([task("ui", ["logic"]), task("logic", ["ui"])], false)).toContain("kruh");
    expect(taskProblem([task("logic", ["missing"])], false)).toContain("jiný úkol");
    expect(taskProblem([task("logic", ["logic"])], false)).toContain("jiný úkol");
  });
  it("requires scope and acceptance criteria and protects existing identities from duplicate updates", () => {
    expect(taskProblem([{ ...task("a"), acceptance: " " }], false)).toContain("kritérium");
    expect(taskProblem([task("a")], true)).toContain("Vyberte");
    expect(taskProblem([task("a", [], "node1"), task("b", [], "node1")], true)).toContain("dvakrát");
    expect(taskProblem([task("a", [], "node1"), task("b", ["a"], "node2")], true)).toBe("");
  });
  it("offers only sourced verified facts or observed evidence, excluding archives", () => {
    const card = (id: string, status: ResearchHeader["verification"]["status"], sourceCount: number, archived = false) => ({ id, verification: { status }, sourceCount, archived }) as ResearchHeader;
    const cards = [card("fact", "verified", 1), card("observation", "observed", 1), card("guess", "inference", 1), card("missing", "verified", 0), card("old", "verified", 1, true)];
    expect(decisionEvidence(cards).map(item => item.id)).toEqual(["fact", "observation"]);
  });
  it("opens the native Hub in the identical project and workspace without approval commands", () => {
    const params = new URLSearchParams(decisionHubUrl({ project: "prague", workspace: "login" }).slice(1));
    expect(Object.fromEntries(params)).toEqual({ project: "prague", workspace: "login", environment: "hub", mode: "structure" });
  });
});
