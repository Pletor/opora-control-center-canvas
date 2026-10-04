import { describe, expect, it } from "vitest";
import { pageLayoutClass } from "./page-layout";

describe("pageLayoutClass", () => {
  it("jen mapa", () => expect(pageLayoutClass({ structure: false, detail: false, focus: "map" })).toBe("page-editor"));
  it("všechny čtyři sloupce s předností struktury", () => {
    expect(pageLayoutClass({ structure: true, detail: true, focus: "structure" }))
      .toBe("page-editor page-editor--structure page-editor--detail page-editor--focus-structure");
  });
  it("přednost se bez otevřené struktury neuvádí", () => {
    expect(pageLayoutClass({ structure: false, detail: true, focus: "structure" })).toBe("page-editor page-editor--detail");
  });
});
