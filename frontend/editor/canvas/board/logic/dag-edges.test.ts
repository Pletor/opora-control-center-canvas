import { describe, expect, it } from "vitest";
import { dagLook } from "./dag-edges";

describe("vazby next jako DAG", () => {
  const cards = new Set(["a", "b"]);
  it("z hotového předchůdce plná zelená, jinak přerušovaná", () => {
    expect(dagLook({ id: "e", source: "a", target: "b" }, cards, new Set(["a"]))?.style).toMatchObject({ stroke: "var(--ok)" });
    expect(dagLook({ id: "e", source: "a", target: "b" }, cards, new Set())?.style).toMatchObject({ strokeDasharray: "6 5" });
  });
  it("druh toku drží barvu a háček, stav závislosti jen čáru", () => {
    const waiting = dagLook({ id: "e", source: "a", target: "b", carries: "command" }, cards, new Set());
    expect(waiting?.style).toMatchObject({ stroke: "var(--edge-carries-command)", strokeWidth: 2, strokeDasharray: "6 5" });
    expect(waiting?.className).toBe("edge-port-next edge-dag--waiting edge--carries-command");
    const open = dagLook({ id: "e", source: "a", target: "b", carries: "data" }, cards, new Set(["a"]));
    expect(open?.style).toMatchObject({ stroke: "var(--edge-carries-data)", strokeWidth: 2.5 });
    expect(open?.className).toBe("edge-port-next edge-dag--open edge--carries-data");
  });
  it("jiné porty a vazby mimo karty nechává být", () => {
    expect(dagLook({ id: "e", source: "a", target: "b", port: "action" }, cards, new Set())).toBeNull();
    expect(dagLook({ id: "e", source: "a", target: "x" }, cards, new Set())).toBeNull();
  });
  it("semantic relations do not inherit next predecessor styling", () => {
    for (const relation of ["requires", "uses", "communicates_with", "evidences"] as const) {
      expect(dagLook({ id: "e", source: "a", target: "b", relation }, cards, new Set())).toBeNull();
      expect(dagLook({ id: "e", source: "a", target: "b", port: "next", relation }, cards, new Set())).toBeNull();
    }
  });
});
