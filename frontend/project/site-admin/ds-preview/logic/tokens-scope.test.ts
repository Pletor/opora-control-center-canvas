import { expect, it } from "vitest";
import { cssLength, cssLineHeight, scopeTokensCss } from "./tokens-scope";

const css = `/* Ember — generated from tokens.json */
:root, [data-theme="light"] {
  --ink: #2a1f1a;
}
[data-theme="dark"] {
  --ink: #f4ebe3;
}
:root {
  --space-1\\.5: 6px;
}
.display {
  font-family: var(--font-sans);
}
@font-face {
  font-family: "Inter";
  src: url("fonts/inter.woff2") format("woff2");
}
`;

it("closes every selector of tokens.css into the preview scope and points fonts to the project API", () => {
  const out = scopeTokensCss(css, "p1");
  expect(out).toContain('.ds-scope, .ds-scope[data-theme="light"] {');
  expect(out).toContain('.ds-scope[data-theme="dark"] {');
  expect(out).toContain(".ds-scope {\n  --space-1\\.5: 6px;");
  expect(out).toContain(".ds-scope .display {");
  expect(out).toContain('@font-face {');
  expect(out).toContain('src: url("/api/site-admin/fonts/inter.woff2?project=p1") format("woff2");');
  expect(out).toContain("/* Ember — generated from tokens.json */");
  expect(out).not.toMatch(/^:root/m);
});

it("turns token numbers into css lengths like the server does", () => {
  expect(cssLength("16")).toBe("16px");
  expect(cssLength("0")).toBe("0");
  expect(cssLength("1.5rem")).toBe("1.5rem");
  expect(cssLength("")).toBeUndefined();
  expect(cssLineHeight(1.4)).toBe("1.4");
  expect(cssLineHeight("40")).toBe("40px");
  expect(cssLineHeight("22px")).toBe("22px");
});
