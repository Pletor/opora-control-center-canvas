import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { OverviewModels } from "../logic/models";
import OporaHubOverview from "./OporaHubOverview";
import { contentList } from "@/hub/content-changes/logic/content-fixtures";

describe("overview evidence entry point", () => {
  it("renders the content entry point and real pending content in decisions and activity", () => {
    const refresh = vi.fn(), empty = { context: null, items: [], busy: false, error: "", refresh };
    const models = { graphProposals: empty, changes: empty, evidence: empty,
      executions: { ...empty, executions: [], choices: [], nodeId: "" }, reconciliation: empty, reviewPolicy: empty,
      formalVerification: { refresh }, onRefresh: refresh,
      contentChanges: { ...empty, list: contentList(), items: contentList().items } } as unknown as OverviewModels;
    const html = renderToStaticMarkup(createElement(OporaHubOverview, { models, open: vi.fn() }));
    expect(html).toContain("Otevřít změny obsahu");
    expect(html).toContain("Pravidla přijetí plánů");
    expect(html).toContain("Pravidla nedoložena");
    expect(html).toContain("Změna obsahu · 1 položek textu, kresby nebo konfigurace.");
    expect(html).toContain("Návrh obsahu");
    expect(html).not.toContain("<script>");
  });
  it("renders the formal evidence button in the actual overview", () => {
    const refresh = vi.fn();
    const empty = { context: null, items: [], busy: false, error: "", refresh };
    const models = {
      graphProposals: empty, changes: empty, evidence: empty,
      executions: { ...empty, executions: [], choices: [], nodeId: "" },
      reconciliation: empty, reviewPolicy: empty,
      formalVerification: { refresh }, onRefresh: refresh,
    } as unknown as OverviewModels;

    const html = renderToStaticMarkup(createElement(OporaHubOverview, { models, open: vi.fn() }));

    expect(html).toMatch(/<button[^>]*>Formální podklady<\/button>/);
  });
});
