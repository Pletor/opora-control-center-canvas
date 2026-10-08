import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import EvidenceEditor from "./EvidenceEditor";

it("starts with pending proof controls and no invented command runs", () => {
  const html = renderToStaticMarkup(createElement(EvidenceEditor, { nodeId: "n", disabled: false, save: async () => true }));
  expect(html.match(/value="pending" selected=""/g)).toHaveLength(3);
  expect(html).toContain("Přidat provedenou kontrolu");
  expect(html).not.toContain("Kontrola 1");
  expect(html).toContain("Uložit důkazy");
});

it("disables evidence editing on a closed or read-only card", () => {
  const html = renderToStaticMarkup(createElement(EvidenceEditor, { nodeId: "n", disabled: true, save: async () => true }));
  expect(html).toContain('<fieldset disabled="">');
});
