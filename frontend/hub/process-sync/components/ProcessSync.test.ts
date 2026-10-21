import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it, vi } from "vitest";
import { ProcessSyncView } from "./ProcessSync";
import { processFixture } from "../logic/process-fixtures";

it("renders scoped process states, observation and copyable API without implied verification", () => {
  const snapshot = processFixture(); snapshot.items[0].status = "reported";
  const html = renderToStaticMarkup(createElement(ProcessSyncView, { snapshot, busy: false, error: "", refresh: vi.fn(), project: "draft", workspace: "draft", open: vi.fn(), onImprove: vi.fn() }));
  for (const text of ["Proces Control Center", "Kontrola změny", "Nahlášeno · vyžaduje kontrolu", "Navrhnout zlepšení", "Poslední pozorování", "GET /api/oporahub/process?project=draft", "Nahlášení není ověření, merge ani nasazení."]) expect(html).toContain(text);
  expect(html).not.toContain("<script");
});
it("an unavailable process shows the error and no old ready cards", () => {
  const html = renderToStaticMarkup(createElement(ProcessSyncView, { snapshot: null, busy: false, error: "Zdroj nedostupný", refresh: vi.fn(), project: "other", workspace: "draft", open: vi.fn(), onImprove: vi.fn() }));
  expect(html).toContain("Zdroj nedostupný"); expect(html).not.toContain("Připraveno k převzetí"); expect(html).toContain("project=other");
});
