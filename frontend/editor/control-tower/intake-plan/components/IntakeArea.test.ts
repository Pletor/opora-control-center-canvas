import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import IntakeArea from "./IntakeArea";
import { intakePlan } from "../logic/intake-plan";
import { intakeFixture } from "../logic/intake-fixture";
import { briefFixture } from "../brief-panel/logic/brief-fixture";

const plan = intakePlan(intakeFixture, id => id);
const render = (index: number, extra: Partial<{ busy: string | null; errors: Record<string, string> }> = {}) =>
  renderToStaticMarkup(createElement(IntakeArea, { area: plan.areas[index], busy: null, errors: {}, onDecide: () => {}, onOpen: () => {},
    brief: { busy: null, errors: {}, onAnswer: () => {}, onStart: () => {} }, ...extra }));

it("oblast s aktivním milníkem: postup, checklist, otevřené a odložené požadavky", () => {
  const html = render(0);
  expect(html).toContain("Vyhledání");
  expect(html).toContain("aria-valuenow=\"50\"");
  expect(html).toContain("width:50%");
  expect(html).toContain("intake-plan__criterion--done");
  expect(html).toContain("Otevřené požadavky · 1");
  expect(html).toContain("otevře se po splnění milníku „bge-m3 lokálně“");
  expect(html).not.toContain("Aktivovat");
});

it("návrh srdce nese Aktivovat a Zamítnout; při zápisu ztichnou a chyba se ukáže textem", () => {
  expect(render(1)).toContain("Aktivovat");
  expect(render(1)).toContain("Aktivní milník zatím není.");
  const busy = render(1, { busy: "ms_2", errors: { ms_2: "Milník se nepodařilo aktivovat: x" } });
  expect(busy).toContain("disabled");
  expect(busy).toContain("role=\"alert\"");
  expect(busy).toContain("Milník se nepodařilo aktivovat: x");
});

it("prázdná oblast řekne jednu krátkou větu", () => {
  const html = render(2);
  expect(html).toContain("intake-plan__area--empty");
  expect(html).toContain("Oblast zatím nemá milník ani požadavky.");
});

it("požadavek bez spisu nabídne výslech, se spisem ukáže otázku srdce", () => {
  expect(render(0)).toContain("Vyslechni mě k tomu");
  const withBrief = intakePlan({ ...intakeFixture, areas: [{ ...intakeFixture.areas[0], requirements: [
    { ...intakeFixture.areas[0].requirements[0], brief: briefFixture }] }] }, id => id);
  const html = renderToStaticMarkup(createElement(IntakeArea, { area: withBrief.areas[0], busy: null, errors: {}, onDecide: () => {},
    onOpen: () => {}, brief: { busy: null, errors: {}, onAnswer: () => {}, onStart: () => {} } }));
  expect(html).toContain("Kdo to čte?");
  expect(html).toContain("Potvrdit doporučení");
});
