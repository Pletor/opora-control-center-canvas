import { expect, it } from "vitest";
import type { ColorFamily } from "@/project/site-admin/logic/site-document";
import { addTheme, MAX_THEMES, moveTheme, removeTheme, renameTheme, themeId } from "./color-themes";

const family: ColorFamily = {
  themes: [{ id: "light", name: "Light" }, { id: "dark", name: "Dark" }],
  tokens: [{ name: "ink", value: { light: "#111111" } }, { name: "surface", value: { light: "#ffffff", dark: "#000000" } }, { name: "ember", value: "#d6582a" }],
};

it("adds themes with a format id, renames them and stops at eight", () => {
  expect(themeId("Vysoký kontrast", family.themes)).toBe("vysoky-kontrast");
  expect(themeId("Dark", family.themes)).toBe("dark-2");
  const added = addTheme(family, "Vysoký kontrast");
  expect(added.themes.at(-1)).toEqual({ id: "vysoky-kontrast", name: "Vysoký kontrast" });
  expect(renameTheme(added, "dark", "Noc").themes[1]).toEqual({ id: "dark", name: "Noc" });
  let full = family;
  for (let index = 0; index < 10; index++) full = addTheme(full, "t" + index);
  expect(full.themes).toHaveLength(MAX_THEMES);
  expect(addTheme(family, "  ")).toBe(family);
});

it("moves a theme to the front without changing any color", () => {
  const moved = moveTheme(family, "dark", -1);
  expect(moved.themes.map((theme) => theme.id)).toEqual(["dark", "light"]);
  expect(moved.tokens[0].value).toEqual({ light: "#111111", dark: "#111111" });
  expect(moved.tokens[1].value).toEqual({ light: "#ffffff", dark: "#000000" });
  expect(moved.tokens[2].value).toBe("#d6582a");
  expect(moveTheme(family, "light", -1)).toBe(family);
});

it("removes a theme with its values and keeps the last one", () => {
  const removed = removeTheme(family, "dark");
  expect(removed.themes).toEqual([{ id: "light", name: "Light" }]);
  expect(removed.tokens[1].value).toBe("#ffffff");
  const first = removeTheme(family, "light");
  expect(first.tokens[0].value).toBe("#111111");
  expect(first.tokens[1].value).toBe("#000000");
  expect(removeTheme(removed, "light")).toBe(removed);
});
