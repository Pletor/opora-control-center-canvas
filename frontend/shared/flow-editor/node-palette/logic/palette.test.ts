import { describe, expect, it } from "vitest";
import { FIXTURE_TYPES } from "../../logic/flow-fixtures";
import { paletteGroups } from "./palette";

describe("node palette", () => {
  it("groups the registry into triggers, agent, flow, approval and sub-nodes", () => {
    expect(paletteGroups(FIXTURE_TYPES).map((g) => [g.id, g.items.length])).toEqual([
      ["trigger", 2], ["agent", 1], ["flow", 2], ["approval", 1], ["sub-model", 1], ["sub-tool", 1]]);
    expect(paletteGroups(FIXTURE_TYPES)[1].items[0]).toEqual({ type: "agent.claude", name: "claude", family: "agent", glyph: "✳",
      summary: "main, Model, Nástroj, Paměť → main" });
  });
  it("searches in names and port kinds", () => {
    expect(paletteGroups(FIXTURE_TYPES, "jev").flatMap((g) => g.items.map((i) => i.type))).toEqual(["decision.jev"]);
    expect(paletteGroups(FIXTURE_TYPES, "nástroj").flatMap((g) => g.items.map((i) => i.type))).toEqual(["agent.claude", "tool.opora_heart"]);
  });
  it("prefilters on the port the plus was clicked on", () => {
    expect(paletteGroups(FIXTURE_TYPES, "", { kind: "model", direction: "in" }).flatMap((g) => g.items.map((i) => i.type))).toEqual(["model.claude"]);
    expect(paletteGroups(FIXTURE_TYPES, "", { kind: "main", direction: "out" }).map((g) => g.id)).toEqual(["agent", "flow", "approval"]);
  });
});
