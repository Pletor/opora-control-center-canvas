import { describe, expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ExecutionObservations from "./ExecutionObservations";
import { parseObservationSnapshot } from "../logic/observations";
import type { ExecutionObservationsView } from "../logic/use-execution-observations";

const id40 = "a".repeat(40), id64 = "b".repeat(64);
const intent = { project: "p", workspace: "w", requestId: "request", executionId: "c".repeat(32), nodeId: "node", epoch: 1, acceptedRevision: id40,
  assignmentDigest: id64, contextProtocolVersion: 2, contextVersion: id64, executionProtocolVersion: 2,
  budget: { policyHead: id40, familyId: "d".repeat(40), allocationId: "e".repeat(40), attempt: 1, repairRound: 0, kind: "initial", admittedAt: 100, runDeadlineAt: 130, maxRunSeconds: 30 },
  authorityDeadlineAt: 130, provider: "anthropic-managed-agents", repository: { url: "https://github.com/team/repo", commitSha: id40 }, agentId: "agent", agentVersion: 1,
  environmentId: "environment", environmentDigest: id64, configurationDigest: id64, maxListCostCents: "100" };
const metadata = { id: id40, schemaVersion: 1, kind: "execution-intent", observerId: "observer", createdAt: "2026-10-21T10:00:00Z", requestDigest: id64, executionBinding: "canvas-verified", providerBinding: "observer-attested" };
const snapshot = (observation: Record<string, unknown> | null = null, exceeded = false, maxListCostCents = "100") => parseObservationSnapshot({ items: [{ intent: { ...intent, ...metadata, maxListCostCents }, observation, listBudgetExceeded: exceeded }], readOnly: true, observerConfigured: true,
  providerAccessVerified: false, usageBasis: "observer-attested-provider-list-cost-not-invoice" }, "p", "w");
const observed = (sessionId: string | null, providerStatus: string | null, status: string, listCostCents: string) => ({ project: "p", workspace: "w", intentId: id40, requestId: "observe", expectedObservationHead: null, sequence: 1,
  sessionId, observedAt: "2026-10-21T10:01:00Z", source: "provider-api", status, providerStatus,
  cumulative: { inputTokens: sessionId ? 2 : 0, outputTokens: sessionId ? 3 : 0, cacheReadInputTokens: sessionId ? 4 : 0, cacheCreation5mTokens: sessionId ? 5 : 0, cacheCreation1hTokens: sessionId ? 6 : 0, listCostCents, currency: "USD", activeSeconds: sessionId ? 3.5 : 0 },
  id: "f".repeat(40), schemaVersion: 1, kind: "execution-observation", observerId: "observer", createdAt: "2026-10-21T10:01:00Z", requestDigest: id64, executionBinding: "canvas-verified", providerBinding: "observer-attested" });
const model = (items: ReturnType<typeof snapshot>["items"]) => ({ items, busy: false, error: "", loadedAt: Date.now(), project: "p", workspace: "w", observerConfigured: true, providerAccessVerified: false, readOnly: true, usageBasis: "observer-attested-provider-list-cost-not-invoice", refresh() {} } as ExecutionObservationsView);

describe("ExecutionObservations", () => {
  it("keeps missing configuration distinct from configured-but-unverified", () => {
    const make = (configured: boolean) => renderToStaticMarkup(createElement(ExecutionObservations, { model: { ...parseObservationSnapshot({ items: [], readOnly: true, observerConfigured: configured, providerAccessVerified: false, usageBasis: "observer-attested-provider-list-cost-not-invoice" }, "p", "w"), busy: false, error: "", loadedAt: null, project: "p", workspace: "w", refresh() {} } as ExecutionObservationsView }));
    expect(make(false)).toContain("Broker pozorov\u00e1n\u00ed nen\u00ed v tomto prostoru nakonfigurov\u00e1n");
    expect(make(true)).toContain("přístup k poskytovateli nebyl tímto čtením ověřen");
  });
  it("shows exact identity without authority or mutation controls", () => {
    const html = renderToStaticMarkup(createElement(ExecutionObservations, { model: model(snapshot().items), selectedExecutionId: "c".repeat(32) }));
    expect(html).toContain("Zatím bez pozorování poskytovatele");
    expect(html).toContain("Přijatá revize");
    expect(html).toContain("nepotvrzuje ukončení");
    expect(html).not.toContain("checkbox");
    expect(html).not.toContain("Povolit");
  });
  it("shows exact broker-attested cost in summary and has no dead selection button", () => {
    const html = renderToStaticMarkup(createElement(ExecutionObservations, { model: model(snapshot(observed("session:1", "idle", "idle", "187"), true).items) }));
    expect(html).toContain("1,87 USD podle ceníku");
    expect(html).toContain("Překročen ceníkový rozpočet");
    expect(html).toContain("Záznamy z API poskytovatele doložené brokerem");
    expect(html).not.toContain("aria-pressed");
    expect(html).not.toContain("Poskytovatelův odhad");
  });
  it("does not display zero sentinels as usage without a provider session", () => {
    const html = renderToStaticMarkup(createElement(ExecutionObservations, { model: model(snapshot(observed(null, null, "creation_unknown", "0")).items), selectedExecutionId: "c".repeat(32) }));
    expect(html).toContain("Spotřeba nedoložena");
    expect(html).toContain("Broker zatím nedoložil čtení konkrétní session");
    expect(html).not.toContain("0,00 USD");
    expect(html).not.toContain("Vstupní tokeny");
  });
  it("does not substitute another observer intent for the requested execution-intent pair", () => {
    const html = renderToStaticMarkup(createElement(ExecutionObservations, { model: model(snapshot().items), selectedExecutionId: "c".repeat(32), selectedIntentId: "wrong-intent" }));
    expect(html).toContain("Vybraný běh není v tomto rozsahu načtených pozorování");
    expect(html).not.toContain("Přijatá revize");
  });
  it("keeps the compact overview bounded while surfacing missing usage and budget overruns", () => {
    const first = snapshot(observed("session:1", "idle", "idle", "187"), true).items[0];
    const unknown = snapshot(observed(null, null, "creation_unknown", "0")).items[0];
    const exceeded = snapshot(observed("session:3", "running", "running", "250"), false, "1000").items[0];
    const items = [first, { ...unknown, intent: { ...unknown.intent, id: "d".repeat(40), executionId: "e".repeat(32), nodeId: "task_unknown" } },
      { ...exceeded, intent: { ...exceeded.intent, id: "f".repeat(40), executionId: "1".repeat(32), nodeId: "task_over" } }];
    const html = renderToStaticMarkup(createElement(ExecutionObservations, { model: model(items), compact: true,
      cards: [{ id: "node", name: "První karta" }, { id: "task_unknown", name: "Druhá karta" }, { id: "task_over", name: "Třetí karta" }], onViewAll() {} }));
    expect(html).toContain("3 načteno");
    expect(html).toContain("Překročený rozpočet: 1 · nedoložená spotřeba: 1");
    expect(html).toContain("První karta");
    expect(html).toContain("1,87 USD podle ceníku");
    expect(html).toContain("Překročen ceníkový rozpočet");
    expect(html).toContain("Druhá karta");
    expect(html).toContain("Spotřeba nedoložena");
    expect(html).not.toContain("Třetí karta");
    expect(html.match(/<li>/g)).toHaveLength(2);
    expect(html).toContain("Všechny záznamy (3)");
  });
});
