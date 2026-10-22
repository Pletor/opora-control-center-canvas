import { isCount, isObject, isText } from "@/hub/oporahub-mirror/logic/hub-read";

// Drátový tvar `GET /api/oporahub/review-jobs/gates` (docs/oporahub-review-jobs.md, „Brána merge“).
// Parser bere jen to, co krok Review promítá; neznámá pole snese, neplatné jádro brány vynechá.
export type GateStatus = "pending" | "blocked" | "ready";
export type GateHumans = { mode: string; count: number; identityIds: string[]; directorId: string | null; unverifiedApprovals: number };
export type GateSecurity = { reviewJobId: string | null; phase: string; reasons: string[]; openImportant: number };
export type GateSelfChecks = { status: string; source: string | null; missing: string[]; failed: string[]; invalid: number };
export type GateBase = { baseRef: string; baseSha: string; mergeBaseSha: string | null; behindBy: number | null; fresh: boolean };
export type MergeReadiness = {
  security?: GateSecurity | null; selfChecks?: GateSelfChecks; requiredChecks?: Record<string, string>;
  base?: GateBase | null; template?: { missing: string[] };
};
export type ReviewGate = {
  executionId: string; cardId: string; repository: string; number: number; headSha: string; prState: string;
  reviewJobId: string | null; round: number | null; riskTier: string | null; mergeReadiness: MergeReadiness;
  reviewGate: {
    status: GateStatus; openImportant: number; requiredHumanApprovals: number; humanApprovalsAtHead: number;
    reasons: string[]; humans?: GateHumans;
  };
};

const texts = (value: unknown): string[] => Array.isArray(value) ? value.filter(item => isText(item)) as string[] : [];
const num = (value: unknown) => isCount(value) ? value : 0;
const str = (value: unknown, fallback: string) => isText(value) ? value : fallback;
const opt = (value: unknown) => isText(value) ? value : null;

function readiness(ready: Record<string, unknown>): MergeReadiness {
  const merge: MergeReadiness = {};
  const sec = ready.security, checks = ready.selfChecks, base = ready.base, template = ready.template;
  if ("security" in ready) merge.security = isObject(sec) ? { reviewJobId: opt(sec.reviewJobId), phase: str(sec.phase, "?"),
    reasons: texts(sec.reasons), openImportant: num(sec.openImportant) } : null;
  if (isObject(checks)) merge.selfChecks = { status: str(checks.status, "?"), source: opt(checks.source),
    missing: texts(checks.missing), failed: texts(checks.failed), invalid: num(checks.invalid) };
  if (isObject(ready.requiredChecks))
    merge.requiredChecks = Object.fromEntries(Object.entries(ready.requiredChecks).filter(([, value]) => isText(value))) as Record<string, string>;
  if ("base" in ready) merge.base = isObject(base) ? { baseRef: str(base.baseRef, "?"), baseSha: str(base.baseSha, ""),
    mergeBaseSha: opt(base.mergeBaseSha), behindBy: isCount(base.behindBy) ? base.behindBy : null, fresh: base.fresh === true } : null;
  if (isObject(template)) merge.template = { missing: texts(template.missing) };
  return merge;
}

function gate(raw: unknown): ReviewGate | null {
  if (!isObject(raw) || !isText(raw.executionId) || !isText(raw.cardId) || !isText(raw.repository) || !isCount(raw.number)) return null;
  const rg = raw.reviewGate;
  if (!isObject(rg) || !["pending", "blocked", "ready"].includes(rg.status as string)) return null;
  const h = rg.humans;
  const humans = isObject(h) && isText(h.mode) ? { mode: h.mode, count: num(h.count), identityIds: texts(h.identityIds),
    directorId: opt(h.directorId), unverifiedApprovals: num(h.unverifiedApprovals) } : undefined;
  return {
    executionId: raw.executionId, cardId: raw.cardId, repository: raw.repository, number: raw.number,
    headSha: str(raw.headSha, ""), prState: str(raw.prState, "?"), reviewJobId: opt(raw.reviewJobId),
    round: isCount(raw.round) ? raw.round : null, riskTier: opt(raw.riskTier),
    mergeReadiness: readiness(isObject(raw.mergeReadiness) ? raw.mergeReadiness : {}),
    reviewGate: { status: rg.status as GateStatus, openImportant: num(rg.openImportant), requiredHumanApprovals: num(rg.requiredHumanApprovals),
      humanApprovalsAtHead: num(rg.humanApprovalsAtHead), reasons: texts(rg.reasons), ...(humans ? { humans } : {}) },
  };
}

export function parseGates(raw: unknown): ReviewGate[] {
  if (!isObject(raw) || !Array.isArray(raw.items)) throw new Error("Brány review mají neplatný tvar.");
  return raw.items.map(gate).filter((item): item is ReviewGate => item !== null);
}
export const gatesEndpoint = (project: string, workspace: string) =>
  `/api/oporahub/review-jobs/gates?${new URLSearchParams({ project, workspace })}`;

/** Brány karty: otevřené PR první, uvnitř nejnovější (vyšší číslo PR) první. */
export function cardGates(gates: ReviewGate[], nodeId: string) {
  return gates.filter(item => item.cardId === nodeId)
    .sort((a, b) => Number(b.prState === "open") - Number(a.prState === "open") || b.number - a.number);
}
