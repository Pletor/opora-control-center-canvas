import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import ConfirmProposal from "./ConfirmProposal";

it("locks confirmation and names missing evidence parts", () => {
  const html = renderToStaticMarkup(createElement(ConfirmProposal, {
    disabled: false, confirm: async () => true,
    readiness: { ready: false, missing: ["tests", "review"], notApplicable: [] },
  }));
  expect(html).toContain("disabled");
  expect(html).toContain("chybí důkazy: tests, review");
  expect(html).toContain('title="Nelze potvrdit, chybí důkazy: tests, review"');
});

it("keeps confirmation enabled when evidence is ready", () => {
  const html = renderToStaticMarkup(createElement(ConfirmProposal, {
    disabled: false, confirm: async () => true, readiness: { ready: true, missing: [], notApplicable: [] },
  }));
  expect(html).not.toContain("disabled");
  expect(html).not.toContain("chybí důkazy");
});
