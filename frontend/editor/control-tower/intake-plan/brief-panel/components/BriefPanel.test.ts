import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import BriefPanel from "./BriefPanel";
import { briefView, type BriefActions } from "../logic/brief-model";
import { briefFixture } from "../logic/brief-fixture";

const actions = (extra: Partial<BriefActions> = {}): BriefActions =>
  ({ busy: null, errors: {}, onAnswer: () => {}, onStart: () => {}, ...extra });
const render = (brief: unknown, extra: Partial<BriefActions> = {}) =>
  renderToStaticMarkup(createElement(BriefPanel, { requirement: "rq_1", brief: briefView(brief), actions: actions(extra) }));

it("výslech čeká na člověka: otázka s doporučením a důvodem, tlačítka, pochopení a co chybí", () => {
  const html = render(briefFixture);
  expect(html).toContain("brief-panel--ask");
  expect(html).toContain("Srdce potřebuje vaši odpověď");
  expect(html).toContain("Kdo to čte?");
  expect(html).toContain("Srdce doporučuje");
  expect(html).toContain("Proč: Určí rozsah.");
  expect(html).toContain("Potvrdit doporučení");
  expect(html).toContain("Odpovědět jinak");
  expect(html).toContain("Provozní metriky srdce pro člověka ve Velínu.");
  expect(html).toContain("z rešerše: https://sre.google/sre-book/");
  expect(html).toContain("Co se dělat nebude");
  expect(html).toContain("Do jasna ještě chybí");
  expect(html).toContain("Vaše odpovědi · 1");
  expect(html).not.toContain("rq_1");
  expect(html).not.toContain(">q2<");
});

it("při odesílání tlačítka ztichnou a chyba se ukáže textem", () => {
  const html = render(briefFixture, { busy: "brief:rq_1:q2", errors: { "brief:rq_1:q2": "Odpověď se nepodařilo odeslat: x" } });
  expect(html).toContain("disabled");
  expect(html).toContain("Posílám odpověď srdci…");
  expect(html).toContain("role=\"alert\"");
});

it("bez spisu jen tlačítko Vyslechni mě k tomu", () => {
  const html = render(null);
  expect(html).toContain("Vyslechni mě k tomu");
  expect(html).not.toContain("Potvrdit doporučení");
  expect(render(null, { busy: "brief:rq_1" })).toContain("Budím srdce…");
});

it("spis bez syntézy řekne, že pochopení ještě není", () => {
  expect(render({ status: "draft", synthesis: null, questions: [], missing: [] })).toContain("Pochopení zatím není sepsané.");
});

it("kořen ve Schránce: tlačítko Otevřít ve Schránce, jen když ho rodič umí otevřít", () => {
  const linked = { ...briefFixture, fragmentId: "f1", fragmentScope: "" };
  const html = render(linked, { onOpenVault: () => {} });
  expect(html).toContain("Otevřít ve Schránce");
  expect(html).toContain("data-oh-fragment=\"f1\"");
  expect(render(linked)).not.toContain("Otevřít ve Schránce");
  expect(render(briefFixture, { onOpenVault: () => {} })).not.toContain("Otevřít ve Schránce");
});
