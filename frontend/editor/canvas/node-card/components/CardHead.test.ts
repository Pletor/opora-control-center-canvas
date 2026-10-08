import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import CardHead from "./CardHead";

it("shows layer, model and a human request directly on the card", () => {
  const html = renderToStaticMarkup(createElement(CardHead, { view: { kind: "node", phase: "build", phaseLabel: "build",
    closed: false, doneProposed: false, cardLayer: "backend", cardModel: "sonnet", cardEffort: "high",
    waitingOnHuman: [{ blockId: "b", ask: "Doplň adresu projektu" }] } }));
  expect(html).toContain("BE");
  expect(html).toContain("sonnet");
  expect(html).toContain("effort: high");
  expect(html).toContain("Čeká na tebe: Doplň adresu projektu");
});

it("does not show a human request on a confirmed card", () => {
  const html = renderToStaticMarkup(createElement(CardHead, { view: { kind: "node", phase: "build", phaseLabel: "build",
    closed: true, doneProposed: false, waitingOnHuman: [{ blockId: "b", ask: "Old request" }] } }));
  expect(html).not.toContain("Old request");
});
import { createElement } from "react";
