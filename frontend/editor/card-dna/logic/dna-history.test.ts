import { describe, expect, it } from "vitest";
import { buildDnaTimeline, filterDnaTimeline } from "./dna-history";

describe("buildDnaTimeline", () => {
  it("neúplná historická data nesmějí zobrazit undefined", () => {
    const rows = buildDnaTimeline({ node: { id: "n", realization: { verifiedAt: "2026-01-01" } }, data: { evidence: { checksRun: [{ checkId: "c" }] } }, state: { nodes: {}, decisions: [] }, graph: { edges: [] }, results: [] } as never);
    expect(rows.map(row => `${row.label} ${row.detail ?? ""}`).join("\n")).not.toContain("undefined");
    expect(rows.some(row => row.label.includes("nedoloženo"))).toBe(true);
  });
  it("sorts every recorded source chronologically and assigns semantic groups", () => {
    const rows = buildDnaTimeline({
      node: { id: "n", name: "Card", purpose: "Goal", parentId: null, kind: "node", x: 0, y: 0, realization: { commit: "abc", prUrl: "", verifiedAt: "2026-01-05T00:00:00Z" } },
      data: { view: {} as never, lease: { owner: "Ada", expiresAt: 0, serverOffset: 0 } as never, evidence: { checksRun: [{ checkId: "unit", exitCode: 0, at: "2026-01-04T00:00:00Z" }] } as never } as never,
      state: { settings: [], rules: [], tickets: [], decisions: [{ id: "d", nodeId: "n", text: "Use API", path: "", pinned: false, by: "human", createdAt: "2026-01-03T00:00:00Z" }], nodes: { n: { phase: "build", criteria: [], steps: [], stages: { profile: "custom", items: [{ id: "s", kind: "work", lens: "", title: "Build", brief: "", status: "passed", note: "implemented", by: "agent", approved: true, doneBy: "Ada", at: "2026-01-02T00:00:00Z" }] } } }, edges: { e: { log: "", summary: "handoff", handoff: "next", improvements: "", errors: "", by: "agent", agent: "Ada", updatedAt: "2026-01-03T12:00:00Z" } } },
      graph: { nodes: [], edges: [{ id: "e", source: "n", target: "next" }] },
      brief: { specification: { cards: [{ nodeId: "n", goal: "Original" }] }, contextVersion: "v1", communication: { incoming: { messages: [{ id: "in", body: "Received", senderLabel: "Prior agent", createdAt: "2026-01-03T05:00:00Z" }] }, outgoing: { messages: [{ id: "out", body: "Ready", senderLabel: "Ada", createdAt: "2026-01-03T06:00:00Z" }] } } },
      results: [{ id: "r", nodeId: "n", agent: "Ada", createdAt: "2026-01-02T12:00:00Z", binding: "bound", contextVersion: "v0", output: {}, specification: { goal: "Old" } }],
    });
    expect(rows.map(row => row.label)).toEqual(["Etapa · Build", "Snímek zadání", "Výstup agenta · Ada", "Rozhodnutí", "Příchozí zpráva · Prior agent", "Odchozí zpráva · Ada", "Zpráva na vazbě", "Kontrola · unit", "Realizace · abc"]);
    expect(filterDnaTimeline(rows, "Předávky").map(row => row.label)).toEqual(["Rozhodnutí", "Příchozí zpráva · Prior agent", "Odchozí zpráva · Ada", "Zpráva na vazbě"]);
  });

  it("keeps events without trustworthy timestamps after dated events", () => {
    const rows = buildDnaTimeline({ node: { id: "n", name: "Card", purpose: "", parentId: null, kind: "node", x: 0, y: 0 }, data: { view: {} as never } as never, state: { settings: [], rules: [], decisions: [], tickets: [], nodes: {} }, graph: { nodes: [], edges: [] }, results: [] });
    expect(rows).toHaveLength(0);
  });
});
