import { describe, expect, it } from "vitest";
import { parseHeartModel } from "./heart-model";

describe("parseHeartModel", () => {
  it("přečte model, poradce a seznam", () => {
    expect(parseHeartModel({ model: "haiku", advisor: "opus", models: [{ id: "opus", label: "Opus" }, { id: "x" }, 3] }))
      .toEqual({ model: "haiku", advisor: "opus", models: [{ id: "opus", label: "Opus" }, { id: "x", label: "x" }], effort: null, efforts: [] });
  });
  it("přečte effort a úrovně", () => {
    expect(parseHeartModel({ model: "haiku", advisor: "opus", models: [], effort: "high", efforts: ["low", "high", 1] }))
      .toMatchObject({ effort: "high", efforts: ["low", "high"] });
  });
  it("vadná odpověď je chyba", () => {
    expect(() => parseHeartModel({ error: "x" })).toThrow();
  });
});
