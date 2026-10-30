import type { AgentState } from "@/hub/oporahub-agent-state/logic/agent-state";
import { BLOCK_TEXT } from "../../logic/card-header";

// Uzavření karty po sloučení PR: agent-state nese akci `close_card` (cíl = karta, preconditions
// executionId · mergeSha · missing · gate). Splněná definice hotovo kromě lidského uzavření přijde jako
// `blocked: human_only` (čeká jen na člověka) nebo `ready` (plná autonomie); obojí člověku nabídne tlačítko.
// Jinak panel řekne česky, co chybí. Zápis `done` dělá rodič (App) přes desktop-state; tady jen model.
export type CloseCardModel =
  | { state: "ready"; label: string; executionId: string; mergeSha: string; shortSha: string; pr: number | null; mergeText: string; note: string }
  | { state: "blocked"; blockReason: string; missing: string[]; reason: string };

/** Co chybí do definice hotovo (backend `missing`), jako doplnění věty „chybí …“. */
export const MISSING_TEXT: Record<string, string> = {
  steps: "výsledky kroků", card_acceptance: "akceptace karty", gate_ready: "zelená brána review", merged: "sloučení PR",
  plan_written_back: "zápis do plánu", journeys: "ověřená cesta zákazníka",
};

const text = (value: unknown) => typeof value === "string" ? value : "";

export const shortSha = (sha: string) => sha.slice(0, 7);

/** Poznámka, kterou člověk zapíše do `done.note`. */
export function closeNote(sha: string, pr: number | null): string {
  const ref = sha ? shortSha(sha) : pr !== null ? `#${pr}` : "";
  return ref ? `Uzavřeno po sloučení PR (${ref})` : "Uzavřeno po sloučení PR";
}

/** Česká věta, proč kartu nejde uzavřít. */
export function blockedText(blockReason: string, missing: string[]): string {
  if (blockReason === "done_state_incomplete" && missing.length)
    return `Kartu nejde uzavřít: chybí ${missing.map(key => MISSING_TEXT[key] ?? key).join(", ")}.`;
  return `Kartu nejde uzavřít: ${BLOCK_TEXT[blockReason] ?? (blockReason || "neznámý důvod")}.`;
}

/** Model panelu z akce `close_card` této karty; `null` = akce není nebo je karta už uzavřená. */
export function closeCardModel(agent: AgentState | null, nodeId: string, facts: { pr?: number | null; closed?: boolean } = {}): CloseCardModel | null {
  if (facts.closed) return null;
  const action = (agent?.actions ?? []).find(item => item.verb === "close_card" && item.targetId === nodeId);
  if (!action) return null;
  const pre = action.preconditions ?? {};
  const blockReason = action.blockReason ?? "";
  if (action.status === "ready" || blockReason === "human_only") {
    const sha = text(pre.mergeSha), pr = facts.pr ?? null;
    const mergeText = [pr !== null ? `PR #${pr}` : "", sha ? `merge ${shortSha(sha)}` : ""].filter(Boolean).join(" · ") || "PR sloučen";
    return { state: "ready", label: "Uzavřít kartu", executionId: text(pre.executionId), mergeSha: sha, shortSha: shortSha(sha), pr,
      mergeText, note: closeNote(sha, pr) };
  }
  const missing = Array.isArray(pre.missing) ? pre.missing.filter((item): item is string => typeof item === "string") : [];
  return { state: "blocked", blockReason, missing, reason: blockedText(blockReason, missing) };
}
