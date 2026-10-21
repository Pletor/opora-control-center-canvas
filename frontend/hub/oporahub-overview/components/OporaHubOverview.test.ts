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

it("shows scoped provider observations in the overview without treating idle as termination", () => {
  const refresh = vi.fn(), empty = { context: null, items: [], busy: false, error: "", refresh };
  const executionId = "c".repeat(32);
  const models = { graphProposals: empty, changes: empty, evidence: empty,
    executions: { ...empty, executions: [], choices: [], nodeId: "" }, reconciliation: empty, reviewPolicy: empty,
    formalVerification: { refresh }, onRefresh: refresh,
    executionObservations: { items: [{ intent: { id: "a".repeat(40), executionId, nodeId: "task_1", epoch: 2, createdAt: "2026-10-21T10:00:00Z" },
      observation: { status: "running", providerStatus: "idle", sessionId: "session:1", cumulative: { listCostCents: "187" }, observedAt: "2026-10-21T10:01:00Z", source: "provider-api" }, listBudgetExceeded: false }],
      readOnly: false, observerConfigured: true, providerAccessVerified: false, usageBasis: "observer-attested-provider-list-cost-not-invoice", busy: false, error: "", project: "project", workspace: "workspace", loadedAt: Date.now(), refresh },
  } as unknown as OverviewModels;
  const html = renderToStaticMarkup(createElement(OporaHubOverview, { models, open: vi.fn() }));
  expect(html).toContain("Pozorování běhů");
  expect(html).toContain(executionId.slice(0, 8));
  expect(html).toContain("Překročený rozpočet: 0 · nedoložená spotřeba: 0");
  expect(html).toContain("1,87 USD podle ceníku");
  expect(html).toContain("Poskytovatel hlásí nečinný stav; běh není potvrzen jako ukončený");
  expect(html).toContain("API poskytovatele doložené brokerem");
});
