import { expect, it } from "vitest";
import { customCssPreview, REDUCED_MOTION_CSS } from "./custom-css-preview";

const source = `/* lesk po najetí */
:scope { position: relative; overflow: hidden; }
:scope::after { content: ""; position: absolute; inset: 0; background: url("assets/web/lesk.png"); }
:scope:hover::after { animation: shine 600ms ease-out; }
.ikona { margin-left: 4px; }
@keyframes shine { from { transform: translateX(-100%); } to { transform: translateX(100%); } }
@media (min-width: 600px) { :scope { letter-spacing: 0.02em; } }`;

it("rewrites the draft like the server: scope root, descendants, renamed keyframes and asset urls", () => {
  const result = customCssPreview("primary", source, "p1");
  if (!("css" in result)) throw new Error(result.problem.reason);
  expect(result.css).toContain(".ds-web .ds-btn--primary { position: relative; overflow: hidden; }");
  expect(result.css).toContain('.ds-web .ds-btn--primary::after { content: ""; position: absolute; inset: 0; background: url("/api/site-admin/assets/web/lesk.png?project=p1"); }');
  expect(result.css).toContain(".ds-web .ds-btn--primary:hover::after { animation: ds-btn-primary-shine 600ms ease-out; }");
  expect(result.css).toContain(".ds-web .ds-btn--primary .ikona {");
  expect(result.css).toContain("@keyframes ds-btn-primary-shine { from {");
  expect(result.css).toContain("@media (min-width: 600px) {\n.ds-web .ds-btn--primary { letter-spacing: 0.02em; }\n}");
});

it("refuses what could leave the button and says on which line", () => {
  expect(customCssPreview("x", ":scope { color: red; }\n} body { display: none; }", "p1")).toEqual({ problem: { line: 2, reason: "Přebývá zavírací závorka }." } });
  expect(customCssPreview("x", ":scope {\n  color: red;\n", "p1")).toEqual({ problem: { line: 1, reason: "Chybí zavírací závorka }." } });
  expect(customCssPreview("x", ":scope { color: red; }\nbody { color: red; }", "p1")).toMatchObject({ problem: { line: 2 } });
  expect(customCssPreview("x", "\n\n:scope { background: url(https://evil.test/x.png); }", "p1")).toMatchObject({ problem: { line: 3 } });
  expect(customCssPreview("x", "@import 'x.css';", "p1")).toMatchObject({ problem: { line: 1 } });
  expect(customCssPreview("x", "@font-face { font-family: x; }", "p1")).toMatchObject({ problem: { line: 1, reason: expect.stringContaining("@font-face") } });
  expect(customCssPreview("x", ":scope { :hover { color: red; } }", "p1")).toMatchObject({ problem: { line: 1 } });
});

it("switches motion off for the reduced motion toggle and for the system setting", () => {
  expect(REDUCED_MOTION_CSS).toContain(".ds-web.ds-web--still .ds-btn::after");
  expect(REDUCED_MOTION_CSS).toContain("@media (prefers-reduced-motion: reduce) { .ds-web .ds-btn,");
});
