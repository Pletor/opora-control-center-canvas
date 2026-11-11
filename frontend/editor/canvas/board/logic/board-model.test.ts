import { describe, expect, it } from "vitest";
import { edgeAppearance, edgeFromConnection, parseBlockHandle, portOf, sameEdge } from "./board-model";
import { blockHandleId, isBlockEdge } from "@/shared/types/logic/types";

describe("board-model", () => {
  it("význam vazby dá barvu a popisek a má přednost před druhem toku", () => {
    const look = edgeAppearance({ id: "e", source: "a", target: "b", relation: "requires", carries: "data" });
    expect(look).toMatchObject({ label: "vyžaduje", style: { stroke: "var(--gold)" }, sourceHandle: "next" });
    expect(look.className).toContain("edge--relation-requires");
    expect(edgeAppearance({ id: "e", source: "a", target: "b", relation: "evidences" }).label).toBe("dokládá");
    expect(edgeAppearance({ id: "e", source: "a", target: "b" }).label).toBeUndefined();
  });

  it("úchyt portu bloku se rozpadne na blok a port, ostatní úchyty ne", () => {
    expect(parseBlockHandle(blockHandleId("b1", "p2"))).toEqual({ blockId: "b1", portId: "p2" });
    expect(parseBlockHandle("next")).toBeNull();
    expect(parseBlockHandle("block:b1")).toBeNull();
    expect(parseBlockHandle(null)).toBeNull();
    expect(portOf("action")).toBe("action");
    expect(portOf("block:b1:p2")).toBe("next");
    expect(portOf(null)).toBe("next");
  });

  it("tah z tlačítka bloku dá vazbu port:block s identitou bloku i portu", () => {
    const edge = edgeFromConnection({ source: "a", target: "b", sourceHandle: blockHandleId("b1", "p2") }, "e1");
    expect(edge).toEqual({ id: "e1", source: "a", target: "b", port: "block", sourceBlockId: "b1", sourcePortId: "p2" });
    expect(isBlockEdge(edge!)).toBe(true);
  });

  it("tah z hrany karty dá klasický port a neznámý úchyt je next", () => {
    expect(edgeFromConnection({ source: "a", target: "b", sourceHandle: "rule" }, "e2"))
      .toEqual({ id: "e2", source: "a", target: "b", port: "rule" });
    expect(edgeFromConnection({ source: "a", target: "b", sourceHandle: null }, "e3"))
      .toEqual({ id: "e3", source: "a", target: "b", port: "next" });
  });

  it("neúplný tah a smyčka na sebe sama vazbu nedají; id je pokaždé jiné", () => {
    expect(edgeFromConnection({ source: "a", target: null })).toBeNull();
    expect(edgeFromConnection({ source: null, target: "b" })).toBeNull();
    expect(edgeFromConnection({ source: "a", target: "a" })).toBeNull();
    const first = edgeFromConnection({ source: "a", target: "b" })!;
    const second = edgeFromConnection({ source: "a", target: "b" })!;
    expect(first.id).not.toBe(second.id);
  });

  it("vzhled vazby: úchyt, třída a tah podle portu; vazba z bloku má akcent a drobnou čárku", () => {
    const pathOptions = { borderRadius: 12, offset: 24 };
    expect(edgeAppearance({ id: "e", source: "a", target: "b", port: "block", sourceBlockId: "b1", sourcePortId: "p1" })).toEqual({
      sourceHandle: "block:b1:p1", className: "edge-port-block", style: { stroke: "var(--accent)", strokeDasharray: "2 3" },
      type: "smoothstep", pathOptions,
    });
    expect(edgeAppearance({ id: "e", source: "a", target: "b", port: "rule" })).toEqual({
      sourceHandle: "rule", className: "edge-port-rule", style: { stroke: "#c4524a", strokeDasharray: "4 3" },
      type: "smoothstep", pathOptions,
    });
    expect(edgeAppearance({ id: "e", source: "a", target: "b" })).toEqual({
      sourceHandle: "next", className: "edge-port-next", style: undefined,
      type: "smoothstep", pathOptions,
    });
  });

  it("tok mezi oblastmi (port flow) je čárkovaný barvou oblasti, vlastní třída bez 'port'", () => {
    const pathOptions = { borderRadius: 12, offset: 24 };
    expect(edgeAppearance({ id: "e", source: "a", target: "b", port: "flow" })).toEqual({
      sourceHandle: "flow", className: "edge-flow", style: { stroke: "var(--area-line)", strokeDasharray: "6 4" },
      type: "smoothstep", pathOptions,
    });
  });

  it("vazba next s druhem toku nese třídu-háček, tooltip a jemný tah; jiný port carries ignoruje", () => {
    const pathOptions = { borderRadius: 12, offset: 24 };
    expect(edgeAppearance({ id: "e", source: "a", target: "b", carries: "data" })).toEqual({
      sourceHandle: "next", className: "edge-port-next edge--carries-data", style: { stroke: "var(--edge-carries-data)" },
      ariaLabel: "Po vazbě teče: Data", type: "smoothstep", pathOptions,
    });
    expect(edgeAppearance({ id: "e", source: "a", target: "b", port: "next", carries: "command" }).style)
      .toEqual({ stroke: "var(--edge-carries-command)", strokeWidth: 1.5 });
    expect(edgeAppearance({ id: "e", source: "a", target: "b", carries: "event" }).style)
      .toEqual({ stroke: "var(--edge-carries-event)", strokeDasharray: "6 4" });
    expect(edgeAppearance({ id: "e", source: "a", target: "b", port: "rule", carries: "data" }).className).toBe("edge-port-rule");
  });

  it("tah z úchytu flow dá vazbu port:flow", () => {
    expect(edgeFromConnection({ source: "a1", target: "a2", sourceHandle: "flow" }, "e5"))
      .toEqual({ id: "e5", source: "a1", target: "a2", port: "flow" });
  });

  it("duplicita se pozná podle portu a u bloku i podle tlačítka, ne podle id", () => {
    const a = edgeFromConnection({ source: "a", target: "b", sourceHandle: blockHandleId("b1", "p1") }, "e1")!;
    const same = edgeFromConnection({ source: "a", target: "b", sourceHandle: blockHandleId("b1", "p1") }, "e2")!;
    const other = edgeFromConnection({ source: "a", target: "b", sourceHandle: blockHandleId("b1", "p2") }, "e3")!;
    expect(sameEdge(a, same)).toBe(true);
    expect(sameEdge(a, other)).toBe(false);
    expect(sameEdge(a, { id: "e4", source: "a", target: "b", port: "next" })).toBe(false);
  });
});
