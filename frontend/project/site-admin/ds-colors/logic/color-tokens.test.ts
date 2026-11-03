import { expect, it } from "vitest";
import type { ColorFamily } from "@/project/site-admin/logic/site-document";
import { colorGroups, contrastPair, removeToken, renameColor, resolveColor, tokenContrast } from "./color-tokens";

const family: ColorFamily = {
  themes: [{ id: "light", name: "Light" }, { id: "dark", name: "Dark" }],
  tokens: [
    { name: "surface", value: { light: "#ffffff", dark: "#111111" } },
    { name: "ink", value: { light: "#111111", dark: "#ffffff" } },
    { name: "ember", value: "#d6582a" },
    { name: "on-ember", value: "#ffffff" },
    { name: "link", value: { light: "{ember}", dark: "{ink}" } },
    { name: "loop-a", value: "{loop-b}" },
    { name: "loop-b", value: "{loop-a}" },
    { name: "lost", value: "{nowhere}" },
  ],
};

it("resolves aliases per theme and reports cycles and missing targets", () => {
  expect(resolveColor(family.tokens, "link", "light", "light")).toEqual({ value: "#d6582a" });
  expect(resolveColor(family.tokens, "link", "dark", "light")).toEqual({ value: "#ffffff" });
  expect(resolveColor(family.tokens, "ember", "dark", "light")).toEqual({ value: "#d6582a" });
  expect(resolveColor(family.tokens, "loop-a", "light", "light")).toEqual({ error: "alias v cyklu" });
  expect(resolveColor(family.tokens, "lost", "light", "light")).toEqual({ error: "alias na neexistující nowhere" });
});

it("groups tokens by the stem of their name and keeps on-x with its fill", () => {
  expect(colorGroups(family.tokens).map((group) => [group.stem, group.items.map((item) => item.index)]))
    .toEqual([["surface", [0]], ["ink", [1]], ["ember", [2, 3]], ["link", [4]], ["loop", [5, 6]], ["lost", [7]]]);
});

it("pairs text with its fill, ink with surface and the rest with surface", () => {
  const names = family.tokens.map((token) => token.name);
  expect(contrastPair("on-ember", names)).toBe("ember");
  expect(contrastPair("ember", names)).toBe("on-ember");
  expect(contrastPair("surface", names)).toBe("ink");
  expect(contrastPair("ink", names)).toBe("surface");
  expect(contrastPair("link", names)).toBe("surface");
  expect(contrastPair("surface", ["surface"])).toBeNull();
});

it("rates contrast against the pair in each theme", () => {
  expect(tokenContrast(family, "ink", "light")).toMatchObject({ pair: "surface", level: "AAA" });
  expect(tokenContrast(family, "link", "dark")).toMatchObject({ pair: "surface", level: "AAA" });
  expect(tokenContrast(family, "ember", "light")).toMatchObject({ pair: "on-ember", level: "fail" });
  expect(tokenContrast(family, "lost", "light")).toBeNull();
});

it("renames a token together with the aliases pointing at it", () => {
  const renamed = renameColor(family.tokens, 2, "brand");
  expect(renamed[2].name).toBe("brand");
  expect(renamed[4].value).toEqual({ light: "{brand}", dark: "{ink}" });
  expect(removeToken(family.tokens, 0)[0].name).toBe("ink");
});
