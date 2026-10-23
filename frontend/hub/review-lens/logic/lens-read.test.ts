import { describe, expect, it } from "vitest";
import { LENS_READ, LENS_SPEC } from "./lens-fixture";
import { lensBadge, lensSummary, lensUrl, omittedLens, omittedText, parseLensRead, shownLens, specFacts } from "./lens-read";

describe("lens read", () => {
  it("parses the PR lens and summarises it for the mirror and the tab badge", () => {
    const read = parseLensRead(LENS_READ);
    expect(read.pr).toMatchObject({ kind: "pr", prNumber: 44, current: true, repository: "pletor/agent-office" });
    expect(lensSummary(shownLens(read))).toEqual({ kind: "pr", headSha: LENS_READ.lens.headSha, nodes: 3, edges: 2 });
    expect(lensBadge(read)).toBe("373909b");
    expect(lensUrl("p", "w", "c 1")).toBe("/api/oporahub/review-lens?project=p&workspace=w&nodeId=c+1");
  });
  it("shows the area map with the 'plán' badge until a PR lens exists", () => {
    const read = parseLensRead({ nodeId: "c", lens: null, area: { executionId: "e", acceptedRevision: "r1", by: "agent:w", createdAt: "t",
      lens: { kind: "area", headSha: null, validatedAt: "t", spec: LENS_SPEC } } });
    expect(read.pr).toBeNull();
    expect(shownLens(read)).toMatchObject({ kind: "area", headSha: null, acceptedRevision: "r1" });
    expect(lensBadge(read)).toBe("plán");
  });
  it("refuses a broken envelope and drops a lens without a full head sha or a graph spec", () => {
    expect(() => parseLensRead({ lens: null })).toThrow();
    expect(parseLensRead({ nodeId: "c", lens: { headSha: "abc" } }).pr).toBeNull();
    expect(parseLensRead({ nodeId: "c", lens: { ...LENS_READ.lens, spec: { kind: "patch" } } }).pr?.spec).toBeNull();
    expect(lensBadge(parseLensRead({ nodeId: "c", lens: null, area: null }))).toBe("");
  });
  it("keeps a PR lens without a spec as a note: too large or from an older head", () => {
    const { spec: _spec, ...bare } = LENS_READ.lens;
    const big = parseLensRead({ ...LENS_READ, lens: { ...bare, note: "spec too large" } });
    expect(big.pr).toMatchObject({ spec: null, note: "spec too large", stale: false });
    expect(omittedText(omittedLens(big)!)).toBe("Lens je příliš velký, viz PR #44.");
    const old = parseLensRead({ ...LENS_READ, lens: { ...bare, stale: true, note: "spec is from an older head" } });
    expect(omittedText(omittedLens(old)!)).toBe("Lens je ze starší verze, viz PR #44.");
    expect(omittedLens(parseLensRead(LENS_READ))).toBeNull();
    expect(parseLensRead({ ...LENS_READ, lens: { ...bare, note: 7 } }).pr?.note).toBeNull();
  });
  it("states size, parts and links in Czech", () => {
    expect(specFacts(LENS_SPEC)).toMatch(/^spec \d KB · 3 části · 2 vazby$/);
    expect(specFacts({ nodes: [1], edges: Array(9).fill(0) })).toBe("spec 1 KB · 1 část · 9 vazeb");
    expect(specFacts(null)).toBe("bez specu");
  });
});
