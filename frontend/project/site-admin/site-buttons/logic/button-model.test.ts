import { expect, it } from "vitest";
import { addVariant, effective, PRESET_VARIANTS, readButtons, readCustomCss, removeVariant, slugProblem, variantNotes, withNestedKey, withSize, withStateKey } from "./button-model";

it("reads an empty document with default sizes and no variants", () => {
  const buttons = readButtons({});
  expect(buttons.variants).toEqual({});
  expect(buttons.sizes.md.minHeight).toBe("44px");
  expect(readCustomCss({ customCss: { button: { primary: ":scope { color: red; }" } } })).toEqual({ primary: ":scope { color: red; }" });
});

it("offers the five presets and adds them as independent copies", () => {
  expect(Object.keys(PRESET_VARIANTS)).toEqual(["primary", "secondary", "outline", "ghost", "link"]);
  const buttons = addVariant(readButtons({}), "primary");
  buttons.variants.primary.states.default!.color = "#000000";
  expect(PRESET_VARIANTS.primary.states.default!.color).toBe("#ffffff");
  expect(addVariant(buttons, "cta").variants.cta.label).toBe("cta");
  expect(Object.keys(removeVariant(buttons, "primary").variants)).toEqual([]);
});

it("checks variant names like the server", () => {
  const buttons = addVariant(readButtons({}), "primary");
  expect(slugProblem("cta-2", buttons)).toBe("");
  expect(slugProblem("Cta", buttons)).not.toBe("");
  expect(slugProblem("md", buttons)).not.toBe("");
  expect(slugProblem("primary", buttons)).toBe("Varianta už existuje.");
});

it("edits one state field and drops empty values and empty nested objects", () => {
  let variant = structuredClone(PRESET_VARIANTS.outline);
  variant = withStateKey(variant, "hover", "color", "#ffffff");
  expect(variant.states.hover).toEqual({ background: "#e6efe8", color: "#ffffff" });
  variant = withStateKey(variant, "hover", "color", "");
  expect(variant.states.hover).toEqual({ background: "#e6efe8" });
  variant = withNestedKey(variant, "hover", "border", "color", "#000000");
  expect(variant.states.hover!.border).toEqual({ color: "#000000" });
  variant = withNestedKey(variant, "hover", "border", "color", "");
  expect(variant.states.hover!.border).toBeUndefined();
});

it("merges a state over default field by field", () => {
  const state = effective(PRESET_VARIANTS.outline, "disabled");
  expect(state.background).toBe("transparent");
  expect(state.border).toEqual({ width: "2px", style: "solid", color: "#9ca3af" });
});

it("changes one size field and keeps the others", () => {
  const buttons = withSize(readButtons({}), "lg", "minHeight", "56px");
  expect(buttons.sizes.lg).toEqual({ paddingX: "2rem", paddingY: "0.875rem", minHeight: "56px", fontSize: "1.125rem" });
  expect(buttons.sizes.md.minHeight).toBe("44px");
});

it("picks the server notes that belong to one variant", () => {
  const notes = ["Tlačítko primary (hover): kontrast textu 2.10:1 je pod 4,5:1.", "Tlačítko primary: focus ring je vypnutý bez náhrady (stín nebo outline).",
    "Tlačítko ghost (default): kontrast", "Tlačítka sm: minHeight 20px je pod 24 px (WCAG 2.5.8).", "settings.customCss.button.primary, řádek 2: focus ring je vypnutý"];
  expect(variantNotes(notes, "primary")).toEqual([notes[0], notes[1], notes[3], notes[4]]);
});
