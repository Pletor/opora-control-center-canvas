import { describe, expect, it } from "vitest";
import { LIBRARY } from "@/shared/flow-editor/logic/flow-fixtures";
import { enumValues, portQueries, variantParams } from "./node-ports";

describe("ports by params", () => {
  it("asks only for nodes of dynamic types or with an error output, keyed by type and params", () => {
    const queries = portQueries({ nodes: [
      { id: "store", type: "ai.vectorStore", params: { mode: "retrieveAsTool", topK: 4 } },
      { id: "set", type: "transform.set", params: {} },
      { id: "set-2", type: "transform.set", onError: "errorOutput" },
      { id: "ghost", type: "nope" },
    ], edges: [] }, LIBRARY);
    expect([...queries.keys()]).toEqual(["store", "set-2"]);
    expect(queries.get("store")).toEqual({ key: '["ai.vectorStore",{"mode":"retrieveAsTool","topK":4},null]', type: "ai.vectorStore", params: { mode: "retrieveAsTool", topK: 4 } });
    expect(queries.get("set-2")).toMatchObject({ onError: "errorOutput", params: {} });
  });
  it("reads enumerated values from the registry description", () => {
    expect(enumValues("insert | load | retrieve | retrieveAsTool")).toEqual(["insert", "load", "retrieve", "retrieveAsTool"]);
    expect(enumValues("true | false")).toEqual([true, false]);
    expect(enumValues("výraz vstupu")).toEqual([]);
    expect(enumValues("[kategorie] (classify)")).toEqual([]);
    expect(variantParams(LIBRARY.get("ai.vectorStore")!)).toEqual([{ mode: "insert" }, { mode: "retrieveAsTool" }]);
    expect(variantParams(LIBRARY.get("transform.set")!)).toEqual([]);
  });
});
