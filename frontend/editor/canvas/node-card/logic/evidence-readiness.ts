// Zrcadlo `evidence_ready` z backend/editor/agent_memory/completion_evidence.py: jen říká, co ještě chybí,
// aby člověk nemačkal „Potvrdit“ naslepo. Rozhoduje dál server; důkazy jsou deklarované, nikdo je neověřuje.
import type { CompletionEvidence } from "../components/CardEvidence";

export type EvidencePart = "tests" | "review" | "merge" | "checksRun";
export type EvidenceReadiness = { ready: boolean; missing: EvidencePart[]; notApplicable: ("tests" | "review" | "merge")[] };
const KINDS = ["tests", "review", "merge"] as const;

/** `[task]` karta nebo karta s předepsanými kontrolami staví kód: testy a merge nejsou N/A. */
export function needsRealTests(node?: { name?: string; checks?: unknown[] } | null): boolean {
  return !!node && (!!node.checks?.length || (node.name ?? "").startsWith("[task] "));
}

export function evidenceReadiness(evidence: CompletionEvidence | undefined,
  node?: { name?: string; checks?: unknown[] } | null): EvidenceReadiness {
  if (!evidence) return { ready: false, missing: [...KINDS, "checksRun"], notApplicable: [] };
  const strict = needsRealTests(node);
  const missing: EvidencePart[] = [];
  for (const kind of KINDS) {
    const status = evidence[kind]?.status;
    const naForbidden = strict && status === "not_applicable" && kind !== "review";
    if ((status !== "passed" && status !== "not_applicable") || naForbidden) missing.push(kind);
  }
  const runs = evidence.checksRun ?? [];
  if (evidence.tests?.status === "passed" && !evidence.tests.url && !runs.length && !missing.includes("tests")) missing.push("tests");
  if (runs.some(run => run.exitCode !== 0) || (!runs.length && evidence.tests?.status !== "not_applicable")) missing.push("checksRun");
  const notApplicable = KINDS.filter(kind => evidence[kind]?.status === "not_applicable");
  return { ready: !missing.length, missing, notApplicable };
}

/** Hromadně jde potvrdit jen karta s hotovými důkazy bez N/A; ostatní potvrzuje člověk jednotlivě. */
export const batchConfirmable = (readiness: EvidenceReadiness) => readiness.ready && !readiness.notApplicable.length;

export const missingLabel = (readiness: EvidenceReadiness) => `chybí důkazy: ${readiness.missing.join(", ")}`;
