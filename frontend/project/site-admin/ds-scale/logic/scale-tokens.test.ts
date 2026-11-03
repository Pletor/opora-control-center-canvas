import { expect, it } from "vitest";
import { addScaleToken, removeScaleToken, scaleFamily, scaleSwatch, SCALE_LIMIT, updateScaleToken, withNote } from "./scale-tokens";

it("adds tokens continuing from the last value and stops at the family limit", () => {
  const family = addScaleToken(addScaleToken(scaleFamily(undefined), "spacing", "space-1"), "spacing", "space-2");
  expect(family.tokens).toEqual([{ name: "space-1", value: "4px" }, { name: "space-2", value: "4px" }]);
  let full = scaleFamily(undefined);
  for (let index = 0; index < SCALE_LIMIT + 3; index++) full = addScaleToken(full, "radius", "r" + index);
  expect(full.tokens).toHaveLength(SCALE_LIMIT);
  expect(addScaleToken(scaleFamily(undefined), "shadow", "shadow-sm").tokens[0].value).toMatch(/rgba/);
});

it("edits the note, updates and removes tokens", () => {
  const family = { note: "4px base", tokens: [{ name: "space-1", value: "4px" }] };
  expect(withNote(family, "")).toEqual({ tokens: family.tokens });
  expect(withNote(family, "8px").note).toBe("8px");
  expect(updateScaleToken(family, 0, { name: "space-1", value: "6px" }).tokens[0].value).toBe("6px");
  expect(removeScaleToken(family, 0).tokens).toEqual([]);
});

it("draws a swatch for spacing, radius and a themed shadow", () => {
  expect(scaleSwatch("spacing", { name: "s", value: "16" }, "light", "light")).toEqual({ width: "min(16px, 100%)" });
  expect(scaleSwatch("radius", { name: "r", value: "9999px" }, "light", "light")).toEqual({ borderRadius: "9999px" });
  const shadow = { name: "shadow-sm", value: { light: "0 1px 2px #0002", dark: "none" } };
  expect(scaleSwatch("shadow", shadow, "dark", "light")).toEqual({ boxShadow: "none" });
  expect(scaleSwatch("shadow", { name: "x", value: { light: "0 1px 2px #0002" } }, "dark", "light")).toEqual({ boxShadow: "0 1px 2px #0002" });
});
