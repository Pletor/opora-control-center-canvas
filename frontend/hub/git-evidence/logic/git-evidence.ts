export type GitEvidenceEvaluation = {
  codeReview: { status: "approved" | "changes_requested" | "unknown"; reviewIds: number[] };
  planReview: { status: "approved" | "changes_requested" | "unknown"; reviewIds: number[] };
  checks: { status: "passed" | "failed" | "pending" | "unknown"; observedCount?: number; policyVerified: false; scope: "observed-only" };
  freshness: { status: "stale" | "matches-observed-context" | "unknown"; observedAt: string; remoteFreshness: "historical-observation" };
  blockers: string[];
};
export type GitEvidenceSnapshot = {
  id: string; project: string; workspace: string; acceptedRevision: string; observedAt: string; complete: boolean;
  configuredRepository: string;
  repository?: { id?: number; fullName: string } | null;
  pr?: { id: number; number: number; headSha: string; state: string; draft: boolean; baseRef: string } | null;
  prNumber?: number; errorCode?: string;
  counts?: { reviews: number; checks: number; statuses: number };
  checks?: { id: number; appId: number; name: string; headSha: string; status: string; conclusion: string | null }[];
  statuses?: { id: number; context: string; sha: string; state: string }[];
};
export type GitEvidenceItem = { snapshot: GitEvidenceSnapshot; evaluation: GitEvidenceEvaluation };
export type GitEvidenceContext = {
  acceptedHead: string | null; repository: string | null; available: boolean; unavailableReason: string; items: GitEvidenceItem[];
};

export class EvidenceRequests {
  private generation = 0;
  next() { const captured = ++this.generation; return () => captured === this.generation; }
  invalidate() { this.generation++; }
}

export function evidencePayload(project: string, workspace: string, acceptedHead: string | null, input: string) {
  if (!acceptedHead || !/^[a-f0-9]{40}$/.test(acceptedHead)) throw new Error("Nejprve přijměte výchozí zadání.");
  if (!/^[1-9][0-9]*$/.test(input.trim()) || !Number.isSafeInteger(Number(input))) throw new Error("Zadejte kladné celé číslo PR.");
  return { project, workspace, expectedAcceptedHead: acceptedHead, prNumber: Number(input) };
}

export function pullRequestLink(repository: string | null | undefined, number: number | undefined) {
  if (!repository || !/^[A-Za-z0-9-]+\/[A-Za-z0-9_-][A-Za-z0-9._-]*$/.test(repository)
    || repository.includes("..") || !number || !Number.isSafeInteger(number) || number < 1) return null;
  return `https://github.com/${repository}/pull/${number}`;
}

export function planReviewMarker(project: string, workspace: string, revision: string) {
  return `Opora-Plan: ${project}/${workspace}@${revision}`;
}

const reasons: Record<string, string> = {
  "stale-revision-or-head": "Pozorování patří starší přijaté revizi nebo jinému poslednímu známému SHA.",
  "incomplete-or-invalid-observation": "Pozorování není úplné nebo neprošlo ověřením dat.",
  "invalid-review-evidence": "Identitu, oprávnění nebo údaje review se nepodařilo ověřit.",
  "independent-code-review-missing-or-blocked": "Chybí platné nezávislé schválení kódu nebo reviewer požaduje změny.",
  "revision-bound-plan-review-missing-or-blocked": "Chybí schválení s přesnou značkou této revize zadání nebo reviewer požaduje změny.",
  "required-checks-and-trusted-provider-policy-not-configured": "Politika povinných kontrol a důvěryhodných poskytovatelů zatím není nastavena.",
};
export function evidenceReason(code: string) { return reasons[code] ?? "Tento podklad zatím nelze považovat za ověřený."; }
export const reviewLabels = { approved: "Schválení doloženo", changes_requested: "Požadovány změny", unknown: "Schválení nedoloženo" };
export const checkLabels = { passed: "Pozorované kontroly prošly", failed: "Pozorované kontroly selhaly", pending: "Kontroly probíhají", unknown: "Výsledek kontrol není doložen" };
