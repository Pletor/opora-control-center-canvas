import type { DetailTarget } from "@/hub/oporahub-overview/logic/overview";

export const PROCESS_STATES = ["needs-plan", "needs-acceptance", "needs-routing", "ready", "running", "reported", "stale", "closed", "blocked", "unavailable"] as const;
export type ProcessStatus = typeof PROCESS_STATES[number];
export type ProcessCard = {
  nodeId: string; name: string; status: ProcessStatus; openIdeas: number;
  nextAction: { kind: string; label: string; reason: string };
  pipeline: { stageCount: number; passedCount: number; failedCount: number; currentStage: string | null };
  workingMatchesAccepted: boolean; doneConfirmed: boolean;
  currentExecution: null | { id: string; state: string; acceptedRevision: string; matchesCurrentRevision: boolean; results: number };
  executionAvailability: { available: boolean; unavailableReason: string | null };
  links: { context: string; claim: string; results: string | null; proposalContext: string; brief: string };
};
export type ProcessSnapshot = {
  schema: "opora.process-sync/1"; project: string; workspace: string; acceptedRevision: string | null;
  observedAt: string; cardLimit: number; totalCards: number; truncated: boolean; items: ProcessCard[];
  githubTracking: { scope: "workspace"; limit: number; truncated: boolean; items: {
    bindingId: string; acceptedRevision: string; matchesCurrentRevision: boolean; enabled: boolean;
    jobStatus: string | null; lastObservationId: string | null; reviewStatus: string | null; observedPrState: string | null;
  }[]; reviews: { evidenceId: string; acceptedRevision: string; matchesCurrentRevision: boolean;
    codeReview: string; planReview: string; freshness: string }[] };
};
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);
const text = (value: unknown): value is string => typeof value === "string" && value.length <= 16000;
const nullable = (value: unknown) => value === null || text(value);
const count = (value: unknown) => Number.isSafeInteger(value) && Number(value) >= 0;
const hash = (value: unknown) => typeof value === "string" && /^[a-f0-9]{40}$/.test(value);
const link = (value: unknown) => text(value) && value.startsWith("/api/") && !/[\r\n]/.test(value);
function validCard(value: unknown): value is ProcessCard {
  if (!object(value) || !text(value.nodeId) || !text(value.name) || !PROCESS_STATES.includes(value.status as ProcessStatus)
    || !count(value.openIdeas) || typeof value.workingMatchesAccepted !== "boolean" || typeof value.doneConfirmed !== "boolean") return false;
  const { nextAction: action, pipeline, currentExecution: execution, executionAvailability: available, links } = value;
  if (!object(action) || !text(action.kind) || !text(action.label) || !text(action.reason) || !object(pipeline)
    || ![pipeline.stageCount, pipeline.passedCount, pipeline.failedCount].every(count) || !nullable(pipeline.currentStage)
    || !object(available) || typeof available.available !== "boolean" || !nullable(available.unavailableReason)
    || !object(links) || ![links.context, links.claim, links.proposalContext, links.brief].every(link)
    || !(links.results === null || link(links.results))) return false;
  return execution === null || (object(execution) && typeof execution.id === "string" && /^[a-f0-9]{32}$/.test(execution.id)
    && text(execution.state) && hash(execution.acceptedRevision) && typeof execution.matchesCurrentRevision === "boolean" && count(execution.results));
}
export function parseProcess(value: unknown, project: string, workspace: string): ProcessSnapshot {
  const invalid = () => { throw new Error("Proces vrátil neplatná data nebo jiný pracovní prostor."); };
  if (!object(value) || value.schema !== "opora.process-sync/1" || value.project !== project || value.workspace !== workspace
    || !(value.acceptedRevision === null || hash(value.acceptedRevision)) || !text(value.observedAt) || !Number.isFinite(Date.parse(value.observedAt))
    || value.cardLimit !== 100 || !count(value.totalCards) || typeof value.truncated !== "boolean"
    || !Array.isArray(value.items) || value.items.length > 100 || !value.items.every(validCard)
    || new Set(value.items.map(item => item.nodeId)).size !== value.items.length) return invalid();
  const tracking = value.githubTracking;
  if (!object(tracking) || tracking.scope !== "workspace" || tracking.limit !== 100 || typeof tracking.truncated !== "boolean"
    || !Array.isArray(tracking.items) || tracking.items.length > 100 || !tracking.items.every(item => object(item)
      && hash(item.bindingId) && hash(item.acceptedRevision) && typeof item.matchesCurrentRevision === "boolean"
      && typeof item.enabled === "boolean" && nullable(item.jobStatus) && nullable(item.lastObservationId) && nullable(item.reviewStatus)
      && nullable(item.observedPrState)) || !Array.isArray(tracking.reviews) || tracking.reviews.length > 100
    || !tracking.reviews.every(item => object(item) && hash(item.evidenceId) && hash(item.acceptedRevision)
      && typeof item.matchesCurrentRevision === "boolean" && text(item.codeReview) && text(item.planReview) && text(item.freshness))) return invalid();
  return value as ProcessSnapshot;
}
export const processEndpoint = (project: string, workspace: string) => "/api/oporahub/process?" + new URLSearchParams({ project, workspace });
const labels: Record<ProcessStatus, string> = {
  "needs-plan": "Chybí přijatý plán", "needs-acceptance": "Zadání čeká na přijetí", "needs-routing": "Chybí směrování",
  ready: "Připraveno k převzetí", running: "Evidovaný běh · ověřit oprávnění", reported: "Nahlášeno · vyžaduje kontrolu",
  stale: "Historický běh · jiná revize", closed: "Lidsky dokončeno", blocked: "Blokováno", unavailable: "Podklady nedostupné",
};
export function processPresentation(card: ProcessCard): { label: string; tone: string; target: DetailTarget } {
  const kind = card.status === "needs-plan" || card.status === "needs-routing" ? "graph"
    : card.status === "needs-acceptance" ? "changes" : card.status === "closed" ? "tracking" : "executions";
  return { label: labels[card.status], tone: card.status === "reported" || card.status === "ready" ? "attention"
    : card.status === "stale" || card.status === "blocked" || card.status === "unavailable" ? "warning" : "neutral",
  target: { kind, title: `${card.name} · ${card.nodeId}`, ...(kind === "executions" && card.currentExecution ? { id: card.currentExecution.id } : {}) } };
}
export function proposeProcessImprovement(nodeId: string, name: string, selectDocument: (nodeId: string) => void,
  open: (target: DetailTarget) => void) {
  selectDocument(nodeId);
  open({ kind: "changes", title: `Navrhnout zlepšení · ${name} · ${nodeId}` });
}
