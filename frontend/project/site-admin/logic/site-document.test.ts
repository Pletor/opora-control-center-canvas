import { expect, it } from "vitest";
import { designSummary, themedValue, withThemeValue, type Design } from "./site-document";

const themes = [{ id: "light", name: "Light" }, { id: "dark", name: "Dark" }];

it("reads a themed value and inherits a missing theme from the first one", () => {
  expect(themedValue("#fff", "dark", "light")).toBe("#fff");
  expect(themedValue({ light: "#fff", dark: "#000" }, "dark", "light")).toBe("#000");
  expect(themedValue({ light: "#fff" }, "dark", "light")).toBe("#fff");
});

it("writes one theme and folds the map back to a string when only the first theme is left", () => {
  expect(withThemeValue("#fff", "dark", "#000", themes)).toEqual({ light: "#fff", dark: "#000" });
  expect(withThemeValue({ light: "#fff", dark: "#000" }, "dark", "", themes)).toBe("#fff");
  expect(withThemeValue({ light: "#fff", dark: "#000" }, "light", "#eee", themes)).toEqual({ light: "#eee", dark: "#000" });
  expect(withThemeValue({ light: "#fff", gone: "#111" }, "light", "#eee", themes)).toBe("#eee");
});

const design: Design = {
  readme: "", sections: [], components: [{ name: "Button", readme: "", preview: "", height: 120 }], cover: null,
  assetGroups: [{ name: "Logos", readme: "", files: ["a.svg", "b.svg"].map((name) => ({ name, blob: "assets/Logos/" + name, size: 1, type: "image/svg+xml" })) }],
  tokens: {
    color: { themes, tokens: [{ name: "ink", value: "#000" }, { name: "link", value: "{ink}" }] },
    type: { fonts: [], families: { sans: "Inter, sans-serif" }, groups: [{ name: "Text", styles: [{ name: "body", fontSize: "15px" }] }] },
    spacing: { tokens: [{ name: "space-1", value: "4px" }] },
    size: { tokens: [{ name: "control", value: "40px" }] },
  },
};

it("counts what the system holds", () => {
  expect(designSummary(design)).toMatchObject({ themes: 2, colors: 2, styles: 1, families: 1, spacing: 1, radius: 0, components: 1, assets: 2 });
});
