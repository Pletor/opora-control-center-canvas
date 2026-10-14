import { describe, expect, it } from "vitest";
import { coverageOf, type VaultNode } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { filterByTrack, ideaTarget, parseTrack, pickTrack, trackCounts, viewOf, TRACK_VIEWS } from "./vault-tracks";
import { flatten } from "./vault-dock-model";

let seq = 0;
const node = (title: string, extra: Partial<VaultNode> = {}): VaultNode => ({
  id: "t" + ++seq, revision: 1, parentId: null, scopeNodeId: null, ord: 1, kind: "brief", title, stage: "draft", mvp: "none",
  note: "", by: "agent", actor: "agent", at: "", deleted: false, chars: 10, status: "saved", inserted: false, cards: [],
  changedSinceInsert: false, ideas: 0, children: [], ...extra,
});

describe("vault tracks", () => {
  it("offers CX/UX/UI · Backend + DB · Nezařazené in order", () => {
    expect(TRACK_VIEWS.map((item) => item.label)).toEqual(["CX/UX/UI", "Backend + DB", "Nezařazené"]);
  });

  it("reads the effective track from the server and inherits it on an older server", () => {
    expect(viewOf({ track: null, effectiveTrack: "logic" })).toBe("logic");
    expect(viewOf({ track: "ux", effectiveTrack: null })).toBe("none");
    expect(viewOf({}, "ux")).toBe("ux");
    expect(viewOf({ track: "logic" }, "ux")).toBe("logic");
    expect(viewOf({})).toBe("none");
  });

  it("filters the tree by track and keeps the path to the root", () => {
    const flow = node("Tok objednávky", { effectiveTrack: "ux" });
    const rules = node("Výpočet ceny", { track: "logic", effectiveTrack: "logic", children: [node("Sleva", { effectiveTrack: "logic" })] });
    const root = node("Zadání", { track: "ux", effectiveTrack: "ux", children: [flow, rules] });
    const ux = filterByTrack([root], "ux");
    expect(flatten(ux).map((item) => item.node.title)).toEqual(["Zadání", "Tok objednávky"]);
    expect(ux[0].offTrack).toBe(false);
    const logic = filterByTrack([root], "logic");
    expect(flatten(logic).map((item) => [item.node.title, !!item.node.offTrack])).toEqual([
      ["Zadání", true], ["Výpočet ceny", false], ["Sleva", false]]);
    // Cesta ke kořeni se nepočítá do pokrytí.
    expect(coverageOf(logic).leaves).toBe(1);
    expect(filterByTrack([root], "none")).toEqual([]);
  });

  it("counts chapters per track and treats fragments before tracks as unassigned", () => {
    const old = node("Staré zadání", { children: [node("1"), node("2")] });
    const root = node("Nové", { effectiveTrack: "ux", children: [node("A", { effectiveTrack: "ux" }), node("B", { effectiveTrack: "logic" })] });
    expect(trackCounts([old, root])).toEqual({ ux: 1, logic: 1, none: 2 });
  });

  it("remembers the last choice, otherwise picks the first track with content", () => {
    expect(pickTrack("logic", { ux: 3, logic: 0, none: 0 })).toBe("logic");
    expect(pickTrack(null, { ux: 0, logic: 0, none: 4 })).toBe("none");
    expect(pickTrack(null, { ux: 0, logic: 0, none: 0 })).toBe("ux");
    expect(parseTrack(JSON.stringify({ track: "none" }))).toBe("none");
    expect(parseTrack(JSON.stringify({ track: "design" }))).toBeNull();
    expect(parseTrack("{rozbité")).toBeNull();
    expect(parseTrack(null)).toBeNull();
  });
  it("a fragment from an idea goes under the root of the chosen track, or into a new root with a track", () => {
    const ux = node("Zadání UX", { effectiveTrack: "ux", scopeNodeId: "s" });
    expect(ideaTarget(filterByTrack([ux], "ux"), "s", "ux", null)).toEqual({ parentId: ux.id });
    // V pohledu Backend + DB je kořen UX jen cesta, ne domov fragmentu.
    const path = filterByTrack([node("Zadání", { effectiveTrack: "ux", children: [node("Výpočet", { effectiveTrack: "logic" })] })], "logic");
    expect(ideaTarget(path, "s", "logic", null)).toEqual({ scopeNodeId: "s", track: "logic" });
    expect(ideaTarget([], "", "ux", null)).toEqual({ scopeNodeId: "", track: "ux" });
    expect(ideaTarget([], "", "none", null)).toBeNull();
    expect(ideaTarget([], "", "none", "logic")).toEqual({ scopeNodeId: "", track: "logic" });
  });
});
