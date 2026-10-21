import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { OverviewModels } from "@/hub/oporahub-overview/logic/models";
import { ExecutionDrawerContent } from "./OporaHubWorkspace";

describe("execution drawer exact observer selection", () => {
  it("shows requested observer B beside a truthful native-filter miss for A", () => {
    const requested = "b".repeat(32), filteredNative = "a".repeat(32), revision = "c".repeat(40), digest = "d".repeat(64);
    const item = { intent: {
      id: "e".repeat(40), project: "p", workspace: "w", requestId: "request", executionId: requested, nodeId: "task_b", epoch: 2, acceptedRevision: revision,
      assignmentDigest: digest, contextProtocolVersion: 2, contextVersion: digest, executionProtocolVersion: 2,
      budget: { policyHead: revision, familyId: revision, allocationId: revision, attempt: 1, repairRound: 0, kind: "initial", admittedAt: 100, runDeadlineAt: 130, maxRunSeconds: 30 },
      authorityDeadlineAt: 130, provider: "anthropic-managed-agents", repository: { url: "https://github.com/team/repo", commitSha: revision },
      agentId: "agent", agentVersion: 1, environmentId: "environment", environmentDigest: digest, configurationDigest: digest, maxListCostCents: "100", createdAt: "2026-10-21T10:00:00Z",
    }, observation: null, listBudgetExceeded: false };
    const models = {
      executions: { selected: { executionId: filteredNative }, busy: false, error: "", project: "p", workspace: "w", choices: [], nodeId: "task_a", executions: [], receipts: [], refresh: vi.fn() },
      executionObservations: { items: [item], busy: false, error: "", loadedAt: 1, project: "p", workspace: "w", observerConfigured: true, readOnly: true, providerAccessVerified: false,
        usageBasis: "observer-attested-provider-list-cost-not-invoice", refresh: vi.fn() },
    } as unknown as OverviewModels;
    const html = renderToStaticMarkup(createElement(ExecutionDrawerContent, { models, executionId: requested, onSelect: vi.fn() }));
    expect(html).toContain("Vybraný záznam není dostupný v načteném výběru");
    expect(html).toContain('aria-label="Přesné pozorování vybraného běhu"');
    expect(html).toContain("task_b");
    expect(html).toContain(revision);
    expect(html.match(/aria-label="Přesné pozorování vybraného běhu"/g)).toHaveLength(1);
    expect(html).not.toContain(filteredNative);
  });
});
