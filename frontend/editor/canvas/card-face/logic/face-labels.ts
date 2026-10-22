// Krátká čeština pro jediný stavový řádek karty. Strojový kód (`stage`, `reason`, pravidlo brány) je smlouva
// backendu (docs/oporahub-agent-state.md); tady je jen jeho znění do jednoho řádku. Neznámý kód zůstane doslova.
import type { StageId } from "@/hub/oporahub-agent-state/logic/agent-state";
import { reasonText } from "@/hub/oporahub-agent-state/logic/loop-model";

export const STAGE_WORD: Record<StageId, string> = {
  plan: "plán", proposal: "návrh", acceptance: "přijetí", claim: "k převzetí", work: "běh", evidence: "důkazy",
  review: "review", pull_request: "PR", merge: "merge", plan_writeback: "zápis",
};

const SHORT: Record<string, string> = {
  card_in_plan: "v plánu", cards_ready: "připraveno", runs_active: "lease", lease_past_deadline: "lease vypršel",
  stale_evidence: "výsledek ke staré revizi", human_review_required: "výsledek ke kontrole",
  pull_requests_open: "PR otevřeno", review_gate_ready: "brána splněna", review_gate_pending: "brána čeká",
  review_gate_blocked: "brána blokuje", awaiting_human_close: "sloučeno · uzavřít",
  plan_written_back: "zapsáno do plánu", merged_without_plan_writeback: "sloučeno bez zápisu",
  card_closed: "uzavřeno", budget_exhausted: "rozpočet vyčerpán", budget_policy_required: "chybí pravidla běhů",
  no_accepted_baseline: "bez přijatého základu", open_security_findings: "bezpečnostní nález",
  self_checks_failed: "vlastní kontrola selhala", required_checks_failed: "CI selhalo",
  stale_against_main: "za hlavou main", self_checks_missing: "chybí vlastní kontroly",
  security_review_not_enqueued: "security review nezařazeno", security_review_in_progress: "běží security review",
  required_checks_pending: "CI běží", base_freshness_unobserved: "čerstvost větve neznámá",
  template_unobserved: "popis PR nepřečten", template_incomplete: "popis PR neúplný",
};

/** Jedno krátké slovo nebo fráze k důvodu; delší věta z OporaHubu bez tečky, jinak kód doslova. */
export function shortReason(code: string): string {
  if (SHORT[code]) return SHORT[code];
  const sentence = reasonText[code];
  return sentence ? sentence.replace(/\.$/, "").toLowerCase() : code;
}

/** Popisek brány: pravidlo, které ji drží, jinak stav. */
export function gateWord(gate: { status: string; rule: string | null }): string {
  if (gate.status === "ready") return "splněna";
  if (gate.rule) return shortReason(gate.rule);
  return gate.status === "blocked" ? "blokuje" : "čeká";
}

/** Zbývající čas pronájmu `mm:ss` (nad hodinu `h:mm:ss`); prošlý pronájem je „vypršel“. */
export function countdown(expiresAt: string, now: number): string {
  const left = Math.floor((Date.parse(expiresAt) - now) / 1000);
  if (!Number.isFinite(left)) return "";
  if (left <= 0) return "vypršel";
  const h = Math.floor(left / 3600), m = Math.floor((left % 3600) / 60), s = left % 60;
  const pad = (value: number) => String(value).padStart(2, "0");
  return h ? `${h}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}
