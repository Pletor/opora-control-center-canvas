import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import CardLease, { leaseSeconds } from "./CardLease";

it("counts down using server time and clamps expired ownership to zero", () => {
  const lease = { owner: "Agent A", expiresAt: 1060, active: true, serverOffset: 900 };
  expect(leaseSeconds(lease, 100000)).toBe(60);
  expect(leaseSeconds(lease, 161000)).toBe(0);
  const html = renderToStaticMarkup(createElement(CardLease, { lease: { ...lease, expiresAt: 0 } }));
  expect(html).toContain("Agent A");
  expect(html).toContain("převzetí vypršelo");
  expect(html).toContain("#94a3b8");
});

it("offers the human a release button only when a release callback is wired", () => {
  const lease = { owner: "Agent A", expiresAt: 0, active: true, serverOffset: 0 };
  expect(renderToStaticMarkup(createElement(CardLease, { lease }))).not.toContain("Uvolnit");
  expect(renderToStaticMarkup(createElement(CardLease, { lease, release: async () => {} }))).toContain("Uvolnit");
});
