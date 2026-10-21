import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it, vi } from "vitest";
import PlanChanges from "./PlanChanges";
import type { PlanChangesView } from "../logic/use-plan-changes";

it("missing explicit card explains refresh and exposes no other card editor or proposal submit", () => {
  const model = { busy: false, readOnly: false, context: { acceptedHead: "a".repeat(40), acceptedDocuments: [], documents: [] },
    documents: [], document: undefined, fields: undefined, missingDocument: "fresh-process-card", subject: "Improve card",
    error: "", notice: "", items: [], refresh: vi.fn() } as unknown as PlanChangesView;
  const html = renderToStaticMarkup(createElement(PlanChanges, { model }));
  expect(html).toContain("fresh-process-card"); expect(html).toContain("jiná karta se místo ní nevybere");
  expect(html).toContain("Obnovit a zahodit rozepsané změny");
  expect(html).not.toContain("Uložit návrh změny"); expect(html).not.toContain("<textarea");
});
