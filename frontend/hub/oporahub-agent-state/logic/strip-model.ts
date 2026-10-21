import type { DetailTarget } from "@/hub/oporahub-overview/logic/overview";
import type { AgentAction, AgentDecision, AgentState } from "./agent-state";
import type { Tone } from "./loop-model";

// Horní pás přehledu: hlava, drift, mix rizika a nejvýše tři rozhodnutí člověka.
export type DecisionView = { id: string; actionId: string; title: string; kindLabel: string; tone: Tone; button: string; target: DetailTarget };
export type StripView = {
  head: string | null; headShort: string; workingDiffers: boolean; staleCount: number;
  risk: { low: number; elevated: number; critical: number; total: number; pct: { low: number; elevated: number; critical: number } };
  decisions: DecisionView[]; gaps: { id: string; label: string; reason: string }[];
};

const KIND: Record<string, { label: string; tone: Tone; button: string }> = {
  accept_baseline: { label: "základ", tone: "warn", button: "Zkontrolovat" },
  accept_critical: { label: "kritické", tone: "bad", button: "Rozhodnout" },
  accept_elevated: { label: "zvýšené", tone: "warn", button: "Rozhodnout" },
  accept_low: { label: "nízké", tone: "ok", button: "Zkontrolovat" },
  review_result: { label: "výsledek", tone: "warn", button: "Zkontrolovat" },
  close_card: { label: "uzavření", tone: "warn", button: "Uzavřít kartu" },
};
export const GAP_LABEL: Record<string, string> = {
  ai_review: "AI review", lean_verification: "Lean", auto_rebase: "auto-rebase", pull_request_link: "PR ↔ běh",
};

/** Cíl rozhodnutí nebo akce se odvozuje z jejího API, ne z hádání: cesta říká druh návrhu. */
export function actionTarget(action: Pick<AgentAction, "path" | "targetId">, title: string): DetailTarget {
  const id = action.targetId ?? undefined;
  if (action.path.includes("/changesets/")) return { kind: "changes", id, title };
  if (action.path.includes("/graph-proposals/")) return { kind: "graph", id, title };
  if (action.path.includes("/content-changes/")) return { kind: "content", id, title };
  if (action.path.includes("/executions/claim") || action.path.includes("/desktop-v3/state")) return { kind: "card", id, title };
  if (action.path.includes("/executions/")) return { kind: "executions", id, title };
  return { kind: "graph", title };
}
export function decisionView(decision: AgentDecision, actions: AgentAction[]): DecisionView {
  const kind = KIND[decision.kind] ?? { label: decision.kind, tone: "warn" as Tone, button: "Otevřít" };
  const action = actions.find(item => item.id === decision.actionId);
  const target = action ? actionTarget(action, decision.title) : { kind: "history" as const, title: decision.title };
  return { id: decision.id, actionId: decision.actionId, title: decision.title, kindLabel: kind.label, tone: kind.tone, button: kind.button, target };
}
const percent = (part: number, total: number) => total ? Math.round(part / total * 1000) / 10 : 0;

export function stripModel(state: AgentState): StripView {
  const { low, elevated, critical } = state.riskMix, total = low + elevated + critical;
  return {
    head: state.heads.acceptedHead, headShort: state.heads.acceptedHead?.slice(0, 12) ?? "nezaložena",
    workingDiffers: state.heads.workingDiffers,
    staleCount: state.actions.filter(item => item.verb === "rebase").length,
    risk: { low, elevated, critical, total, pct: { low: percent(low, total), elevated: percent(elevated, total), critical: percent(critical, total) } },
    decisions: state.decisions.slice(0, 3).map(item => decisionView(item, state.actions)),
    gaps: state.gaps.map(item => ({ id: item.id, label: GAP_LABEL[item.id] ?? item.id, reason: item.reason })),
  };
}
