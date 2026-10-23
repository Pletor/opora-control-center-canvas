import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { PLAN_LENS_RESPONSE } from "../logic/plan-lens-fixture";
import { parsePlanLens } from "../logic/plan-lens-read";
import PlanLensStrip from "./PlanLensStrip";

describe("plan lens strip", () => {
  it("shows the six numbers, Graphify and the legend", () => {
    const html = renderToStaticMarkup(createElement(PlanLensStrip, { lens: parsePlanLens(PLAN_LENS_RESPONSE), busy: false, onReload: vi.fn() }));
    for (const key of ["areas", "cards", "withCode", "planned", "standalone", "unassigned"]) expect(html).toContain(`data-oh-plan-stat="${key}"`);
    expect(html).toContain(">3 karty<");
    expect(html).toContain('data-oh-plan-graphify="true"');
    expect(html).toContain("plná část = kód existuje");
    expect(html).toContain("šedá vazba „kód“ = vazba z Graphify");
    expect(html).toContain('data-oh-plan-area="area-login"');
  });
  it("says calmly when Graphify did not deliver code links", () => {
    const lens = parsePlanLens({ ...PLAN_LENS_RESPONSE, graphify: { available: false } });
    const html = renderToStaticMarkup(createElement(PlanLensStrip, { lens, busy: true, onReload: vi.fn() }));
    expect(html).toContain('data-oh-plan-graphify="false"');
    expect(html).toContain("Načítám…");
  });
});
