import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import SectorAutonomy, { AUTONOMY_PRESETS, autonomyUntil } from "./SectorAutonomy";
import CardEvidence from "./CardEvidence";

it("shows scoped human grant, expiry and revocation controls", () => {
  const html = renderToStaticMarkup(createElement(SectorAutonomy, {
    sectorId: "s", name: "Backend", grant: { until: "2099-01-01T12:00:00Z", grantedAt: "2026-10-07T12:00:00Z", grantedBy: "Reviewer", note: "Approved" },
    disabled: false, save: async () => {},
  }));
  expect(html).toContain("Autonomie: do ");
  expect(html).toContain("board-bar__chip--on");
  expect(html).toContain("Backend");
  expect(html).toContain("Reviewer");
  expect(html).toContain("Vypnout autonomii");
  expect(html).toContain("Bránu sektoru potvrzuje vždy člověk");
});

it("marks expired grants and autonomous completion distinctly", () => {
  const html = renderToStaticMarkup(createElement(SectorAutonomy, {
    sectorId: "s", name: "Backend", grant: { until: "2000-01-01T12:00:00Z", grantedAt: "1999-12-31T12:00:00Z", note: "" }, disabled: true, save: async () => {},
  }));
  expect(html).toContain("vypršela");
  expect(html).not.toContain("board-bar__chip--on");
  expect(html.match(/<button type="button"[^>]*disabled=""/g)).toHaveLength(AUTONOMY_PRESETS.length + 1);
  expect(renderToStaticMarkup(createElement(CardEvidence, { autonomous: true }))).toContain("Uzavřel agent");
});

it("turns autonomy on with one click on a preset, within the 30 day server limit", () => {
  const html = renderToStaticMarkup(createElement(SectorAutonomy, { sectorId: "s", name: "Backend", disabled: false, save: async () => {} }));
  expect(html).toContain("Autonomie: vypnuto");
  for (const preset of AUTONOMY_PRESETS) expect(html).toContain(`>${preset.label}<`);
  expect(Math.max(...AUTONOMY_PRESETS.map((p) => p.hours))).toBeLessThanOrEqual(30 * 24);
  expect(autonomyUntil(Date.UTC(2026, 0, 1), 8)).toBe("2026-01-01T08:00:00.000Z");
});
