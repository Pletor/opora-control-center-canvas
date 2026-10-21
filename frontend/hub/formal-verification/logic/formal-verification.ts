export type FormalArtifact = { path: string; role: string; sha256: string; bytes: number; available?: boolean };
export type FormalClaim = { id: string; kind: "invariant" | "temporal-property" | "theorem"; statement: string; statementDigest: string };
export type FormalOutcome = "passed" | "counterexample" | "failed" | "inconclusive" | "cancelled";
export type FormalReport = { requestId: string; reportDigest: string; outcome: FormalOutcome; checkedClaims: string[];
  summary: string; artifacts: FormalArtifact[]; createdAt: string; trust: "agent-reported";
  sourceBinding: "agent-reported"; currentEligibility: false; independentlyVerified: false };
export type FormalRecord = { id: string; project: string; workspace: string; nodeId: string; executionId: string; epoch: number;
  acceptedRevision: string; assignmentDigest: string; requestId: string; requestDigest: string; manifestDigest: string;
  verification: { tool: { name: "tlc" | "lean"; version: string; distributionSha256: string };
    source: { repository: string; commitSha: string }; claims: FormalClaim[]; assumptions: string[];
    configuration: Record<string, unknown>; artifacts: FormalArtifact[] };
  createdAt: string; trust: "agent-reported"; sourceBinding: "agent-reported"; currentEligibility: false;
  independentlyVerified: false; report: FormalReport | null };
export type FormalScope = { project: string; workspace: string };
export const FORMAL_ROOT = "/api/oporahub/verifications";
export const formalOutcomes: Record<FormalOutcome, string> = { passed: "Nahlášeno: prošlo · neověřeno", counterexample: "Nahlášen protipříklad",
  failed: "Nahlášeno selhání", inconclusive: "Nahlášeno bez rozhodnutí", cancelled: "Nahlášeno zrušení" };
export function formalOutcome(record: FormalRecord) { return record.report ? formalOutcomes[record.report.outcome] : "Výsledek zatím nenahlášen"; }
export function formalRevision(record: FormalRecord, currentAcceptedHead: string | null) {
  return !currentAcceptedHead ? "Aktuální přijatá revize není doložena; stáří vazby není známé."
    : currentAcceptedHead === record.acceptedRevision ? "Vazba odpovídá načtené přijaté revizi; nezávislé ověření není doloženo."
    : "Historický podklad · přijatá revize se změnila.";
}
export function formalQuery(scope: FormalScope) { return new URLSearchParams(scope).toString(); }
export function formalDetailUrl(scope: FormalScope, id: string) {
  if (!/^[a-f0-9]{32}$/.test(id)) throw new Error("Neplatné ID formálního požadavku.");
  return `${FORMAL_ROOT}/${id}?${formalQuery(scope)}`;
}
export function formalArtifactUrl(scope: FormalScope, id: string, sha256: string) {
  formalDetailUrl(scope, id);
  if (!/^[a-f0-9]{64}$/.test(sha256)) throw new Error("Neplatný otisk souboru.");
  return `${FORMAL_ROOT}/${id}/artifacts/${sha256}?${formalQuery(scope)}`;
}
export function formalSourceUrl(repository: string, commitSha: string) {
  if (!/^[A-Za-z0-9_.-]{1,100}\/[A-Za-z0-9_.-]{1,100}$/.test(repository) || repository.split("/").some(part => part === "." || part === "..") || !/^[a-f0-9]{40}$/.test(commitSha)) return null;
  return `https://github.com/${repository}/commit/${commitSha}`;
}

/** Each scope/selection/refresh invalidates even requests whose effect cleanup has not run yet. */
export class FormalReads {
  private key = "";
  private generation = 0;
  context(key: string) { if (key !== this.key) { this.key = key; this.generation++; } }
  next() { const version = ++this.generation; return () => version === this.generation; }
  invalidate() { this.generation++; }
}
