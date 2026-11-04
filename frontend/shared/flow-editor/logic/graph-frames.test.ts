import { describe, expect, it } from "vitest";
import { heartGraph } from "./flow-fixtures";
import { removeNode, setNodeField } from "./graph-edit";
import { addNote, groupFromSelection, removeNote, setGroup, setNote, ungroup } from "./graph-frames";

describe("notes and frames are pure graph edits", () => {
  it("adds, edits, resizes and removes a sticky note", () => {
    const graph = addNote(heartGraph(), { x: 10.4, y: -200.6 });
    expect(graph.notes).toEqual([{ id: "poznamka-1", content: "## Poznámka\nCo se tady děje a proč.", x: 10, y: -201, width: 260, height: 160, color: 1 }]);
    const next = setNote(graph, "poznamka-1", { content: "# Ingest", color: 2, width: 20.2, height: 500.7 });
    expect(next.notes![0]).toMatchObject({ content: "# Ingest", color: 2, width: 80, height: 501, x: 10 });
    expect(removeNote(next, "poznamka-1").notes).toEqual([]);
    expect(heartGraph().notes).toBeUndefined();
  });
  it("makes a frame from the selection and refuses one node or a node already framed", () => {
    const { graph, group } = groupFromSelection(heartGraph(), ["jev", "srdce", "nic"]);
    expect(group).toEqual({ id: "ramec-1", name: "Rámec", description: "", nodeIds: ["jev", "srdce"] });
    expect(() => groupFromSelection(graph, ["srdce", "model"])).toThrow(/srdce už je v jiném rámci/);
    expect(() => groupFromSelection(graph, ["model"])).toThrow(/aspoň dva/);
    const named = setGroup(graph, "ramec-1", { name: "Rozhodnutí", description: "x".repeat(200) });
    expect(named.groups![0].name).toBe("Rozhodnutí");
    expect(named.groups![0].description).toHaveLength(145);
    expect(ungroup(named, "ramec-1").groups).toEqual([]);
  });
  it("drops a removed node from its frame and the empty frame with it", () => {
    const { graph } = groupFromSelection(heartGraph(), ["jev", "srdce"]);
    expect(removeNode(graph, "jev").groups![0].nodeIds).toEqual(["srdce"]);
    expect(removeNode(removeNode(graph, "jev"), "srdce").groups).toEqual([]);
  });
  it("sets and clears node fields of the flow canvas", () => {
    const graph = setNodeField(heartGraph(), "jev", "onError", "errorOutput");
    expect(graph.nodes[1].onError).toBe("errorOutput");
    expect("onError" in setNodeField(graph, "jev", "onError", undefined).nodes[1]).toBe(false);
  });
});
