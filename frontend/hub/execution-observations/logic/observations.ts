export type Usage = { inputTokens: number; outputTokens: number; cacheReadInputTokens: number; cacheCreation5mTokens: number; cacheCreation1hTokens: number; listCostCents: string; currency: "USD"; activeSeconds: number };
export type ObserverIntent = { id: string; executionId: string; nodeId: string; epoch: number; acceptedRevision: string; provider: "anthropic-managed-agents"; repository: { url: string; commitSha: string }; agentId: string; agentVersion: number; environmentId: string; environmentDigest: string; configurationDigest: string; maxListCostCents: string; createdAt: string };
export type ObserverReadback = { id: string; intentId: string; requestId: string; sequence: number; sessionId: string | null; observedAt: string; source: "provider-api"; status: string; providerStatus: string | null; cumulative: Usage };
export type ObservationItem = { intent: ObserverIntent; observation: ObserverReadback | null; listBudgetExceeded: boolean };
export type ObservationSnapshot = { items: ObservationItem[]; readOnly: boolean; observerConfigured: boolean; providerAccessVerified: false; usageBasis: "observer-attested-provider-list-cost-not-invoice" };

const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
const keys = (v: Record<string, unknown>, expected: string[]) => Object.keys(v).length === expected.length && expected.every(k => Object.hasOwn(v, k));
const id = (v: unknown, pattern: RegExp) => typeof v === "string" && pattern.test(v);
const safeInt = (v: unknown): v is number => typeof v === "number" && Number.isSafeInteger(v) && v >= 0;
const stamp = (v: unknown) => typeof v === "string" && v.length <= 64 && Number.isFinite(Date.parse(v));
const hex40 = /^[a-f0-9]{40}$/; const hex64 = /^[a-f0-9]{64}$/;
const resourceId = /^[A-Za-z0-9_.:-]{1,160}$/;
const requestId = /^[A-Za-z0-9_-]{1,80}$/;
const budgetKeys = ["policyHead", "familyId", "allocationId", "attempt", "repairRound", "kind", "admittedAt", "runDeadlineAt", "maxRunSeconds"];
const intentBodyKeys = ["project", "workspace", "requestId", "executionId", "nodeId", "epoch", "acceptedRevision", "assignmentDigest", "contextProtocolVersion", "contextVersion", "executionProtocolVersion", "budget", "authorityDeadlineAt", "provider", "repository", "agentId", "agentVersion", "environmentId", "environmentDigest", "configurationDigest", "maxListCostCents"];
const metadataKeys = ["id", "schemaVersion", "kind", "observerId", "createdAt", "requestDigest", "executionBinding", "providerBinding"];
const countKeys = ["inputTokens", "outputTokens", "cacheReadInputTokens", "cacheCreation5mTokens", "cacheCreation1hTokens"];
const usageKeys = [...countKeys, "listCostCents", "currency", "activeSeconds"];
const observationBodyKeys = ["project", "workspace", "intentId", "requestId", "expectedObservationHead", "sequence", "sessionId", "observedAt", "source", "status", "providerStatus", "cumulative"];

