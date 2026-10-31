// Tvář karty z jediného zdroje stavu: `cards[]` agent-state (docs/oporahub-ui.md, „Tvář karty“). Čistá data bez
// funkcí a bez času (odpočet lease počítá komponenta), aby `stable-nodes.ts` mohl tvář porovnat hluboce.
// Na tváři je jen: druh, kdo kartu drží, název, JEDEN stavový řádek, postup kroků a nejvýš jedna patička.
// Přednost stavu: hotovo > rozhodnutí člověka > agent drží lease > blokováno předchůdcem > brána > zdraví.
import type { AgentCardStage, AgentDecision } from "@/hub/oporahub-agent-state/logic/agent-state";
import { STAGE_WORD, gateWord, shortReason } from "./face-labels";
import { prBadge, type PrBadge } from "@/shared/pr-badge/logic/pr-badge";
import { changeOf, orderBadge, type FaceChange, type LatestChange } from "./face-change";

export type FaceState = "blocked" | "ready" | "working" | "review" | "decision" | "done" | "problem" | "plan";
export type FaceTone = "ok" | "warn" | "bad" | "gap" | "hum";
export type FaceFooter =
  | { kind: "gate"; status: string; rule: string | null; tone: FaceTone; glyph: string; text: string }
  | { kind: "blocked"; ids: string[]; text: string }
  | { kind: "decision"; id: string; actionId: string; text: string };
export type CardFace = {
  nodeId: string; state: FaceState; kindChip: string;
  holder: { who: "agent" | "human"; name: string } | null;
  chip: { tone: FaceTone; glyph: string; word: string };
  stage: string; reason: string;
  /** Pronájem běží: komponenta místo důvodu ukáže odpočet. */
  lease: { holder: string | null; expiresAt: string; epoch: number | null } | null;
  steps: { total: number; done: number; segments: ("done" | "cur" | "")[]; count: string; label: string };
  footer: FaceFooter | null;
  /** Odznak PR v barvách GitHubu (`cards[].pr`); uzavřená karta ho nemá. */
  pr: PrBadge | null;
  /** Odznak pořadí podle záměru `F·PP` (`cards[].order`); karta bez pořadí ho nemá. */
  order: string | null;
  /** Poslední změna karty ze záznamu činnosti (`latest-by-node`); bez zápisu nic. */
  change: FaceChange | null;
  /** Syrové kódy pro `data-oh-*`. */
  raw: { stage: string; health: string; reason: string; executionId: string | null; gateStatus: string; gateRule: string };
};

const MAX_SEGMENTS = 12;
const GATE_TONE: Record<string, [FaceTone, string]> = { ready: ["ok", "✓"], pending: ["warn", "◷"], blocked: ["bad", "✕"] };
const HUMAN_REASONS = new Set(["awaiting_human_close", "human_review_required"]);
const gateTone = (status: string): [FaceTone, string] => GATE_TONE[status] ?? ["warn", "◷"];

function segments(total: number, done: number, running: boolean): CardFace["steps"]["segments"] {
  const shown = Math.min(total, MAX_SEGMENTS);
  const filled = total ? Math.round((done / total) * shown) : 0;
  return Array.from({ length: shown }, (_, index) => index < filled ? "done" : index === filled && running ? "cur" : "");
}

function stepsOf(card: AgentCardStage | undefined, running: boolean, closed: boolean): CardFace["steps"] {
  const steps = card?.steps ?? { total: 0, done: 0, current: null };
  const { total, done } = steps;
  const current = steps.current ? steps.current + (steps.currentTitle ? " " + steps.currentTitle : "") : "";
  const label = !total ? "plán bez kroků"
    : done >= total ? (closed ? "definice hotového splněna" : "všechny kroky splněny")
    : current ? (running ? current : "další " + current) : "kroky čekají";
  return { total, done, segments: segments(total, done, running && done < total), count: `${done}/${total}`, label };
}

