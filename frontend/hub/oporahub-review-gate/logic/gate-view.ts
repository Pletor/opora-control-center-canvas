import type { AgentAction } from "@/hub/oporahub-agent-state/logic/agent-state";
import { REVIEW_GATE_REASONS } from "@/hub/oporahub-agent-state/logic/review-gate-labels";
import type { GateStatus, ReviewGate } from "./review-gate";

// Krok Review v detailu karty: co bránu drží, kolik lidí ji schválilo a co má udělat agent.
export const GATE_REASON_TEXT: Record<string, string> = {
  ...REVIEW_GATE_REASONS,
  review_round_cap_reached: "Review dosáhlo stropu kol; rozhodne člověk.",
  open_important_findings: "Otevřený důležitý nález review blokuje merge.",
  changes_requested: "Reviewer požaduje změny.", invalid_review_evidence: "Důkaz review je neplatný.",
  review_not_enqueued: "Review ještě není zařazené.", review_in_progress: "Běží review kódu.",
  human_approvals_missing: "Chybí schválení člověkem pro aktuální hlavu.",
  github_evidence_missing: "Chybí GitHub důkazy; načtěte je v OporaHubu.",
  github_evidence_stale_head: "GitHub důkazy patří starší hlavě PR.",
};
const BLOCKED = ["open_security_findings", "self_checks_failed", "required_checks_failed", "review_round_cap_reached",
  "open_important_findings", "changes_requested", "invalid_review_evidence"];
const PENDING = ["stale_against_main", "self_checks_missing", "security_review_not_enqueued", "security_review_in_progress",
  "required_checks_pending", "base_freshness_unobserved", "template_unobserved", "template_incomplete", "review_not_enqueued",
  "review_in_progress", "human_approvals_missing", "github_evidence_missing", "github_evidence_stale_head"];
export const GATE_STATUS: Record<GateStatus, { glyph: string; word: string; health: "ok" | "waiting" | "blocking" }> = {
  ready: { glyph: "✓", word: "připraveno", health: "ok" }, pending: { glyph: "◷", word: "čeká", health: "waiting" },
  blocked: { glyph: "✕", word: "blokuje", health: "blocking" },
};

/** Pravidlo, které bránu drží: nejdřív podle priority stavu brány, pak ostatní známé, pak zbytek v pořadí API. */
export function holdingRule(reasons: string[], status: GateStatus): string {
  if (status === "ready" || !reasons.length) return "";
  const order = status === "blocked" ? [...BLOCKED, ...PENDING] : [...PENDING, ...BLOCKED];
  return order.find(code => reasons.includes(code)) ?? reasons[0];
}
export const reasonLabel = (code: string) => GATE_REASON_TEXT[code] ?? code;

export type GateView = {
  executionId: string; pr: string; head: string; prState: string; status: GateStatus; statusGlyph: string; statusWord: string;
  health: "ok" | "waiting" | "blocking"; rule: string; ruleText: string; reasons: { code: string; text: string }[];
  openImportant: number; security: { state: string; text: string; reasons: string[] };
  approvals: { required: number; counted: number; mode: string; label: string; notes: string[] };
  selfChecks: { status: string; detail: string }; stale: { on: boolean; text: string }; template: { on: boolean; text: string };
  actions: { id: string; verb: string; status: string; blockReason: string }[];
};

function securityView(gate: ReviewGate) {
  const sec = gate.mergeReadiness.security;
  if (!sec) return { state: "off", text: "vypnuto", reasons: [] as string[] };
  const reasons = gate.reviewGate.reasons;
  const state = reasons.includes("open_security_findings") ? "blocked"
    : reasons.some(code => code.startsWith("security_review_")) ? "pending" : "ok";
  return { state, text: `fáze ${sec.phase} · ${sec.openImportant} otevřených důležitých`, reasons: sec.reasons };
}
function selfCheckView(gate: ReviewGate) {
  const checks = gate.mergeReadiness.selfChecks;
  if (!checks) return { status: "off", detail: "pravidlo vypnuto" };
  const parts = [checks.missing.length ? `chybí: ${checks.missing.join(", ")}` : "", checks.failed.length ? `selhalo: ${checks.failed.join(", ")}` : "",
    checks.invalid ? `${checks.invalid} neplatných záznamů` : ""].filter(Boolean);
  return { status: checks.status, detail: parts.join(" · ") || (checks.status === "ok" ? "doloženo pro aktuální hlavu" : "") };
}

export function gateView(gate: ReviewGate, actions: AgentAction[]): GateView {
  const rg = gate.reviewGate, rule = holdingRule(rg.reasons, rg.status), status = GATE_STATUS[rg.status];
  const humans = rg.humans?.mode === "verified_humans" ? rg.humans : undefined;
  const notes: string[] = [];
  if (humans?.directorId) notes.push("Operátor, který přijal plán, se počítá jednou.");
  if (humans?.unverifiedApprovals) notes.push(`${humans.unverifiedApprovals} schválení z neověřených účtů se nepočítá.`);
  if (!humans) notes.push("Projekt zatím nemá ověřené identity; počítají se účty.");
  const base = gate.mergeReadiness.base, template = gate.mergeReadiness.template;
  const stale = rg.reasons.includes("stale_against_main"), incomplete = rg.reasons.includes("template_incomplete");
  return {
    executionId: gate.executionId, pr: `${gate.repository}#${gate.number}`, head: gate.headSha.slice(0, 12), prState: gate.prState,
    status: rg.status, statusGlyph: status.glyph, statusWord: status.word, health: status.health,
    rule, ruleText: rule ? reasonLabel(rule) : "Brána nic nedrží.",
    reasons: rg.reasons.map(code => ({ code, text: reasonLabel(code) })), openImportant: rg.openImportant, security: securityView(gate),
    approvals: { required: rg.requiredHumanApprovals, counted: humans ? humans.count : rg.humanApprovalsAtHead,
      mode: humans ? "verified_humans" : "accounts", label: humans ? "ověření lidé" : "účty (bez ověřených identit)", notes },
    selfChecks: selfCheckView(gate),
    stale: { on: stale, text: stale ? `${base?.behindBy ?? "?"} commitů za ${base?.baseRef ?? "cílovou větví"}`
      : base ? `stojí na aktuální ${base.baseRef}` : "neověřeno" },
    template: { on: incomplete, text: incomplete ? `chybí sekce: ${template?.missing.join(", ") || "?"}`
      : template ? "šablona vyplněna" : "pravidlo vypnuto" },
    actions: actions.filter(item => (item.verb === "review.claim" && !!gate.reviewJobId && item.targetId === gate.reviewJobId)
      || ((item.verb === "review.self_checks" || item.verb === "pr.update_branch") && item.targetId === gate.executionId))
      .map(item => ({ id: item.id, verb: item.verb, status: item.status, blockReason: item.blockReason ?? "" })),
  };
}
