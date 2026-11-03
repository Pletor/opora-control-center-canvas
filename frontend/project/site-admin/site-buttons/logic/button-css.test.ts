import { expect, it } from "vitest";
import { buttonsCss, stateLines } from "./button-css";
import { addVariant, readButtons } from "./button-model";

it("writes one state as component tokens like the server", () => {
  expect(stateLines({
    background: { gradient: { angle: 90, stops: [{ color: "#000000", position: 0 }, { color: "#ffffff", position: 1 }] } },
    color: "{on-brand}", radius: "pill", width: "full", border: { width: "2px", color: "#111111" },
    font: { family: "heading", weight: 700, transform: "uppercase" }, transition: { properties: ["transform"], duration: "200ms" },
  })).toEqual([
    "--btn-bg: linear-gradient(90deg, #000000 0%, #ffffff 100%);", "--btn-color: var(--on-brand);", "--btn-radius: 999px;",
    "--btn-width: 100%;", "--btn-border-width: 2px;", "--btn-border-color: #111111;", "--btn-font-family: var(--font-heading);",
    "--btn-font-weight: 700;", "--btn-text-transform: uppercase;", "--btn-transition: transform 200ms ease;",
  ]);
  expect(stateLines({ radius: "12px", outline: { offset: "3px" } })).toEqual(["--btn-radius: 12px;", "--btn-ring-offset: 3px;"]);
});

it("scopes sizes, variants and states under the preview and adds forced state classes", () => {
  const css = buttonsCss(addVariant(readButtons({}), "primary"));
  expect(css).toContain(".ds-web .ds-btn--lg {\n  --btn-px: 2rem;");
  expect(css).toContain(".ds-web .ds-btn--primary {\n  --btn-bg: #157a3a;");
  expect(css).toContain('.ds-web .ds-btn--primary:hover:not(:disabled):not([aria-disabled="true"]), .ds-web .ds-btn--primary.ds-btn--is-hover {');
  expect(css).toContain('.ds-web .ds-btn--primary:disabled, .ds-web .ds-btn--primary[aria-disabled="true"], .ds-web .ds-btn--primary.ds-btn--is-disabled {');
  expect(css).toContain(".ds-web .ds-btn.ds-btn--is-focusVisible {");
});

it("leaves out values that would break the preview stylesheet", () => {
  expect(stateLines({ color: "red; } body { display: none", font: { family: "x) ; y" } })).toEqual([]);
});
