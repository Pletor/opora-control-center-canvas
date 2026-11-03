import { expect, it } from "vitest";
import type { DesignTokens } from "./site-document";
import { freeName, nameProblem, tokenNames } from "./token-names";

const tokens: DesignTokens = {
  color: { themes: [{ id: "light", name: "Light" }], tokens: [{ name: "ink", value: "#000" }, { name: "link", value: "{ink}" }] },
  type: { fonts: [], families: {}, groups: [{ name: "Text", styles: [{ name: "body", fontSize: "15px" }] }] },
  spacing: { tokens: [{ name: "space-1", value: "4px" }] },
  size: { tokens: [{ name: "control", value: "40px" }] },
};

it("checks token names in one shared namespace and finds a free one", () => {
  const taken = tokenNames(tokens);
  expect(taken).toEqual(["ink", "link", "space-1", "control"]);
  expect(nameProblem("ink", taken)).toMatch(/už v systému/);
  expect(nameProblem("ink", taken, "ink")).toBe("");
  expect(nameProblem("-bad", taken)).toMatch(/Jméno/);
  expect(freeName("space-1", taken)).toBe("space-1-2");
  expect(freeName("new", taken)).toBe("new");
});
