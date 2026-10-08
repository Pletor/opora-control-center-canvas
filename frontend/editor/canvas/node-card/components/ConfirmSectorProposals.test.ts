import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import ConfirmSectorProposals, { selectableIds } from "./ConfirmSectorProposals";

const ready = { ready: true, missing: [], notApplicable: [] };

it("lists each proposed card with checked controls and a batch confirmation", () => {
  const html = renderToStaticMarkup(createElement(ConfirmSectorProposals, {
    proposals: [{ id: "a", name: "Database", note: "Tests passed", readiness: ready }, { id: "b", name: "Frontend", note: "Review ready", readiness: ready }],
    disabled: false, confirm: async () => {},
  }));
  expect(html.match(/type="checkbox"/g)).toHaveLength(2);
  expect(html.match(/checked=""/g)).toHaveLength(2);
  expect(html).toContain("Database");
  expect(html).toContain("Frontend");
  expect(html).toContain("Potvrdit vybrané (2)");
  expect(html).toContain("důkazy deklarovány");
});

it("allows batch selection only for ready evidence without N/A", () => {
  const proposals = [
    { id: "ok", name: "A", note: "", readiness: ready },
    { id: "missing", name: "B", note: "", readiness: { ready: false, missing: ["tests" as const, "review" as const], notApplicable: [] } },
    { id: "na", name: "C", note: "", readiness: { ready: true, missing: [], notApplicable: ["merge" as const] } },
    { id: "unknown", name: "D", note: "" },
  ];
  expect(selectableIds(proposals)).toEqual(["ok"]);
  const html = renderToStaticMarkup(createElement(ConfirmSectorProposals, { proposals, disabled: false, confirm: async () => {} }));
  expect(html.match(/type="checkbox"/g)).toHaveLength(4);
  expect(html.match(/checked=""/g)).toHaveLength(1);
  expect(html).toContain("chybí důkazy: tests, review");
  expect(html).toContain("obsahuje N/A: merge");
  expect(html).toContain("Potvrdit vybrané (1)");
});