export type FaceInput = {
  nodeId: string; card?: AgentCardStage; sector: boolean; layer?: string;
  decisions: readonly AgentDecision[]; nameOf: (id: string) => string;
  /** Nejnovější zápis záznamu činnosti s touto kartou (`latest-by-node`). */
  latest?: LatestChange;
};

/** Tvář jedné karty; karta, kterou agent-state nezná (starý server, neuložený uzel), je „v plánu“ bez kroků. */
export function cardFace({ nodeId, card, sector, layer, decisions, nameOf, latest }: FaceInput): CardFace {
  const closed = card?.reason === "card_closed" || card?.reason === "plan_written_back";
  const decision = card ? decisions.find(item => item.targetId === nodeId || (!!card.executionId && item.targetId === card.executionId)) : undefined;
  const blockedBy = card?.blockedBy ?? [];
  const lease = card?.lease ?? null;
  const gate = card?.gate ?? null;
  const base = {
    nodeId, kindChip: card?.kind || layer || (sector ? "sektor" : "uzel"), lease: null as CardFace["lease"],
    pr: card ? prBadge(card.stage, card.reason, card.pr, card.reason === "card_closed") : null,
    order: orderBadge(card?.order), change: changeOf(latest),
    stage: card ? STAGE_WORD[card.stage] : "plán", reason: card ? shortReason(card.reason) : "mimo OporaHub",
    raw: { stage: card?.stage ?? "", health: card?.health ?? "", reason: card?.reason ?? "", executionId: card?.executionId ?? null,
      gateStatus: gate?.status ?? "", gateRule: gate?.rule ?? "" },
  };
  // Patička je nejvýš jedna: rozhodnutí člověka > blokace předchůdcem > brána merge.
  const footer: FaceFooter | null = decision ? { kind: "decision", id: decision.id, actionId: decision.actionId, text: decision.title }
    : blockedBy.length ? { kind: "blocked", ids: blockedBy, text: blockedBy.map(nameOf).join(", ") }
    : gate ? { kind: "gate", status: gate.status, rule: gate.rule, tone: gateTone(gate.status)[0], glyph: gateTone(gate.status)[1], text: gateWord(gate) }
    : null;
  const face = (state: FaceState, tone: FaceTone, glyph: string, word: string, extra: Partial<CardFace> = {}): CardFace => ({
    ...base, state, chip: { tone, glyph, word }, holder: null, footer, steps: stepsOf(card, state === "working", closed), ...extra,
  });
  if (!card) return face("plan", "gap", "◌", "v plánu");
  if (closed) return face("done", "ok", "✓", "hotovo", card.reason === "card_closed"
    ? { stage: "uzavřeno", reason: "sloučeno a zapsáno" } : { stage: "zapsáno", reason: "sloučeno, čeká na uzavření" });
  if (decision || HUMAN_REASONS.has(card.reason)) return face("decision", "hum", "◷", "čeká na tebe", { holder: { who: "human", name: "ty" } });
  if (lease) {
    const late = card.health === "blocking";
    return face("working", late ? "bad" : "ok", late ? "✕" : "✓", "běží",
      { lease, holder: lease.holder ? { who: "agent", name: lease.holder.replace(/^agent:/, "") } : null });
  }
  if (blockedBy.length) return face("blocked", "gap", "◌", "blokováno", { reason: `čeká na ${blockedBy.length}` });
  if (gate && (card.stage === "review" || card.stage === "pull_request")) {
    const [tone, glyph] = gateTone(gate.status);
    return face("review", tone, glyph, gate.status === "ready" ? "splněno" : gate.status === "blocked" ? "blokuje" : "drží");
  }
  if (card.health === "blocking") return face("problem", "bad", "✕", "problém");
  if (card.stage === "claim") return face("ready", "ok", "✓", "připraveno");
  if (card.health === "waiting") return face("plan", "warn", "◷", "čeká");
  return face("plan", "ok", "✓", "v pořádku");
}
