import { expect, it } from "vitest";
import { assetUrls, PREVIEW_RESET, scopeComponentsCss, scopeWebSelector, splitSelectors } from "./components-scope";

const css = `/* Ember — components.css, generated from design-system.json; load after tokens.css */
@layer base, components, custom;
@layer base {
  body {
    background-color: var(--surface);
    background-image: url("assets/pozadi/vlny.png");
  }
  ul, ol {
    padding-inline-start: var(--list-indent);
  }
  :focus-visible {
    outline: 2px solid var(--focus);
  }
}
@layer components {
  .ds-btn--primary:disabled, .ds-btn--primary[aria-disabled="true"] {
    --btn-bg: #ccc;
  }
}
@layer custom {
  /* .ds-btn--primary */
  .ds-btn--primary:hover::after {
    animation: ds-btn-primary-pulse 400ms ease;
  }
  @keyframes ds-btn-primary-pulse {
    from {
      opacity: 0;
    }
    50% {
      opacity: 1;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .ds-btn--primary, .ds-btn--primary::after {
      animation-duration: 0.01ms !important;
    }
  }
}
`;

it("splits selectors only on top-level commas", () => {
  expect(splitSelectors('a, b:not(.x, .y), [data-x="1,2"]')).toEqual(["a", "b:not(.x, .y)", '[data-x="1,2"]']);
});

it("makes body the preview root and every other selector its descendant", () => {
  expect(scopeWebSelector("body")).toBe(".ds-web");
  expect(scopeWebSelector("ul, ol")).toBe(".ds-web ul, .ds-web ol");
  expect(scopeWebSelector(".ds-btn--x:hover")).toBe(".ds-web .ds-btn--x:hover");
});

it("closes components.css into the preview, unwraps layers and keeps keyframe steps", () => {
  const out = scopeComponentsCss(css, "p1");
  expect(out).not.toContain("@layer");
  expect(out).toContain("  .ds-web {\n    background-color: var(--surface);");
  expect(out).toContain('background-image: url("/api/site-admin/assets/pozadi/vlny.png?project=p1");');
  expect(out).toContain("  .ds-web ul, .ds-web ol {");
  expect(out).toContain("  .ds-web :focus-visible {");
  expect(out).toContain('  .ds-web .ds-btn--primary:disabled, .ds-web .ds-btn--primary[aria-disabled="true"] {');
  expect(out).toContain("  .ds-web .ds-btn--primary:hover::after {");
  expect(out).toContain("    from {\n      opacity: 0;");
  expect(out).toContain("    50% {");
  expect(out).toContain("    .ds-web .ds-btn--primary, .ds-web .ds-btn--primary::after {");
  expect(out.split("{").length).toBe(out.split("}").length);
});

it("points unquoted asset urls from sanitized custom CSS to the project API", () => {
  expect(assetUrls("background: url(assets/ikony/sipka.svg) no-repeat;", "p1"))
    .toBe('background: url("/api/site-admin/assets/ikony/sipka.svg?project=p1") no-repeat;');
});

it("resets the app element styles inside the preview without outweighing the site rules", () => {
  expect(PREVIEW_RESET).toContain(".ds-web :where(h3) { font-size: 1.17em; }");
  expect(PREVIEW_RESET.split("\n").every((line) => line.startsWith(".ds-web :where("))).toBe(true);
});
