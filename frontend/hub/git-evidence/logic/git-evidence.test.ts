import { describe, expect, it } from "vitest";
import { EvidenceRequests, evidencePayload, evidenceReason, planReviewMarker, pullRequestLink } from "./git-evidence";

const revision = "a".repeat(40);
describe("GitHub evidence input boundaries", () => {
  it("sends only identifiers and the exact accepted revision, without a client verdict", () => {
    expect(evidencePayload("project", "draft", revision, " 10 ")).toEqual({
      project: "project", workspace: "draft", expectedAcceptedHead: revision, prNumber: 10,
    });
  });
  it.each(["0", "-1", "01", "1.1", "1e2", "0x10", "9007199254740993", "", "NaN", "1/2"])("rejects ambiguous or unsafe PR number %s", input => {
    expect(() => evidencePayload("p", "w", revision, input)).toThrow();
  });
  it.each([null, "", "short", "G".repeat(40)])("requires a full accepted revision: %s", value => {
    expect(() => evidencePayload("p", "w", value, "1")).toThrow();
  });
  it("constructs links only for GitHub repository names and positive safe integers", () => {
    expect(pullRequestLink("Pletor/opora-control-center-canvas", 10)).toBe("https://github.com/Pletor/opora-control-center-canvas/pull/10");
    for (const repository of ["https://evil.test", "x/y/../../../evil", "x/y?url=evil", "x/y#fragment", "x@y/z", "x/.."]) {
      expect(pullRequestLink(repository, 10)).toBeNull();
    }
    for (const number of [0, -1, 0.5, Number.MAX_SAFE_INTEGER + 1]) expect(pullRequestLink("x/y", number)).toBeNull();
  });
  it("copies the exact revision-bound review marker", () => {
    expect(planReviewMarker("project", "worktree-1", revision)).toBe(`Opora-Plan: project/worktree-1@${revision}`);
  });
  it("unknown backend reasons never imply approval", () => {
    expect(evidenceReason("new-server-policy")).toContain("nelze považovat za ověřený");
    expect(evidenceReason("stale-revision-or-head")).toContain("starší");
  });
});

describe("request generations isolate late responses", () => {
  it("a scope change rejects a delayed success from the previous project", async () => {
    const requests = new EvidenceRequests();
    const valid = requests.next();
    let deliver!: (value: string) => void;
    const response = new Promise<string>(resolve => { deliver = resolve; });
    let shown = "new project";
    const completed = response.then(value => { if (valid()) shown = value; });
    requests.invalidate();
    deliver("old successful observation");
    await completed;
    expect(shown).toBe("new project");
  });
  it("a newer failed read cannot be replaced by an older successful read", () => {
    const requests = new EvidenceRequests();
    const oldSuccess = requests.next();
    const latestFailure = requests.next();
    expect(latestFailure()).toBe(true);
    expect(oldSuccess()).toBe(false);
  });
  it("detail selection has an independent generation from the list", () => {
    const list = new EvidenceRequests();
    const detail = new EvidenceRequests();
    const currentList = list.next();
    const oldDetail = detail.next();
    const nextDetail = detail.next();
    expect(currentList()).toBe(true);
    expect(oldDetail()).toBe(false);
    expect(nextDetail()).toBe(true);
  });
});
