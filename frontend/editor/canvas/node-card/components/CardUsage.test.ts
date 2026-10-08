import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import CardUsage from "./CardUsage";

it("keeps unknown distinct from measured zero", () => {
  const unknown = renderToStaticMarkup(createElement(CardUsage, { sector: false }));
  expect(unknown).toContain("Tokeny: nedostupné");
  const measured = renderToStaticMarkup(createElement(CardUsage, { sector: true,
    usage: { tokens: 0, durationMs: 1500, attempts: null, reports: 1 } }));
  expect(measured).toContain("Součet sektoru");
  expect(measured).toContain("Tokeny: 0");
  expect(measured).toContain("1,5 s");
  expect(measured).toContain("Pokusy: nedostupné");
});
