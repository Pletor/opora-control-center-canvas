import { expect, it } from "vitest";
import { cssValue, fieldValue, pickerHex, safeCss } from "./field-values";

it("keeps values that cannot break out of a preview declaration", () => {
  expect(safeCss("#1c9749")).toBe("#1c9749");
  expect(safeCss("1.5rem")).toBe("1.5rem");
  expect(safeCss("red; } body { display: none")).toBeNull();
  expect(safeCss("</style>")).toBeNull();
  expect(safeCss("")).toBeNull();
  expect(safeCss(null)).toBeNull();
});

it("turns an alias into a custom property like the server does", () => {
  expect(cssValue("{brand}")).toBe("var(--brand)");
  expect(cssValue("{space.2}")).toBe("var(--space\\.2)");
  expect(cssValue("transparent")).toBe("transparent");
});

it("offers the color picker only for literal colors", () => {
  expect(pickerHex("#1C9749")).toBe("#1c9749");
  expect(pickerHex("rgb(255, 255, 255)")).toBe("#ffffff");
  expect(pickerHex("{brand}")).toBeNull();
  expect(pickerHex("")).toBeNull();
});

it("treats an empty field as unset", () => {
  expect(fieldValue("  ")).toBeNull();
  expect(fieldValue(" 2px ")).toBe("2px");
});
