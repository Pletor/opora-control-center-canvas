import type { DetailTarget } from "@/hub/oporahub-overview/logic/overview";
import type { AgentState, StageId } from "./agent-state";
import { REVIEW_GATE_REASONS } from "./review-gate-labels";

// Doplňky etap v Přehledu: Review ukazuje stav brány merge a pravidlo, které ji drží; Návrh změny
// ukazuje počet konfliktů auto-rebase a otevře jejich drawer. Vše jen z dokumentu agent-state.
export type GateStatus = "blocked" | "pending" | "clear" | "off";
export type StageExtra = { text: string; tone: "ok" | "warn" | "bad" | "gap"; attrs: Record<string, string>; target?: DetailTarget };

const GENERIC = new Set(["review_gate_blocked", "review_gate_pending"]);
const GATE_TEXT: Record<GateStatus, string> = { blocked: "✕ brána blokuje", pending: "◷ brána čeká", clear: "✓ žádná brána nedrží", off: "◌ automatické review vypnuto" };
const GATE_TONE = { blocked: "bad", pending: "warn", clear: "ok", off: "gap" } as const;

/** Stav brány review z etapy: kód pravidla brány je přímo `reason` etapy (docs/oporahub-agent-state.md). */
export function reviewGate(state: AgentState): { status: GateStatus; rule: string } {
  const review = state.stages.find(item => item.id === "review")!;
  const gateReason = review.reason in REVIEW_GATE_REASONS;
  if (gateReason && review.health === "blocking") return { status: "blocked", rule: GENERIC.has(review.reason) ? "" : review.reason };
  if (gateReason && review.health === "waiting") return { status: "pending", rule: GENERIC.has(review.reason) ? "" : review.reason };
  if (state.gaps.some(item => item.id === "ai_review")) return { status: "off", rule: "" };
  return { status: "clear", rule: "" };
}

export function stageExtra(state: AgentState, id: StageId): StageExtra | null {
  if (id === "review") {
    const gate = reviewGate(state);
    // Lidské znění pravidla už nese důvod etapy; tady stačí stav brány a strojový kód pravidla.
    const rule = gate.rule ? ` · pravidlo ${gate.rule}` : "";
    return { text: GATE_TEXT[gate.status] + rule, tone: GATE_TONE[gate.status],
      attrs: { "data-oh-gate-status": gate.status, "data-oh-gate-rule": gate.rule } };
  }
  if (id === "proposal") {
    const conflicts = state.actions.filter(item => item.verb === "proposal.resolve_conflict").length;
    const reason = state.stages.find(item => item.id === "proposal")!.reason;
    if (!conflicts && reason !== "auto_rebase_conflicts") return null;
    return { text: `◷ konflikty auto-rebase: ${conflicts}`, tone: "warn", attrs: { "data-oh-conflicts": String(conflicts) },
      target: { kind: "conflicts", title: "Konflikty auto-rebase" } };
  }
  return null;
}
