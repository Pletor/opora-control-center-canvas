import { describe, expect, it } from "vitest";
import type { Graph, GraphEdge } from "@/shared/types/logic/types";
import { emptyDesktopState, type DesktopState } from "@/shared/desktop-state/logic/types";
import { buildBoardIndex, childCount, ownNodeRules } from "./board-index";
import { layerEdges } from "./board-edges";
import { upstreamRows } from "@/editor/canvas/node-card/logic/upstream";
import { effectiveRules } from "@/editor/canvas/node-card/logic/effective-rules";
import { sectorViews } from "@/editor/canvas/node-card/logic/sector-status";
import { proposalCount, proposalsIn } from "@/editor/canvas/node-card/logic/completion-proposals";
import { handoffMark, nodeKinds } from "@/editor/canvas/card-checklist/logic/card-checklist";

/** Syntetický graf se vším, na čem index může selhat: vnořené sektory, brány se scénářem, cyklus rodičů,
 *  vazby toku a do neexistujících uzlů, nahrazená rozhodnutí, pravidla projektu, cesty i uzlu. */
function synth(cards = 120): { graph: Graph; state: DesktopState } {
  let seed = 7;
  const rnd = () => ((seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);
  const graph: Graph = { nodes: [], edges: [] };
  const state = emptyDesktopState();
  const sectors = ["s-0", "s-1", "s-2", "s-3"];
  sectors.forEach((id, i) => graph.nodes.push({ id, parentId: i === 3 ? "s-0" : null, kind: "sector", name: "Sektor " + i, purpose: "", x: 0, y: 0,
    gateNodeId: i === 1 ? "n-5" : i === 2 ? "missing" : undefined }));
  for (let i = 0; i < cards; i++) {
    const id = "n-" + i;
    const parentId = i % 4 === 0 ? null : sectors[i % sectors.length];
    const kind = i % 17 === 0 ? "comment" : i % 23 === 0 ? "area" : "node";
    graph.nodes.push({ id, parentId, kind, name: "Karta " + i, purpose: "", x: i, y: i,
      sourceRef: i % 6 === 0 ? { origin: "planned", path: i % 12 === 0 ? "backend/api/x.py" : "frontend/y.ts", kind: "file" } : undefined,
      scenario: i === 5 ? { command: "npm test" } : undefined });
    state.nodes[id] = { phase: "build", criteria: [], steps: [],
      rules: i % 5 === 0 ? [{ id: "own" + i, text: "vlastní", kind: "must" }] : [],
      blocks: [{ id: id + "-b", number: "1", title: "B", text: "", tags: [], todos: [], images: [], parentBlockId: "",
        state: { status: "open", condition: "", onMet: { kind: "none", targetId: "", note: "" }, onUnmet: { kind: "none", targetId: "", note: "" } },
        ports: [{ id: "p1", label: "Ano", status: i % 3 === 0 ? "chosen" : undefined, reason: "proto" }, { id: "p2", label: "Ne", status: i % 7 === 0 ? "rejected" : undefined }] }],
      done: i % 5 === 0 ? { confirmed: false, at: "", by: "agent", note: "návrh" } : i % 3 === 0 ? { confirmed: true, at: "", by: "human", note: "" } : undefined,
      scenarioRun: i === 5 ? { command: "npm test", at: "", passed: 1, failed: 0, logUrl: "", firstFailure: "" } : undefined };
    if (i % 3 === 0) state.rules.push({ id: "nr" + i, text: "uzel", kind: "must", scope: "node", target: i % 9 === 0 ? sectors[i % 4] : id });
    if (i % 11 === 0) state.rules.push({ id: "pr" + i, text: "cesta", kind: "must_not", scope: "path", target: i % 22 === 0 ? "backend" : "front" });
    if (i % 4 === 0) state.decisions.push({ id: "d" + i, text: "rozhodnutí", pinned: false, path: "", nodeId: id, createdAt: "", by: "human",
      supersedes: i % 8 === 0 && i > 0 ? "d" + (i - 4) : undefined });
  }
  state.rules.splice(3, 0, { id: "proj", text: "projekt", kind: "must", scope: "project", target: "" });
  // Cyklus rodičů: ochrana proti zacyklení musí platit s indexem i bez něj.
  graph.nodes.push({ id: "loop-a", parentId: "loop-b", kind: "node", name: "A", purpose: "", x: 0, y: 0 },
    { id: "loop-b", parentId: "loop-a", kind: "sector", name: "B", purpose: "", x: 0, y: 0 });
  const ids = graph.nodes.map((n) => n.id).concat("ghost");
  for (let e = 0; e < cards * 2; e++) {
    const source = ids[Math.floor(rnd() * ids.length)], target = ids[Math.floor(rnd() * ids.length)];
    const port = (["next", "block", "flow", "rule", undefined] as const)[e % 5];
    const edge: GraphEdge = { id: "e" + e, source, target, port };
    if (port === "block") Object.assign(edge, { sourceBlockId: source + "-b", sourcePortId: e % 2 ? "p1" : "p2" });
    graph.edges.push(edge);
    if (e % 4 === 0) (state.edges ??= {})[edge.id] = { log: "", summary: "shrnutí", handoff: e % 8 ? "předáno" : "", improvements: "", errors: "", updatedAt: "", by: "agent", agent: "w" };
  }
  sectors.forEach((target, i) => graph.edges.push({ id: "into-" + i, source: sectors[(i + 1) % 4], target, port: "next" }));
  return { graph, state };
}

describe("index plátna dává stejné výsledky jako průchod celým grafem", () => {
  const { graph, state } = synth();
  const index = buildBoardIndex(graph, state);
  const all = graph.nodes.map((n) => n.id).concat("ghost");

  it("počty dětí a vlastní pravidla karty", () => {
    for (const id of all) {
      expect(childCount(index, id)).toBe(graph.nodes.filter((c) => c.parentId === id).length);
      expect(ownNodeRules(index, id)).toEqual(state.rules.filter((rule) => rule.scope === "node" && rule.target === id));
    }
  });

  it("přítoky z předchozích karet", () => {
    let rows = 0;
    for (const id of all) {
      const plain = upstreamRows(graph, state, id);
      rows += plain.length;
      expect(upstreamRows(graph, state, id, index)).toEqual(plain);
    }
    expect(rows).toBeGreaterThan(50);
    expect(all.some((id) => upstreamRows(graph, state, id).some((row) => row.details.includes("Nahrazeno: ")))).toBe(true);
  });

  it("platná pravidla včetně pořadí", () => {
    for (const id of all) expect(effectiveRules(graph, state, id, index)).toEqual(effectiveRules(graph, state, id));
    expect(effectiveRules(graph, state, "n-12").map((r) => r.origin.scope)).toContain("path");
  });

  it("stav sektorů a co je blokuje", () => {
    const plain = sectorViews(graph, state);
    expect(sectorViews(graph, state, index)).toEqual(plain);
    expect(plain["s-0"].total).toBeGreaterThan(0);
  });

  it("návrhy uzavření pod každým rodičem", () => {
    for (const parent of [null, ...all]) {
      expect(proposalsIn(graph, state, parent, index)).toEqual(proposalsIn(graph, state, parent));
      expect(proposalCount(graph, state, parent, index)).toBe(proposalCount(graph, state, parent));
    }
  });

  it("obálka předávky z jedné mapy druhů", () => {
    const kinds = nodeKinds(graph.nodes);
    for (const edge of graph.edges) expect(handoffMark(edge, state, index.kinds)).toBe(handoffMark(edge, state, kinds));
  });
});

describe("vazby vrstvy", () => {
  it("jen mezi vykreslenými uzly, s pulsem, výběrem a šipkami bloků na konci", () => {
    const { graph, state } = synth(40);
    const index = buildBoardIndex(graph, state);
    const ids = new Set(graph.nodes.filter((n) => n.id !== "n-1").map((n) => n.id));
    const blockEdge = { id: "blk", source: "n-0", target: "block:n-0:action" };
    const inLayer = graph.edges.filter((e) => ids.has(e.source) && ids.has(e.target));
    const edges = layerEdges({ graph, state, ids, kinds: index.kinds, added: new Set([inLayer[0].id]), selectedEdge: inLayer[1].id, blockEdges: [blockEdge] });
    expect(edges.map((e) => e.id)).toEqual([...inLayer.map((e) => e.id), "blk"]);
    expect(edges.filter((e) => e.animated).map((e) => e.id)).toEqual([inLayer[0].id]);
    expect(edges.filter((e) => e.selected).map((e) => e.id)).toEqual([inLayer[1].id]);
    const sent = inLayer.find((e) => handoffMark(e, state, index.kinds) === "sent");
    expect(sent).toBeDefined();
    expect(edges.find((e) => e.id === sent?.id)?.style?.stroke).toBe("#22c55e");
  });
});