function scope(v: Record<string, unknown>, project: string, workspace: string) { return v.project === project && v.workspace === workspace; }
function envelope(value: unknown, kind: string): value is Record<string, unknown> {
  if (!object(value) || !metadataKeys.every(k => Object.hasOwn(value, k)) || value.schemaVersion !== 1 || value.kind !== kind || value.executionBinding !== "canvas-verified" || value.providerBinding !== "observer-attested") return false;
  return id(value.id, hex40) && id(value.observerId, resourceId) && id(value.requestDigest, hex64) && stamp(value.createdAt);
}
function budget(value: unknown): boolean {
  if (!object(value) || !keys(value, budgetKeys) || !id(value.policyHead, hex40) || !id(value.familyId, hex40) || !id(value.allocationId, hex40)) return false;
  const { attempt, repairRound, admittedAt, runDeadlineAt, maxRunSeconds, kind } = value;
  if (!(safeInt(attempt) && attempt > 0 && safeInt(repairRound) && repairRound < attempt
    && ["initial", "retry", "repair"].includes(String(kind)) && typeof admittedAt === "number" && Number.isFinite(admittedAt) && admittedAt >= 0
    && typeof runDeadlineAt === "number" && Number.isFinite(runDeadlineAt) && safeInt(maxRunSeconds) && maxRunSeconds >= 30 && maxRunSeconds <= 86400
    && runDeadlineAt === admittedAt + maxRunSeconds)) return false;
  return kind === "initial" ? attempt === 1 && repairRound === 0
    : kind === "retry" ? attempt > 1 && repairRound === 0 : repairRound > 0;
}
function intent(value: unknown, project: string, workspace: string): value is ObserverIntent {
  if (!envelope(value, "execution-intent") || !scope(value, project, workspace) || !keys(value, [...metadataKeys, ...intentBodyKeys])) return false;
  if (!id(value.executionId, /^[a-f0-9]{32}$/) || !id(value.nodeId, /^[A-Za-z0-9_-]{1,80}$/) || !safeInt(value.epoch) || value.epoch === 0
    || !id(value.acceptedRevision, hex40) || !id(value.assignmentDigest, hex64) || ![1, 2].includes(Number(value.contextProtocolVersion))
    || !id(value.contextVersion, hex64) || value.executionProtocolVersion !== 2 || !budget(value.budget) || typeof value.authorityDeadlineAt !== "number"
    || value.authorityDeadlineAt !== (value.budget as Record<string, unknown>).runDeadlineAt || value.provider !== "anthropic-managed-agents") return false;
  if (!object(value.repository) || !keys(value.repository, ["url", "commitSha"]) || typeof value.repository.url !== "string"
    || !/^https:\/\/github\.com\/[A-Za-z0-9_-]+\/[A-Za-z0-9_.-]+$/.test(value.repository.url) || value.repository.url.includes("..") || !id(value.repository.commitSha, hex40)) return false;
  return id(value.agentId, resourceId) && safeInt(value.agentVersion) && value.agentVersion > 0 && id(value.environmentId, resourceId)
    && id(value.environmentDigest, hex64) && id(value.configurationDigest, hex64) && id(value.maxListCostCents, /^(0|[1-9][0-9]{0,17})$/)
    && value.maxListCostCents !== "0" && id(value.requestId, requestId);
}
function usage(value: unknown): value is Usage {
  if (!object(value) || !keys(value, usageKeys) || !countKeys.every(key => safeInt(value[key]))) return false;
  return id(value.listCostCents, /^(0|[1-9][0-9]{0,17})$/) && value.currency === "USD" && typeof value.activeSeconds === "number" && Number.isFinite(value.activeSeconds) && value.activeSeconds >= 0 && value.activeSeconds <= Number.MAX_SAFE_INTEGER;
}
function observation(value: unknown, expected: ObserverIntent, project: string, workspace: string): value is ObserverReadback {
  if (!envelope(value, "execution-observation") || !scope(value, project, workspace) || !keys(value, [...metadataKeys, ...observationBodyKeys])) return false;
  if (value.intentId !== expected.id || !id(value.requestId, requestId) || !(value.expectedObservationHead === null || id(value.expectedObservationHead, hex40))
    || !safeInt(value.sequence) || value.sequence === 0 || !(value.sessionId === null || id(value.sessionId, resourceId)) || !stamp(value.observedAt)
    || value.source !== "provider-api" || !["creating", "creation_unknown", "running", "idle", "termination_pending", "terminated", "failed", "unknown"].includes(String(value.status))
    || !(value.providerStatus === null || ["idle", "running", "rescheduling", "terminated"].includes(String(value.providerStatus))) || !usage(value.cumulative)) return false;
  if ((value.status === "terminated") !== (value.providerStatus === "terminated")) return false;
  if (value.sessionId === null && (value.status !== "creating" && value.status !== "creation_unknown" && value.status !== "unknown")) return false;
  if (value.sessionId === null && (countKeys.some(key => value.cumulative && object(value.cumulative) && value.cumulative[key] !== 0)
    || !object(value.cumulative) || value.cumulative.listCostCents !== "0" || value.cumulative.activeSeconds !== 0 || value.providerStatus !== null)) return false;
  return true;
}

