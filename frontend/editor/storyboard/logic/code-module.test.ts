import { describe, expect, it } from "vitest";
import { buildModuleSource, checkExports, describeError, parseCodeDraft } from "./code-module";

describe("kontrakt kódu animace", () => {
  it("buildModuleSource zachová zdroj a přidá sourceURL", () => {
    const out = buildModuleSource("export const fields = [];");
    expect(out.startsWith("export const fields = [];")).toBe(true);
    expect(out).toContain("sourceURL=opora-animation.js");
  });
  it("checkExports hlásí chybějící paint, fields a layers", () => {
    expect(checkExports({ paint() {}, fields: [], layers: [] })).toBeNull();
    expect(checkExports({ fields: [], layers: [] })).toContain("paint");
    expect(checkExports({ paint() {}, layers: [] })).toContain("fields");
    expect(checkExports({ paint() {}, fields: [] })).toContain("layers");
  });
  it("describeError vrátí zprávu chyby i z řetězce", () => {
    expect(describeError(new SyntaxError("Unexpected token"))).toBe("Unexpected token");
    expect(describeError("boom")).toBe("boom");
    expect(describeError(null)).toBe("neznámá chyba");
  });
  const draft = { source: "export function paint() {}", title: "T", fields: "[]", layers: '[{"id":"a","label":"A"}]' };
  it("parseCodeDraft přijme platný koncept", () => {
    expect(parseCodeDraft(draft)).toEqual({ code: { source: draft.source, title: "T", fields: [], layers: [{ id: "a", label: "A" }] } });
  });
  it("parseCodeDraft hlásí špatný JSON, tvar a velikost", () => {
    expect(parseCodeDraft({ ...draft, fields: "[" })).toEqual({ error: "Pole fields nejsou platný JSON." });
    expect(parseCodeDraft({ ...draft, layers: "{}" })).toHaveProperty("error");
    expect(parseCodeDraft({ ...draft, fields: '[{"key":"x","label":"X","kind":"vector"}]' })).toHaveProperty("error");
    expect(parseCodeDraft({ ...draft, source: " " })).toHaveProperty("error");
    expect(parseCodeDraft({ ...draft, source: "x".repeat(64001) })).toHaveProperty("error");
  });
});
