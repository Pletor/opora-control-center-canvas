import { describe, expect, it } from "vitest";
import { FIXTURE_TYPES, LIBRARY_TYPES, PROCESS_TYPES } from "../../logic/flow-fixtures";
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
  it("sorts the data-flow catalog into n8n categories with AI sub-categories by sub-port", () => {
    expect(paletteGroups(LIBRARY_TYPES).map((g) => [g.label, g.items.map((i) => i.type)])).toEqual([
      ["Spouštěče", ["trigger.chat"]], ["AI · Agent a řetězce", ["ai.agent"]], ["AI · Modely", ["ai.model"]], ["AI · Nástroje", ["ai.vectorStore"]],
      ["AI · Načítače", ["ai.documentLoader"]], ["Transformace dat", ["transform.set"]], ["Tok", ["flow.if"]]]);
  });
  it("offers a type for a port through its variant (vector store as an agent tool)", () => {
    const items = paletteGroups(LIBRARY_TYPES, "", { kind: "tool", direction: "in" }).flatMap((g) => g.items);
    expect(items.map((i) => i.type)).toEqual(["ai.vectorStore"]);
    expect(items[0].summary).toMatch(/→ Nástroj$/);
  });
  it("groups process types by layer (FE, BE, DB, Infra, AI, triggers, AI, flow) and carries use and avoid", () => {
    const groups = paletteGroups(PROCESS_TYPES);
    expect(groups.map((g) => g.id)).toEqual(["layer-fe", "layer-be", "layer-db", "layer-infra", "trigger", "ai", "flow"]);
    expect(groups[0].items.map((i) => i.type)).toEqual(["fe.form", "fe.click", "fe.notify"]);
    expect(groups[1].items[2]).toMatchObject({ type: "be.function", use: "je třeba spočítat hodnotu", avoid: "stačí přesun dat" });
  });
});
