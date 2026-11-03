import { expect, it } from "vitest";
import { field, imageAssets, numberLeaf, readAppearance, withField } from "./appearance";

it("reads the whole view and fills what the server did not send with null", () => {
  const appearance = readAppearance({ appearance: { colors: { link: "#1c6ed1" }, headings: { h1: { size: "3rem" } } } });
  expect(appearance.colors.link).toBe("#1c6ed1");
  expect(appearance.headings.h1).toEqual({ size: "3rem", weight: null, lineHeight: null, letterSpacing: null });
  expect(appearance.background.image.asset).toBeNull();
  expect(readAppearance({}).layout).toEqual({ contentSize: null, wideSize: null, gutter: null });
});

it("changes one leaf without touching the rest, empty text becomes null", () => {
  const before = readAppearance({ appearance: { colors: { link: "#111111", linkHover: "#222222" } } });
  const after = withField(before, "colors.link", " #333333 ");
  expect(field(after, "colors.link")).toBe("#333333");
  expect(field(after, "colors.linkHover")).toBe("#222222");
  expect(before.colors.link).toBe("#111111");
  expect(field(withField(after, "colors.link", ""), "colors.link")).toBeNull();
  expect(field(withField(after, "background.pattern.scale", 2), "background.pattern.scale")).toBe(2);
});

it("reads numbers from fields and offers only image assets for the background", () => {
  expect(numberLeaf("0,5")).toBe(0.5);
  expect(numberLeaf("")).toBeNull();
  expect(numberLeaf("x")).toBeNull();
  expect(imageAssets([{ name: "web", files: [{ blob: "assets/web/vlny.png", type: "image/png" }, { blob: "assets/web/manual.pdf", type: "application/pdf" }] }]))
    .toEqual(["assets/web/vlny.png"]);
});
