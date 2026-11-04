import { describe, expect, it } from "vitest";
import type { NodeTypeSpec } from "../../logic/flow-types";
import { INTENTS, intentOptions } from "./intents";

const spec = (type: string, layer: NodeTypeSpec["layer"], intents: string[], use = `use ${type}`): NodeTypeSpec => ({ type, version: 1, trigger: false, ports: [], layer, intents, use });
const types = [spec("db.write", "db", ["store"]), spec("transform.set", "neutral", ["compute"]), spec("be.function", "be", ["compute", "validate"]),
  spec("fe.form", "fe", ["input"]), spec("infra.storage", "infra", ["store"]), { type: "x.plain", version: 1, trigger: false, ports: [] }];

describe("intent wizard", () => {
  it("offers the types with the intent tag ordered FE, BE, DB, Infra, others", () => {
    expect(intentOptions(types, "store").map((o) => o.type)).toEqual(["db.write", "infra.storage"]);
    expect(intentOptions(types, "compute").map((o) => o.type)).toEqual(["be.function", "transform.set"]);
    expect(intentOptions(types, "compute")[0].use).toBe("use be.function");
  });
  it("returns nothing for an intent no type carries and knows ten intents", () => {
    expect(intentOptions(types, "repeat")).toEqual([]);
    expect(INTENTS).toHaveLength(10);
  });
});
