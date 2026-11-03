import { describe, expect, it } from "vitest";
import { fieldRows, parseField, parseNewParam, prettyRef } from "./inspector-fields";

describe("inspector fields", () => {
  it("infers the field kind from the value", () => {
    expect(fieldRows({ subcommands: null, model: "haiku", per_hour: 6, on: true })).toEqual([
      { key: "model", kind: "text", raw: "haiku" }, { key: "on", kind: "boolean", raw: "true" },
      { key: "per_hour", kind: "number", raw: "6" }, { key: "subcommands", kind: "json", raw: "null" }]);
  });
  it("parses numbers with a decimal comma and rejects bad JSON", () => {
    expect(parseField("number", "1,5")).toEqual({ value: 1.5 });
    expect(parseField("number", "")).toEqual({ error: "Zadejte číslo." });
    expect(parseField("json", "[\"a\"]")).toEqual({ value: ["a"] });
    expect(parseField("json", "{")).toEqual({ error: "Neplatný JSON." });
    expect(parseField("boolean", "false")).toEqual({ value: false });
  });
  it("adds a new param as JSON or text", () => {
    expect(parseNewParam("limit", "20", {})).toEqual({ key: "limit", value: 20 });
    expect(parseNewParam("note", "ahoj", {})).toEqual({ key: "note", value: "ahoj" });
    expect(parseNewParam("bad key", "1", {})).toHaveProperty("error");
    expect(parseNewParam("limit", "1", { limit: 2 })).toEqual({ error: "Parametr už existuje." });
  });
  it("pretty prints stored refs", () => {
    expect(prettyRef('{"a":1}')).toBe('{\n  "a": 1\n}');
    expect(prettyRef("nečitelné")).toBe("nečitelné");
    expect(prettyRef(null)).toBe("");
  });
});