export function parseObservationSnapshot(value: unknown, project: string, workspace: string): ObservationSnapshot {
  if (!object(value) || !keys(value, ["items", "readOnly", "observerConfigured", "providerAccessVerified", "usageBasis"]) || !Array.isArray(value.items)
    || value.items.length > 100 || typeof value.readOnly !== "boolean" || typeof value.observerConfigured !== "boolean"
    || value.providerAccessVerified !== false || value.usageBasis !== "observer-attested-provider-list-cost-not-invoice") throw new Error("Pozorování běhů mají neplatný tvar.");
  if (JSON.stringify(value).length > 16 * 1024 * 1024) throw new Error("Historie pozorování překračuje velikostní limit.");
  const seen = new Set<string>();
  const seenExecutions = new Set<string>();
  const items = value.items.map((raw): ObservationItem => {
    if (!object(raw) || !keys(raw, ["intent", "observation", "listBudgetExceeded"]) || typeof raw.listBudgetExceeded !== "boolean" || !intent(raw.intent, project, workspace)) throw new Error("Záznam z jiného rozsahu nebo s neplatným obsahem byl odmítnut.");
    const record = raw.intent as ObserverIntent;
    if (seen.has(record.id) || seenExecutions.has(record.executionId) || (raw.observation !== null && !observation(raw.observation, record, project, workspace))) throw new Error("Pozorování neodpovídá svému běhu.");
    seen.add(record.id);
    seenExecutions.add(record.executionId);
    const readback = raw.observation as ObserverReadback | null;
    const exceeded = !!readback && BigInt(readback.cumulative.listCostCents) > BigInt(record.maxListCostCents);
    if (raw.listBudgetExceeded !== exceeded) throw new Error("Označení překročení limitu neodpovídá doložené spotřebě.");
    return { intent: record, observation: readback, listBudgetExceeded: exceeded };
  });
  return { items, readOnly: value.readOnly, observerConfigured: value.observerConfigured, providerAccessVerified: false, usageBasis: "observer-attested-provider-list-cost-not-invoice" };
}

export type ReadApi = <T>(url: string) => Promise<T>;
export async function readObservations(read: ReadApi, project: string, workspace: string) {
  if (!project || project.length > 80 || !workspace || workspace.length > 80) throw new Error("Projekt a prostor musí být vybrány.");
  await read("/api/access/ui-session");
  const query = new URLSearchParams({ project, workspace, limit: "100" });
  return parseObservationSnapshot(await read<unknown>(`/api/oporahub/execution-observers?${query}`), project, workspace);
}

export class ObservationRequests {
  private version = 0;
  next() { const version = ++this.version; return () => version === this.version; }
  invalidate() { this.version++; }
}

export function observationStatus(item: ObservationItem): string {
  const state = item.observation?.status;
  if (state === "termination_pending") return "Ukon\u010den\u00ed \u010dek\u00e1 na pozorov\u00e1n\u00ed poskytovatele";
  if (state === "creating" || state === "creation_unknown") return "Vytvo\u0159en\u00ed relace nen\u00ed potvrzeno";
  if (state === "unknown") return "Stav poskytovatele nen\u00ed zn\u00e1m";
  if (item.observation?.providerStatus === "terminated") return "Poskytovatel potvrdil ukon\u010den\u00ed";
  if (item.observation?.providerStatus === "idle") return "Poskytovatel hl\u00e1s\u00ed ne\u010dinn\u00fd stav; b\u011bh nen\u00ed potvrzen jako ukon\u010den\u00fd";
  if (item.observation?.providerStatus === "running") return "Poskytovatel hl\u00e1s\u00ed b\u011bh; opr\u00e1vn\u011bn\u00ed se zde nevyhodnocuje";
  if (item.observation?.providerStatus === "rescheduling") return "Poskytovatel hl\u00e1s\u00ed p\u0159esun relace";
  if (state === "failed") return "Pozorovatel hl\u00e1s\u00ed chybu";
  return "Zat\u00edm bez pozorov\u00e1n\u00ed poskytovatele";
}

export function hasProviderUsage(item: ObservationItem): boolean {
  return item.observation !== null && item.observation.sessionId !== null && item.observation.providerStatus !== null;
}

export function formatUsdCents(cents: string): string {
  if (!/^(0|[1-9][0-9]{0,17})$/.test(cents)) return "Částka není dostupná";
  const value = BigInt(cents);
  const whole = new Intl.NumberFormat("cs-CZ").format(value / 100n);
  return `${whole},${String(value % 100n).padStart(2, "0")} USD`;
}

export function observedAt(value: string | undefined): string {
  if (!value || !stamp(value)) return "Čas pozorování není dostupný";
  return new Date(value).toLocaleString("cs-CZ");
}
