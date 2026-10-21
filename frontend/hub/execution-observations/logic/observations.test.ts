import { describe, expect, it } from "vitest";
import { formatUsdCents, ObservationRequests, observationStatus, parseObservationSnapshot, readObservations, type ReadApi } from "./observations";

const id40 = "a".repeat(40), id64 = "b".repeat(64), now = "2026-10-21T10:00:00Z";
const intent: Record<string, unknown> = { project: "project", workspace: "workspace", requestId: "request_1", executionId: "c".repeat(32), nodeId: "_card", epoch: 1,
  acceptedRevision: id40, assignmentDigest: id64, contextProtocolVersion: 2, contextVersion: id64, executionProtocolVersion: 2,
  budget: { policyHead: id40, familyId: "d".repeat(40), allocationId: "e".repeat(40), attempt: 1, repairRound: 0, kind: "initial", admittedAt: 100, runDeadlineAt: 130, maxRunSeconds: 30 },
  authorityDeadlineAt: 130, provider: "anthropic-managed-agents", repository: { url: "https://github.com/team/project", commitSha: id40 }, agentId: "agent", agentVersion: 1,
  environmentId: "env", environmentDigest: id64, configurationDigest: id64, maxListCostCents: "900719925474099312" };
const envelope = (id: string, kind: string): Record<string, unknown> => ({ id, schemaVersion: 1, kind, observerId: "observer", createdAt: now, requestDigest: id64, executionBinding: "canvas-verified", providerBinding: "observer-attested" });
const bound: Record<string, unknown> = { ...intent, ...envelope(id40, "execution-intent") };
const observation: Record<string, unknown> = { project: "project", workspace: "workspace", intentId: id40, requestId: "observe_1", expectedObservationHead: null, sequence: 1,
  sessionId: "session:1", observedAt: now, source: "provider-api", status: "idle", providerStatus: "idle",
  cumulative: { inputTokens: 2, outputTokens: 3, cacheReadInputTokens: 4, cacheCreation5mTokens: 5, cacheCreation1hTokens: 6, listCostCents: "900719925474099313", currency: "USD", activeSeconds: 1.25 },
  ...envelope("f".repeat(40), "execution-observation") };
const snapshot = (records: unknown[] = [{ intent: bound, observation, listBudgetExceeded: true }]) => ({ items: records, readOnly: false, observerConfigured: true, providerAccessVerified: false, usageBasis: "observer-attested-provider-list-cost-not-invoice" });

describe("isolated execution observation read boundary", () => {
  it("accepts immutable scoped v2 records and preserves fractional usage and exact high-value cents", () => {
    const value = parseObservationSnapshot(snapshot(), "project", "workspace");
    expect(value.items[0].observation?.cumulative.activeSeconds).toBe(1.25);
    expect(value.items[0].listBudgetExceeded).toBe(true);
    expect(formatUsdCents("900719925474099313")).toBe("9 007 199 254 740 993,13 USD");
    expect(observationStatus(value.items[0])).toContain("ne\u010dinn\u00fd stav");
    expect(value.providerAccessVerified).toBe(false);
  });

  it("accepts the native 80-character node identifier and derives idle from provider status", () => {
    const longNodeIntent = { ...bound, nodeId: "-" + "n".repeat(79) };
    const value = parseObservationSnapshot(snapshot([{ intent: longNodeIntent, observation: { ...observation, status: "running", providerStatus: "idle" }, listBudgetExceeded: true }]), "project", "workspace");
    expect(value.items[0].intent.nodeId).toHaveLength(80);
    expect(observationStatus(value.items[0])).toContain("ne\u010dinn\u00fd stav");
    expect(observationStatus(value.items[0])).toContain("ne\u010dinn\u00fd stav");
  });

  it("keeps null-session zero sentinels undocumented rather than implying free provider usage", () => {
    const sentinel = { ...observation, sessionId: null, providerStatus: null, status: "creation_unknown",
      cumulative: { inputTokens: 0, outputTokens: 0, cacheReadInputTokens: 0, cacheCreation5mTokens: 0, cacheCreation1hTokens: 0, listCostCents: "0", currency: "USD", activeSeconds: 0 } };
    const item = parseObservationSnapshot(snapshot([{ intent: bound, observation: sentinel, listBudgetExceeded: false }]), "project", "workspace").items[0];
    expect(observationStatus(item)).toContain("relace");
  });

  it("distinguishes absent observation and refuses a false budget-overrun flag", () => {
    const item = parseObservationSnapshot(snapshot([{ intent: bound, observation: null, listBudgetExceeded: false }]), "project", "workspace").items[0];
    expect(observationStatus(item)).toContain("Zat\u00edm bez pozorov\u00e1n\u00ed");
    expect(() => parseObservationSnapshot(snapshot([{ intent: bound, observation, listBudgetExceeded: false }]), "project", "workspace")).toThrow();
  });

  it("rejects scope drift, secret/unknown fields, bad status bindings, duplicate IDs and unbounded lists", () => {
    expect(() => parseObservationSnapshot(snapshot(), "other", "workspace")).toThrow();
    expect(() => parseObservationSnapshot({ ...snapshot(), providerKey: "secret" }, "project", "workspace")).toThrow();
    expect(() => parseObservationSnapshot(snapshot([{ intent: { ...bound, leaseToken: "private" }, observation, listBudgetExceeded: true }]), "project", "workspace")).toThrow();
    expect(() => parseObservationSnapshot(snapshot([{ intent: bound, observation: { ...observation, status: "terminated" }, listBudgetExceeded: true }]), "project", "workspace")).toThrow();
    expect(() => parseObservationSnapshot(snapshot([{ intent: bound, observation, listBudgetExceeded: true }, { intent: bound, observation, listBudgetExceeded: true }]), "project", "workspace")).toThrow();
    expect(() => parseObservationSnapshot({ ...snapshot(), items: Array(101).fill({ intent: bound, observation, listBudgetExceeded: true }) }, "project", "workspace")).toThrow();
  });

  it("reads through the identified UI session and explicit scoped GET, with no worker credentials", async () => {
    const urls: string[] = [];
    const read = (async (url: string) => {
      urls.push(url);
      if (!url.includes("execution-observers")) return {};
      const query = new URLSearchParams(url.split("?")[1]);
      return snapshot([{ intent: { ...bound, project: query.get("project")!, workspace: query.get("workspace")! },
        observation: { ...observation, project: query.get("project")!, workspace: query.get("workspace")! }, listBudgetExceeded: true }]);
    }) as ReadApi;
    await readObservations(read, "project / one", "workspace&two");
    expect(urls).toEqual(["/api/access/ui-session", "/api/oporahub/execution-observers?project=project+%2F+one&workspace=workspace%26two&limit=100"]);
  });

  it("invalidates late scope/generation responses and unmounted reads", () => {
    const requests = new ObservationRequests(), oldScope = requests.next();
    requests.invalidate();
    const currentGeneration = requests.next();
    expect(oldScope()).toBe(false);
    expect(currentGeneration()).toBe(true);
    requests.invalidate();
    expect(currentGeneration()).toBe(false);
  });
});
