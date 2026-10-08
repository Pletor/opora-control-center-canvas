import { describe, expect, it } from "vitest";
import { buildDnaExport, type DnaExportInput } from "./dna-export";
const minimal = { node: { id: "n", name: "N", purpose: "" }, data: {}, state: { nodes: {}, rules: [], decisions: [] }, graph: { edges: [] }, results: [], partialHistory: false } as unknown as DnaExportInput;
it("exportuje načtené předávky i celý node-brief pro rekonstrukci", () => {
  const markdown = buildDnaExport({ ...minimal, brief: { upstream: [{ nodeId: "before" }] }, messages: [{ id: "third-page", body: "Doložená předávka" }] });
  expect(markdown).toContain("Doložená předávka"); expect(markdown).toContain("third-page"); expect(markdown).toContain("upstream");
});
it("chybějící pole jsou nedoloženo, nikdy undefined", () => {
  const markdown = buildDnaExport({ ...minimal, results: [{}] as never });
  expect(markdown).toContain("nedoloženo"); expect(markdown).not.toContain("undefined");
});
it("neúplné zprávy nesmějí tvrdit úplnost historie", () => {
  const markdown = buildDnaExport({ ...minimal, partialHistory: true });
  expect(markdown).toContain("zpráv"); expect(markdown).toContain("není kompletní");
});

describe("buildDnaExport", () => {
  it("preserves the complete real reconstruction payload instead of inventing flat assignment fields", () => {
    const markdown = buildDnaExport({
      node: { id: "n", name: "DNA", purpose: "Ship", parentId: null, kind: "node", x: 0, y: 0, sourceRef: { origin: "planned", kind: "file", path: "frontend/dna.ts" }, realization: { commit: "abc123", prUrl: "https://github/pr/1", verifiedAt: "2026-01-04T00:00:00Z" } },
      data: { view: {} as never, evidence: { tests: { status: "passed", url: "https://ci" }, checksRun: [{ checkId: "unit", command: "npm test", exitCode: 0, logUrl: "", at: "2026-01-03T00:00:00Z" }] } as never } as never,
      state: { settings: [], rules: [], tickets: [], decisions: [{ id: "d", nodeId: "n", text: "Keep API", path: "docs/api.md", pinned: true, by: "human", createdAt: "2026-01-02T00:00:00Z" }], nodes: { n: { phase: "build", criteria: [], steps: [], stages: { profile: "custom", items: [{ id: "s", kind: "work", lens: "", title: "Build", brief: "", status: "passed", note: "done", by: "agent", approved: true, doneBy: "Ada", at: "2026-01-01T00:00:00Z" }] } } } },
      graph: { nodes: [], edges: [] }, brief: { node: { id: "n", sourceRef: { path: "frontend/dna.ts" } }, goal: { goal: "Ship", nonGoals: "No backend", acceptance: "Tests pass" }, assignment: { goal: "Frozen goal" }, specification: { cards: [{ nodeId: "n", goal: "Ship" }] }, blocks: [{ id: "b", ports: [{ id: "p", onMet: "spawn" }] }], boundaries: { effectiveRules: [{ text: "Keep API" }] }, context: { decisions: [{ text: "Prior decision" }] }, evidence: { checksRun: [{ logUrl: "https://logs" }] } }, results: [{ id: "r", nodeId: "n", agent: "Ada", createdAt: "2026-01-01T01:00:00Z", binding: "bound", contextVersion: "v1", output: { note: "implemented" }, specification: { cards: [{ nodeId: "n", goal: "Frozen result" }] } }], partialHistory: true,
    });
    for (const expected of ["## Zadání", "Frozen goal", "## Pipeline", "Build — done", "## Důkazy", "https://logs", "npm test", "## Rozhodnutí", "Keep API", "## Historie agentů", "Frozen result", "Ada", "## Realizace", "abc123", "frontend/dna.ts", "## Rekonstrukční data", "effectiveRules", "⚠ Historie agentů není kompletní"]) expect(markdown).toContain(expected);
  });
});
