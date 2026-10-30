import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import CardGaugeBadge from "./CardGaugeBadge";
import { gaugeBadge } from "../logic/card-gauge-badge";

it("ukáže štítek, % kroků a riziko jen mimo standard", () => {
  const html = renderToStaticMarkup(createElement(CardGaugeBadge, { badge: gaugeBadge({
    steps: { total: 4, done: 1, percent: 25 }, risk: { level: "elevated", reasons: ["text: migrace"] }, run: { label: "M" } }) }));
  expect(html).toContain("card-gauge__label\">M<");
  expect(html).toContain("25 %");
  expect(html).toContain("card-gauge__risk--elevated");
  const plain = renderToStaticMarkup(createElement(CardGaugeBadge, { badge: gaugeBadge({ risk: { level: "standard" }, run: { label: "XS" } }) }));
  expect(plain).not.toContain("card-gauge__risk");
});

it("chudé podklady dostanou variantu thin a bez gauge se nic nekreslí", () => {
  expect(renderToStaticMarkup(createElement(CardGaugeBadge, { badge: gaugeBadge({ evidence: "thin", run: { label: "?" } }) })))
    .toContain("card-gauge--thin");
  expect(renderToStaticMarkup(createElement(CardGaugeBadge, { badge: null }))).toBe("");
});
