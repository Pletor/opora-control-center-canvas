import { describe, expect, it } from "vitest";
import { dagLook } from "./dag-edges";

describe("vazby next jako DAG", () => {
  const cards = new Set(["a", "b"]);
  it("z hotového předchůdce plná zelená, jinak přerušovaná", () => {
    expect(dagLook({ id: "e", source: "a", target: "b" }, cards, new Set(["a"]))?.style).toMatchObject({ stroke: "var(--ok)" });
    expect(dagLook({ id: "e", source: "a", target: "b" }, cards, new Set())?.style).toMatchObject({ strokeDasharray: "6 5" });
  });
  it("jiné porty a vazby mimo karty nechává být", () => {
    expect(dagLook({ id: "e", source: "a", target: "b", port: "action" }, cards, new Set())).toBeNull();
    expect(dagLook({ id: "e", source: "a", target: "x" }, cards, new Set())).toBeNull();
  });
});
