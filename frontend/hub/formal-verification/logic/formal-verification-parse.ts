import { formalSourceUrl, type FormalArtifact, type FormalClaim, type FormalRecord, type FormalReport, type FormalScope, type FormalTrust } from "./formal-verification";

type ObjectValue = Record<string, unknown>;
const reject = (): never => { throw new Error("Formální podklad má neplatný obsah nebo hranici důvěry."); };
const object = (value: unknown): ObjectValue => value && typeof value === "object" && !Array.isArray(value) ? value as ObjectValue : reject();
const text = (value: unknown) => typeof value === "string" && value.trim() && value.length <= 4000 && !value.includes("\0") ? value : reject();
const pattern = (value: unknown, expression: RegExp) => typeof value === "string" && expression.test(value) ? value : reject();
const hash = (value: unknown, size = 64) => pattern(value, new RegExp(`^[a-f0-9]{${size}}$`));
const identity = (value: unknown) => pattern(value, /^[A-Za-z0-9_.-]{1,80}$/);
const list = (value: unknown, limit = 32): unknown[] => Array.isArray(value) && value.length <= limit ? value : reject();
const time = (value: unknown) => typeof value === "string" && value.length <= 50 && /(?:Z|[+-]\d\d:\d\d)$/.test(value) && Number.isFinite(Date.parse(value)) ? value : reject();
/** `ci-verified` = run by the base-branch workflow on this head; never independent, never eligible. */
function trust(value: ObjectValue) {
  const level = value.trust;
  if ((level !== "agent-reported" && level !== "ci-verified") || value.sourceBinding !== level || value.currentEligibility !== false || value.independentlyVerified !== false) reject();
  return { trust: level as FormalTrust, sourceBinding: level as FormalTrust, currentEligibility: false as const, independentlyVerified: false as const };
}
function artifacts(value: unknown, roles: string[]): FormalArtifact[] {
  const paths = new Set<string>();
  return list(value).map(raw => {
    const item = object(raw), path = text(item.path), role = text(item.role);
    if (paths.has(path) || /[\\:\x00-\x1f]/.test(path) || path.split("/").some(part => !part || part === "." || part === "..")
      || !roles.includes(role) || !Number.isSafeInteger(item.bytes) || (item.bytes as number) < 0 || (item.bytes as number) > 2 * 1024 * 1024
      || !(item.available === undefined || typeof item.available === "boolean")) reject();
    paths.add(path);
    return { path, role, sha256: hash(item.sha256), bytes: item.bytes as number, ...(typeof item.available === "boolean" ? { available: item.available } : {}) };
  });
}
function configuration(value: unknown, depth = 0): unknown {
  if (depth > 8) return reject();
  if (value === null || typeof value === "boolean" || (typeof value === "number" && Number.isFinite(value))) return value;
  if (typeof value === "string") return text(value);
  if (Array.isArray(value)) return value.map(item => configuration(item, depth + 1));
  return Object.fromEntries(Object.entries(object(value)).map(([key, item]) => [text(key), configuration(item, depth + 1)]));
}
function report(raw: unknown, claims: FormalClaim[]): FormalReport | null {
  if (raw === null) return null;
  const value = object(raw), checkedClaims = list(value.checkedClaims).map(identity), outcome = text(value.outcome);
  if (!["passed", "counterexample", "failed", "inconclusive", "cancelled"].includes(outcome)
    || new Set(checkedClaims).size !== checkedClaims.length || checkedClaims.some(id => !claims.some(claim => claim.id === id))
    || (outcome === "passed" && checkedClaims.length !== claims.length)) reject();
  return { ...trust(value), requestId: identity(value.requestId), reportDigest: hash(value.reportDigest), outcome: outcome as FormalReport["outcome"],
    checkedClaims, summary: text(value.summary), artifacts: artifacts(value.artifacts, ["stdout", "stderr", "counterexample", "proof", "run-metadata"]), createdAt: time(value.createdAt) };
}
export function parseFormalRecord(raw: unknown, scope: FormalScope, requestedId?: string): FormalRecord {
  const value = object(raw), id = hash(value.id, 32), verification = object(value.verification), tool = object(verification.tool), source = object(verification.source);
  if (value.project !== scope.project || value.workspace !== scope.workspace || (requestedId && id !== requestedId)
    || !Number.isSafeInteger(value.epoch) || (value.epoch as number) < 1 || (tool.name !== "tlc" && tool.name !== "lean")) reject();
  const repository = text(source.repository), commitSha = hash(source.commitSha, 40);
  if (!formalSourceUrl(repository, commitSha)) reject();
  const claims = list(verification.claims).map(raw => {
    const claim = object(raw), kind = text(claim.kind);
    if (!(tool.name === "lean" ? ["theorem"] : ["invariant", "temporal-property"]).includes(kind)) reject();
    return { id: identity(claim.id), kind: kind as FormalClaim["kind"], statement: text(claim.statement), statementDigest: hash(claim.statementDigest) };
  });
  if (!claims.length || new Set(claims.map(claim => claim.id)).size !== claims.length) reject();
  const config = configuration(object(verification.configuration)) as Record<string, unknown>;
  if (new TextEncoder().encode(JSON.stringify(config)).length > 16 * 1024) reject();
  return { ...trust(value), id, project: scope.project, workspace: scope.workspace, nodeId: identity(value.nodeId), executionId: hash(value.executionId, 32),
    epoch: value.epoch as number, acceptedRevision: hash(value.acceptedRevision, 40), assignmentDigest: hash(value.assignmentDigest), requestId: identity(value.requestId),
    requestDigest: hash(value.requestDigest), manifestDigest: hash(value.manifestDigest), createdAt: time(value.createdAt), report: report(value.report, claims),
    verification: { tool: { name: tool.name as "tlc" | "lean", version: text(tool.version), distributionSha256: hash(tool.distributionSha256) }, source: { repository, commitSha },
      claims, assumptions: list(verification.assumptions).map(text), configuration: config,
      artifacts: artifacts(verification.artifacts, ["model", "configuration", "dependency", "proof", "source", "lockfile"]) } };
}
export function parseFormalHistory(raw: unknown, scope: FormalScope) {
  const requests = list(object(raw).requests, 100).map(item => parseFormalRecord(item, scope));
  if (new Set(requests.map(item => item.id)).size !== requests.length) reject();
  return requests;
}
