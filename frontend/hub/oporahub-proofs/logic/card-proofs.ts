import type { AgentAction } from "@/hub/oporahub-agent-state/logic/agent-state";
import { isObject, isText } from "@/hub/oporahub-mirror/logic/hub-read";

// Formální důkazy karty (docs/oporahub-verification.md): Lean, TLC a test shody (conformance).
// Ze záznamu `GET /api/oporahub/verifications?nodeId=` bereme jen to, co karta ukazuje; důvěru nikdy
// nezvyšujeme: `ci-verified` jen tehdy, když ji server výslovně uvádí.
export type ProofKind = "lean" | "tlc" | "conformance";
export type ProofTrust = "agent-reported" | "ci-verified";
export type ProofRecord = {
  id: string; nodeId: string; acceptedRevision: string; tool: string; checkName: string; commitSha: string;
  trust: ProofTrust; outcome: string | null; createdAt: string;
};
export const PROOF_KINDS: ProofKind[] = ["lean", "tlc", "conformance"];
const KIND_LABEL: Record<ProofKind, string> = { lean: "Lean · důkaz", tlc: "TLA+/TLC · model", conformance: "Shoda s implementací" };
export const TRUST_LABEL: Record<ProofTrust, string> = { "agent-reported": "nahlášeno agentem", "ci-verified": "ověřeno CI" };
const OUTCOME: Record<string, { tone: "ok" | "warn" | "bad" | "gap"; glyph: string; word: string }> = {
  passed: { tone: "ok", glyph: "✓", word: "prošlo" }, counterexample: { tone: "bad", glyph: "✕", word: "protipříklad" },
  failed: { tone: "bad", glyph: "✕", word: "selhalo" }, inconclusive: { tone: "warn", glyph: "◷", word: "bez rozhodnutí" },
  cancelled: { tone: "gap", glyph: "◌", word: "zrušeno" },
};

function record(raw: unknown): ProofRecord | null {
  if (!isObject(raw) || !isText(raw.id) || !isObject(raw.verification) || !isObject(raw.verification.tool)) return null;
  const verification = raw.verification, configuration = isObject(verification.configuration) ? verification.configuration : {};
  const origin = isObject(raw.origin) ? raw.origin : {}, source = isObject(verification.source) ? verification.source : {};
  const report = isObject(raw.report) ? raw.report : null, tool = isObject(verification.tool) ? verification.tool : {};
  const checkName = isText(origin.checkName) ? origin.checkName : isText(configuration.checkName) ? configuration.checkName : "";
  return { id: raw.id, nodeId: isText(raw.nodeId) ? raw.nodeId : "", acceptedRevision: isText(raw.acceptedRevision) ? raw.acceptedRevision : "",
    tool: isText(tool.name) ? tool.name : "?", checkName,
    commitSha: isText(source.commitSha) ? source.commitSha : "", trust: raw.trust === "ci-verified" ? "ci-verified" : "agent-reported",
    outcome: report && isText(report.outcome) ? report.outcome : null,
    createdAt: report && isText(report.createdAt) ? report.createdAt : isText(raw.createdAt) ? raw.createdAt : "" };
}
export function parseProofs(raw: unknown): ProofRecord[] {
  if (!isObject(raw)) throw new Error("Formální podklady mají neplatný tvar.");
  const items = Array.isArray(raw.requests) ? raw.requests : Array.isArray(raw.items) ? raw.items : null;
  if (!items) throw new Error("Formální podklady mají neplatný tvar.");
  return items.map(record).filter((item): item is ProofRecord => item !== null);
}
export const proofsEndpoint = (project: string, workspace: string, nodeId: string) =>
  `/api/oporahub/verifications?${new URLSearchParams({ project, workspace, nodeId })}`;

export const kindOf = (item: ProofRecord): ProofKind | null =>
  item.checkName.includes("conformance") ? "conformance" : item.tool === "lean" ? "lean" : item.tool === "tlc" ? "tlc" : null;

export type ProofRow = {
  kind: ProofKind; label: string; status: string; tone: "ok" | "warn" | "bad" | "gap"; glyph: string; word: string;
  trust: ProofTrust | null; trustLabel: string; verificationId: string; checkName: string; commit: string; historical: boolean; note: string;
};
export type ProofAction = { id: string; verb: string; path: string; targetId: string; status: string };

/** Tři řádky (lean, tlc, conformance): nejnovější záznam karty pro každý druh, jinak poctivá mezera. */
export function proofRows(records: ProofRecord[], acceptedHead: string | null): ProofRow[] {
  return PROOF_KINDS.map(kind => {
    const latest = records.filter(item => kindOf(item) === kind)
      .sort((a, b) => b.createdAt.localeCompare(a.createdAt))[0];
    if (!latest) return { kind, label: KIND_LABEL[kind], status: "not_connected", tone: "gap", glyph: "◌",
      word: kind === "conformance" ? "nenapojeno" : "bez záznamu", trust: null, trustLabel: "—", verificationId: "", checkName: "", commit: "",
      historical: false, note: kind === "conformance" ? "Check formal/conformance běží jen v CI; do karty se zatím nepřenáší." : "Pro kartu zatím nikdo nenahlásil ověření." };
    const outcome = latest.outcome ? OUTCOME[latest.outcome] ?? { tone: "warn" as const, glyph: "◷", word: latest.outcome } : { tone: "gap" as const, glyph: "◌", word: "bez výsledku" };
    const historical = !!acceptedHead && !!latest.acceptedRevision && latest.acceptedRevision !== acceptedHead;
    return { kind, label: KIND_LABEL[kind], status: latest.outcome ?? "pending", ...outcome, trust: latest.trust, trustLabel: TRUST_LABEL[latest.trust],
      verificationId: latest.id, checkName: latest.checkName, commit: latest.commitSha.slice(0, 12), historical,
      note: historical ? "Historický podklad · přijatá revize se změnila." : "Nezávislé ověření není doloženo." };
  });
}

/** Akce `verification.fix` / `verification.investigate` z agent-state, které míří na záznamy této karty. */
export function proofActions(actions: AgentAction[], records: ProofRecord[]): ProofAction[] {
  const ids = new Set(records.map(item => item.id));
  return actions.filter(item => (item.verb === "verification.fix" || item.verb === "verification.investigate") && !!item.targetId && ids.has(item.targetId))
    .map(item => ({ id: item.id, verb: item.verb, path: item.path, targetId: item.targetId as string, status: item.status }));
}
