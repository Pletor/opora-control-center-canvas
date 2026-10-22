import type { AgentAction, AgentCardStage, AgentState, Health, StageId } from "@/hub/oporahub-agent-state/logic/agent-state";
import { VERB_LABEL } from "@/hub/oporahub-agent-state/logic/actions-model";
import { healthGlyph, healthLabel, reasonText } from "@/hub/oporahub-agent-state/logic/loop-model";

// Hlavička detailu karty: jeden stavový řádek a jedna další akce, obojí jen ze snímku agent-state.
// Pole `cards[]` z vlny DAG (kind, blockedBy, nextActionId, gate, steps, dod) parser agent-state nehlídá,
// proto se čtou tolerantně: chybějící pole je „neznámé“, nikdy „v pořádku“.
/** Postup kroku z agent-state (`cards[].steps.items`, souhrn přes všechny běhy karty). */
export type CardStepItem = { id: string; status: string; executionId: string | null };
export type CardSteps = { total: number; done: number; current: string | null; items: CardStepItem[] };
export type CardGate = { status: string; rule: string | null };
export type CardEntry = AgentCardStage & {
  kind: string | null; layer: string | null; blockedBy: string[]; topoIndex: number | null;
  nextActionId: string | null; gate: CardGate | null; steps: CardSteps | null; dod: unknown;
};

const obj = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);
const str = (value: unknown) => typeof value === "string" ? value : null;
const int = (value: unknown) => Number.isSafeInteger(value) && Number(value) >= 0 ? Number(value) : null;

function stepItems(value: unknown): CardStepItem[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap(item => obj(item) && str(item.id) && str(item.status)
    ? [{ id: item.id as string, status: item.status as string, executionId: str(item.executionId) }] : []);
}

export function cardEntry(state: AgentState | null, nodeId: string): CardEntry | null {
  const raw = (state?.cards ?? []).find(item => item.nodeId === nodeId) as (AgentCardStage & Record<string, unknown>) | undefined;
  if (!raw) return null;
  const steps = obj(raw.steps) && int(raw.steps.total) !== null && int(raw.steps.done) !== null
    ? { total: int(raw.steps.total) as number, done: int(raw.steps.done) as number, current: str(raw.steps.current),
      items: stepItems(raw.steps.items) } : null;
  const gate = obj(raw.gate) && str(raw.gate.status) ? { status: raw.gate.status as string, rule: str(raw.gate.rule) } : null;
  return { ...raw, kind: str(raw.kind), layer: str(raw.layer), topoIndex: int(raw.topoIndex),
    blockedBy: Array.isArray(raw.blockedBy) ? raw.blockedBy.filter((id): id is string => typeof id === "string") : [],
    nextActionId: str(raw.nextActionId), gate, steps, dod: raw.dod ?? null };
}

export const STAGE_LABEL: Record<StageId, string> = {
  plan: "plán", proposal: "návrh", acceptance: "přijetí", claim: "převzetí", work: "běh", evidence: "důkazy",
  review: "review", pull_request: "PR", merge: "merge", plan_writeback: "zápis do plánu",
};
export type StatusLine = { health: Health; glyph: string; word: string; stage: string; reason: string; reasonCode: string };

/** Stavový řádek `značka slovo · etapa · důvod`; bez karty v agent-state poctivě „nenapojeno“. */
export function statusLine(card: CardEntry | null): StatusLine {
  if (!card) return { health: "not_connected", glyph: healthGlyph.not_connected, word: healthLabel.not_connected,
    stage: "—", reason: "Karta zatím není ve snímku agent-state.", reasonCode: "" };
  return { health: card.health, glyph: healthGlyph[card.health], word: healthLabel[card.health], stage: STAGE_LABEL[card.stage] ?? card.stage,
    reason: reasonText[card.reason] ?? card.reason, reasonCode: card.reason };
}

const HUMAN_VERBS = new Set(["accept_baseline", "accept", "close_card", "review", "proposal.resolve_conflict", "verification.fix"]);
const BLOCK_TEXT: Record<string, string> = {
  human_only: "rozhoduje člověk", budget_exhausted: "vyčerpaný rozpočet", budget_policy_required: "chybí pravidla běhů",
  blocked_by_predecessor: "čeká na předchůdce", not_implemented: "modul není napojen", done_state_incomplete: "definice hotovo není splněna",
  plan_steps_missing: "zadání nemá kroky",
};
export type NextAction = { id: string; verb: string; label: string; actor: "human" | "agent"; status: "ready" | "blocked";
  blockReason: string; blockText: string; path: string; method: string };

/** Akce v patičce: `cards[].nextActionId` z `actions[]`; bez něj první akce, která míří na kartu nebo její běh. */
export function nextAction(state: AgentState | null, card: CardEntry | null, nodeId: string): NextAction | null {
  const actions = state?.actions ?? [];
  const found: AgentAction | undefined = card?.nextActionId
    ? actions.find(item => item.id === card.nextActionId)
    : actions.find(item => item.targetId === nodeId || (!!card?.executionId && item.targetId === card.executionId));
  if (!found) return null;
  const blockReason = found.blockReason ?? "";
  return { id: found.id, verb: found.verb, label: VERB_LABEL[found.verb] ?? found.verb,
    actor: blockReason === "human_only" || HUMAN_VERBS.has(found.verb) ? "human" : "agent", status: found.status,
    blockReason, blockText: blockReason ? BLOCK_TEXT[blockReason] ?? blockReason : "", path: found.path, method: found.method };
}
