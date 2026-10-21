import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { OverviewModels } from "../logic/models";
import OporaHubOverview from "./OporaHubOverview";

describe("overview evidence entry point", () => {
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
