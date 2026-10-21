import type { AgentCardStage, AgentState, StageId } from "@/hub/oporahub-agent-state/logic/agent-state";
import { healthGlyph, healthLabel, reasonText, toneOf, type Tone } from "@/hub/oporahub-agent-state/logic/loop-model";

// Odznak karty na plátně: etapa smyčky, značka zdraví a slovo. Barva nikdy nenese význam sama.
export type LoopBadge = {
  nodeId: string; stage: StageId; stageLabel: string; health: AgentCardStage["health"]; glyph: string; word: string;
  tone: Tone; reason: string; title: string; executionId: string | null;
};
export const STAGE_SHORT: Record<StageId, string> = {
  plan: "Plán", proposal: "Návrh", acceptance: "Přijetí", claim: "Převzetí", work: "Práce", evidence: "Důkazy",
  review: "Review", pull_request: "PR", merge: "Merge", plan_writeback: "Zápis",
};
const STAGE_NUMBER: Record<StageId, number> = { plan: 1, proposal: 2, acceptance: 3, claim: 4, work: 5, evidence: 6,
  review: 7, pull_request: 8, merge: 9, plan_writeback: 10 };

export function loopBadge(card: AgentCardStage): LoopBadge {
  const reason = reasonText[card.reason] ?? card.reason;
  return { nodeId: card.nodeId, stage: card.stage, stageLabel: STAGE_SHORT[card.stage], health: card.health,
    glyph: healthGlyph[card.health], word: healthLabel[card.health], tone: toneOf[card.health], reason: card.reason,
    executionId: card.executionId,
    title: `OporaHub · ${STAGE_NUMBER[card.stage]}. ${STAGE_SHORT[card.stage]} · ${healthLabel[card.health]} · ${reason}` };
}

/** Odznaky jen pro karty, které agent-state zná; starý server bez `cards[]` nekreslí nic (žádné domýšlení). */
export function loopBadges(state: AgentState | null, nodeIds: readonly string[]): LoopBadge[] {
  if (!state?.cards) return [];
  const wanted = new Set(nodeIds);
  return state.cards.filter(item => wanted.has(item.nodeId)).map(loopBadge);
}
