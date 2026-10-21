import type { AgentAction, AgentState } from "./agent-state";

// Fronta akcí pro pohled „Pro agenty“: stejné pořadí jako API (sloveso, cíl), jen čitelně rozložené.
export type ActionRow = {
  id: string; verb: string; verbLabel: string; targetId: string | null; method: string; path: string;
  preconditions: { key: string; value: string }[]; budget: string; status: "ready" | "blocked";
  statusLabel: string; blockReason: string; human: boolean;
};
export const VERB_LABEL: Record<string, string> = {
  accept_baseline: "Přijmout základ", accept: "Přijmout návrh", rebase: "Převést návrh", claim: "Převzít kartu",
  review: "Zkontrolovat výsledek", link_pull_request: "Navázat PR", close_card: "Uzavřít kartu",
};
const show = (value: unknown) => value === null ? "null" : typeof value === "string" ? value : JSON.stringify(value);
export function budgetText(action: AgentAction) {
  if (!action.budget) return "—";
  const { remainingAttempts: attempts, remainingRepairRounds: repairs } = action.budget;
  return `${attempts ?? "?"} pokusů · ${repairs ?? "?"} oprav`;
}
export function actionRows(state: AgentState): ActionRow[] {
  return state.actions.map(action => ({
    id: action.id, verb: action.verb, verbLabel: VERB_LABEL[action.verb] ?? action.verb, targetId: action.targetId,
    method: action.method, path: action.path,
    preconditions: Object.entries(action.preconditions).map(([key, value]) => ({ key, value: show(value) })),
    budget: budgetText(action), status: action.status,
    statusLabel: action.status === "ready" ? "ready" : `blocked:${action.blockReason ?? "?"}`,
    blockReason: action.blockReason ?? "", human: action.blockReason === "human_only",
  }));
}
/** Fakta pro CAS: přesné hodnoty, které agent opakuje v těle zápisu. */
export function headFacts(state: AgentState) {
  const policies = Object.entries(state.heads.budgetPolicyHead);
  return [
    { field: "acceptedHead", value: state.heads.acceptedHead ?? "null" },
    { field: "graphDigest", value: state.heads.graphDigest },
    { field: "contextVersion", value: state.heads.contextVersion },
    { field: "workingDiffers", value: String(state.heads.workingDiffers) },
    { field: "budgetPolicyHead", value: policies.length ? policies.map(([node, head]) => `${node}=${head.slice(0, 12)}`).join(" · ") : "{}" },
  ];
}
export const PROTOCOL = ["1 · GET stav (If-None-Match)", "2 · ověř preconditions", "3 · zápis s requestId",
  "409 → znovu GET, neopakuj naslepo", "přijetí = jen člověk"];
