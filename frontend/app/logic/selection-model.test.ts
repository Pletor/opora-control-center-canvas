import { describe, expect, it } from "vitest";
import { clearSelection, emptySelection, panelsFor, selectBlock, selectEdge, selectNode } from "./selection-model";

describe("selection-model", () => {
  it("selectNode vybere jen uzel", () => {
    expect(selectNode("n1")).toEqual({ node: "n1", block: null, edge: null });
  });

  it("selectBlock nese uzel i blok, aby karta zůstala otevřená", () => {
    expect(selectBlock("n1", "b1")).toEqual({ node: "n1", block: "b1", edge: null });
  });

  it("selectEdge vybere jen vazbu", () => {
    expect(selectEdge("e1")).toEqual({ node: null, block: null, edge: "e1" });
  });

  it("clearSelection i emptySelection dají prázdný výběr", () => {
    expect(clearSelection()).toEqual({ node: null, block: null, edge: null });
    expect(emptySelection()).toEqual({ node: null, block: null, edge: null });
  });

  describe("panelsFor ve struktuře", () => {
    it("vybraný blok otevře knihovnu bloku bez inspektoru", () => {
      expect(panelsFor(selectBlock("n1", "b1"), "structure", false)).toEqual({ drawer: "block", inspector: null });
    });
    it("vybraný uzel otevře pouze pravý inspektor a žádný levý panel", () => {
      expect(panelsFor(selectNode("n1"), "structure", false)).toEqual({ drawer: null, inspector: "node" });
    });
    it("vybraná vazba otevře jen inspektor vazby", () => {
      expect(panelsFor(selectEdge("e1"), "structure", false)).toEqual({ drawer: null, inspector: "edge" });
    });
    it("bez výběru nejsou panely žádné", () => {
      expect(panelsFor(emptySelection(), "structure", false)).toEqual({ drawer: null, inspector: null });
    });
    it("vybraný komentář otevře jen svůj inspektor, bez knihovny", () => {
      expect(panelsFor(selectNode("c1"), "structure", false, "comment")).toEqual({ drawer: null, inspector: "comment" });
    });
    it("vybraná oblast otevře jen svůj inspektor, bez knihovny", () => {
      expect(panelsFor(selectNode("a1"), "structure", false, "area")).toEqual({ drawer: null, inspector: "area" });
    });
    it("explicitní druh uzlu rovněž neotevře levý panel", () => {
      expect(panelsFor(selectNode("n1"), "structure", false, "node")).toEqual({ drawer: null, inspector: "node" });
    });
  });

  describe("panelsFor v textu", () => {
    it("s otevřenou vrstvou ukáže její deník", () => {
      expect(panelsFor(emptySelection(), "text", true)).toEqual({ drawer: null, inspector: "layer" });
    });
    it("bez vrstvy ukáže obecný kontext", () => {
      expect(panelsFor(emptySelection(), "text", false)).toEqual({ drawer: null, inspector: "scope" });
    });
    it("výběr uzlu v textu na panely nemá vliv", () => {
      expect(panelsFor(selectNode("n1"), "text", true)).toEqual({ drawer: null, inspector: "layer" });
    });
  });

  describe("panelsFor v mapě a bězích", () => {
    it("mapa nemá žádné panely, i s výběrem", () => {
      expect(panelsFor(selectNode("n1"), "map", true)).toEqual({ drawer: null, inspector: null });
    });
    it("běhy agentů nemají žádné panely", () => {
      expect(panelsFor(selectEdge("e1"), "agents", true)).toEqual({ drawer: null, inspector: null });
    });
  });
});
