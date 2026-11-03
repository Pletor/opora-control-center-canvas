import { expect, it } from "vitest";
import { readAppearance, withField } from "./appearance";
import { appearanceCss } from "./appearance-css";

it("renders the unsaved appearance under the preview root like the server base layer", () => {
  let appearance = readAppearance({ appearance: { colors: { text: "{ink}", link: "#1c6ed1" }, headings: { h1: { size: "3rem", weight: 700, lineHeight: 1.1 } } } });
  appearance = withField(appearance, "background.color", "#fafaf5");
  appearance = withField(appearance, "lists.indent", "24");
  const css = appearanceCss(appearance, "p1");
  expect(css).toContain(".ds-web {\n  background-color: #fafaf5;\n  color: var(--ink);");
  expect(css).toContain(".ds-web h1 {\n  font-size: 3rem;\n  font-weight: 700;\n  line-height: 1.1;\n}");
  expect(css).toContain(".ds-web a {\n  color: #1c6ed1;\n}");
  expect(css).toContain(".ds-web ul, .ds-web ol {\n  padding-inline-start: 24px;");
  expect(css).not.toContain(".ds-web h2");
});

it("layers overlay, pattern and image like the server and loads the image from the project API", () => {
  let appearance = readAppearance({});
  appearance = withField(appearance, "background.overlay.color", "#000000");
  appearance = withField(appearance, "background.overlay.opacity", 0.25);
  appearance = withField(appearance, "background.pattern.preset", "grid");
  appearance = withField(appearance, "background.pattern.scale", 2);
  appearance = withField(appearance, "background.image.asset", "assets/web/vlny.png");
  const css = appearanceCss(appearance, "p1");
  expect(css).toContain("color-mix(in srgb, #000000 25%, transparent)");
  expect(css).toContain("background-size: auto, 32px 32px, 32px 32px, cover;");
  expect(css).toContain('url("/api/site-admin/assets/web/vlny.png?project=p1")');
});

it("never writes a value that could close the declaration", () => {
  const appearance = withField(readAppearance({}), "colors.link", "red; } body { display: none");
  expect(appearanceCss(appearance, "p1")).toBe("");
});
