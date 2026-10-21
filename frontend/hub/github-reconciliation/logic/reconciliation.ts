export type ReconciliationBinding = { id: string; schemaVersion: 1; project: string; workspace: string; acceptedRevision: string;
  identityEvidenceId: string; repository: { id: number; fullName: string; baseBranch: string }; pr: { id: number; number: number; headRepoId: number };
  enrolledHeadSha: string; intervalSeconds: number; by: { kind: string; name: string }; createdAt: string };
export type ReconciliationControl = { id: string; bindingId: string; parentControlId: string | null; generation: number;
  action: "enroll" | "pause" | "resume" | "retry" | "system-pause"; enabled: boolean; requestId: string | null; by: { kind: string; name: string }; createdAt: string };
export type ReconciliationJob = { state: "scheduled" | "checking" | "retrying" | "paused" | "reconciled";
  bindingId: string; generation: number; nextAttemptAt: string | null; leaseUntil: string | null; consecutiveFailures: number;
  lastErrorCode: string | null; providerRetryUntil?: string | null; lastAttemptId: string | null; lastObservationId: string | null; lastEventId: string | null };
export type ReconciliationAttempt = { id: string; state: "pending" | "complete" | "failed" | "interrupted"; startedAt: string;
  finishedAt: string | null; errorCode: string | null; observationId: string | null };
export type PrObservation = { id: string; bindingId: string; createdAt: string; data: { complete: true; observedFrom: string; observedUntil: string;
  repository: { id: number; fullName: string }; pr: { id: number; number: number; baseRef: string; headSha: string; headRepoId: number | null;
    state: "open" | "closed-unmerged" | "merged"; draft: boolean; merged: boolean; mergedAt: string | null; mergeCommitSha: string | null } } };
export type ReconciliationItem = { binding: ReconciliationBinding; control: ReconciliationControl; job: ReconciliationJob;
  latestAttempt: ReconciliationAttempt | null; lastSuccessfulObservation: PrObservation | null;
  revisionRelation: { boundAcceptedRevision: string; currentAcceptedRevision: string | null; matchesCurrentAcceptedRevision: boolean } };
export type ReconciliationContext = { project: string; workspace: string; currentAcceptedHead: string | null; canConfigure: boolean;
  canPause: boolean; automaticWorkerEnabled: boolean; automaticWorkerUnavailableReason?: string | null;
  unavailableReason: string | null; serverNow: string; items: ReconciliationItem[] };
export type ReconciliationCandidate = { project: string; workspace: string; currentAcceptedHead: string | null; canConfigure: boolean;
  unavailableReason: string | null; evidenceId: string; binding: ReconciliationBinding; existingEnabledBinding: ReconciliationBinding | null };
export type HistoryEntry = { kind: string; record: Record<string, unknown> };
export type ReconciliationHistory = { binding: ReconciliationBinding; items: HistoryEntry[]; nextCursor: string | null;
  attempts: ReconciliationAttempt[]; nextAttemptCursor: string | null };
export type ControlAction = "pause" | "resume" | "retry";
export const ROOT = "/api/oporahub/reconciliation";
export const jobLabels: Record<ReconciliationJob["state"], string> = { scheduled: "Naplánováno", checking: "Čte se GitHub", retrying: "Čeká na opakování",
  paused: "Pozastaveno", reconciled: "Sloučení zaznamenáno; pravidelné sledování skončilo" };
export const prLabels = { open: "PR otevřen", "closed-unmerged": "PR uzavřen bez sloučení", merged: "PR sloučen podle pozorování" };
export function reconciliationLink(binding: ReconciliationBinding) {
  const name = binding.repository.fullName, number = binding.pr.number;
  return /^[A-Za-z0-9-]+\/[A-Za-z0-9_-][A-Za-z0-9._-]*$/.test(name) && !name.includes("..") && Number.isSafeInteger(number) && number > 0
    ? `https://github.com/${name}/pull/${number}` : null;
}
export const displayTime = (value: string | null | undefined) => value && Number.isFinite(Date.parse(value)) ? new Date(value).toLocaleString("cs-CZ") : "Není doloženo";
/** An unchanged user intent retains its request ID across an uncertain response and explicit reread. */
export class ReconciliationIntents {
  private key = "";
  private id = "";
  constructor(private create: () => string = () => crypto.randomUUID()) {}
  request(action: string, payload: object) { const key = JSON.stringify([action, payload]); if (key !== this.key) { this.key = key; this.id = this.create(); } return this.id; }
}
export class ReconciliationRequests {
  private generation = 0;
  private writing = false;
  invalidate() { this.generation++; }
  next() { const ticket = ++this.generation; return () => ticket === this.generation; }
  beginWrite() { if (this.writing) return null; this.writing = true; return this.next(); }
  endWrite() { this.writing = false; }
  get busy() { return this.writing; }
}
export function enrollmentPayload(project: string, workspace: string, context: ReconciliationContext, candidate: ReconciliationCandidate) {
  if (!context.canConfigure || !candidate.canConfigure || candidate.project !== project || candidate.workspace !== workspace)
    throw new Error("Sledování může potvrdit pouze člověk v dostupném pracovním prostoru.");
  if (!context.currentAcceptedHead || candidate.currentAcceptedHead !== context.currentAcceptedHead || candidate.binding.acceptedRevision !== context.currentAcceptedHead)
    throw new Error("Vybrané pozorování nepatří aktuální přijaté revizi. Obnovte podklady.");
  if (candidate.existingEnabledBinding) throw new Error("Toto PR se již sleduje. Nejdříve výslovně pozastavte původní vazbu.");
  if (!/^[a-f0-9]{40}$/.test(candidate.evidenceId)) throw new Error("Chybí platná identita serverového pozorování.");
  return { project, workspace, expectedAcceptedHead: context.currentAcceptedHead, identityEvidenceId: candidate.evidenceId };
}
export function controlPayload(project: string, workspace: string, item: ReconciliationItem, action: ControlAction) {
  if (item.binding.project !== project || item.binding.workspace !== workspace || !Number.isSafeInteger(item.control.generation) || item.control.generation < 1)
    throw new Error("Vazba nebo její generace nepatří načtenému kontextu.");
  return { project, workspace, expectedGeneration: item.control.generation, action };
}
export function historyPage(previous: HistoryEntry[], page: ReconciliationHistory) {
  const seen = new Set(previous.map(item => `${item.kind}:${String(item.record.id)}`));
  return [...previous, ...page.items.filter(item => { const key = `${item.kind}:${String(item.record.id)}`; if (seen.has(key)) return false; seen.add(key); return true; })];
}
export type HistoryPages = Pick<ReconciliationHistory, "items" | "nextCursor" | "attempts" | "nextAttemptCursor">;
/** An exhausted stream must not restart when the other stream still has pages. */
export function advanceHistory(previous: HistoryPages, page: ReconciliationHistory): HistoryPages {
  return { items: previous.nextCursor ? historyPage(previous.items, page) : previous.items,
    nextCursor: previous.nextCursor ? page.nextCursor : null,
    attempts: previous.nextAttemptCursor ? [...new Map([...previous.attempts, ...page.attempts].map(item => [item.id, item])).values()] : previous.attempts,
    nextAttemptCursor: previous.nextAttemptCursor ? page.nextAttemptCursor : null };
}
