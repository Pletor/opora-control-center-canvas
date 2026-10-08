import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import CardDesign, { safeDesignUrl, safePreviewUrl } from "./CardDesign";
it("DNA odkazy nepovolují nešifrované http", () => {
  expect(safeDesignUrl("http://example.com/proof")).toBe(false);
});

it("shows version and an on-demand preview button linking to the artifact", () => {
  const html = renderToStaticMarkup(createElement(CardDesign, { design: {
    artifactUrl: "https://example.com/design", version: "v2", previewUrl: "https://example.com/screen.png",
  } }));
  expect(html).toContain('href="https://example.com/design"');
  expect(html).toContain("Zobrazit náhled");
  expect(html).not.toContain("<img");
  expect(html).not.toContain("https://example.com/screen.png");
  expect(html).toContain("v2");
  expect(html).toContain('rel="noopener noreferrer"');
});

it("keeps the artifact accessible without a thumbnail", () => {
  const html = renderToStaticMarkup(createElement(CardDesign, { design: { artifactUrl: "https://example.com/design", version: "v1" } }));
  expect(html).toContain("href=");
  expect(html).not.toContain("<img");
  expect(html).not.toContain("Zobrazit náhled");
});

it("offers preview only for https URLs", () => {
  expect(safePreviewUrl("https://example.com/a.png")).toBe(true);
  expect(safePreviewUrl("http://example.com/a.png")).toBe(false);
  expect(safePreviewUrl("javascript:alert(1)")).toBe(false);
  expect(safePreviewUrl(undefined)).toBe(false);
  const html = renderToStaticMarkup(createElement(CardDesign, { design: {
    artifactUrl: "https://example.com/design", version: "v1", previewUrl: "http://example.com/a.png" } }));
  expect(html).not.toContain("Zobrazit náhled");
});

it.each(["javascript:alert(1)", "data:text/html,hi", "//example.com/x", "https://user:secret@example.com", "https://example.com:bad/x", "https://example.com/\nx", "https://example.com\\x", ""])("rejects unsafe design link %s", url => {
  expect(safeDesignUrl(url)).toBe(false);
  expect(renderToStaticMarkup(createElement(CardDesign, { design: { artifactUrl: url, version: "v1" } }))).toBe("");
});
