// Mapa toku: jeden řádek na kartu, sedm fází. Řádek skládá snímek karty z agent-state (etapa, zdraví,
// běh, lease) a události toku. Aktuální fáze = fáze poslední události karty (`memory.recall` je čtení,
// fázi nemění); bez události fáze podle etapy snímku a značka „bez události“. Stopa za značkou nese stav
// poslední události každé minulé fáze. Pořadí: nejdřív blokace, pak čerstvost poslední události.
import type { AgentCardStage, StageId } from "@/hub/oporahub-agent-state/logic/agent-state";
import { PHASES, phaseIndex, type FlowEvent, type ProcessSource, type ProcessState } from "./process-event";

export type CardSnapshot = AgentCardStage & { lastEventAt?: string | null };
/** Stopa ve fázi: potvrzeno, selhalo, čeká, proběhlo bez potvrzení, bez události. */
export type TrailMark = "ok" | "fail" | "wait" | "seen" | "none";
export type MarkerTone = "run" | "ok" | "wait" | "fail" | "blocked" | "none" | "stale";
export type Blocker = { label: string; tone: "bad" | "warn"; human: boolean };
export type Lane = {
  nodeId: string; title: string; workerName: string; source: ProcessSource | null;
  phase: number; marker: MarkerTone; trail: (TrailMark | null)[]; last: FlowEvent | null; lastMs: number;
  blocker: Blocker | null; stale: boolean; card: CardSnapshot | null; events: FlowEvent[];
};

const STAGE_PHASE: Record<StageId, string> = {
  plan: "plan", proposal: "plan", acceptance: "plan", claim: "intake", work: "work", evidence: "checks",
  review: "review", pull_request: "review", merge: "merge", plan_writeback: "merge",
};

/** Stav poslední události fáze → tvar stopy. Start, průběh a info nejsou potvrzení. */
export function trailMark(state: ProcessState): TrailMark {
  if (state === "ok") return "ok";
  if (state === "fail") return "fail";
  if (state === "wait" || state === "blocked") return "wait";
  return "seen";
}

/** Redukce událostí karty (vzestupně) na stav každé fáze: poslední událost fáze vyhrává. */
export function phaseTrail(events: FlowEvent[]): (TrailMark | null)[] {
  const trail: (TrailMark | null)[] = PHASES.map(() => null);
  for (const event of events) if (event.phase >= 0) trail[event.phase] = trailMark(event.state);
  return trail;
}

/** Blokace = poslední událost karty potřebuje člověka nebo selhala; jinak blokující zdraví snímku. */
export function blockerOf(last: FlowEvent | null, card: CardSnapshot | null): Blocker | null {
  if (last) {
    if (last.kind === "needs.input") return { label: "čeká na vás", tone: "bad", human: true };
    if (last.kind === "pr.checks" && last.state === "fail") return { label: "CI selhalo", tone: "bad", human: false };
    if (last.kind === "pr.review" && last.state === "wait") return { label: "změny požadovány", tone: "warn", human: true };
    if (last.kind === "guard" && last.state === "fail") return { label: "guard červený", tone: "bad", human: false };
    if (last.kind === "tool.use" && last.state === "fail") return { label: "nástroj selhává", tone: "bad", human: false };
    if (last.state === "blocked") return { label: "blokováno", tone: "bad", human: true };
    if (last.state === "fail") return { label: "selhalo", tone: "bad", human: false };
  }
  if (card?.health === "blocking") return { label: "blokuje", tone: "bad", human: false };
  return null;
}

function markerOf(last: FlowEvent | null, stale: boolean): MarkerTone {
  if (!last) return "none";
  if (stale) return "stale";
  if (last.state === "ok") return "ok";
  if (last.state === "wait") return "wait";
  if (last.state === "fail") return "fail";
  if (last.state === "blocked") return "blocked";
  return "run";
}

export type LaneOptions = { names: Record<string, string>; officeConnected: boolean | null };

/** Řádky mapy: karty s událostí v okně nebo s během, lease či `lastEventAt` ve snímku. */
export function buildLanes(cards: CardSnapshot[], events: FlowEvent[], { names, officeConnected }: LaneOptions): Lane[] {
  const byCard = new Map<string, FlowEvent[]>();
  for (const event of [...events].sort((a, b) => a.id - b.id)) {
    if (!event.cardId) continue;
    const list = byCard.get(event.cardId) ?? [];
    list.push(event); byCard.set(event.cardId, list);
  }
  const snapshot = new Map(cards.map((card) => [card.nodeId, card]));
  const ids = new Set([...byCard.keys(), ...cards.filter((card) => card.lastEventAt || card.executionId || card.lease).map((card) => card.nodeId)]);
  const lanes = [...ids].map((nodeId): Lane => {
    const own = byCard.get(nodeId) ?? [];
    const card = snapshot.get(nodeId) ?? null;
    const moving = own.filter((event) => event.kind !== "memory.recall" && event.phase >= 0);
    const last = moving[moving.length - 1] ?? own[own.length - 1] ?? null;
    const phase = last && last.phase >= 0 ? last.phase : phaseIndex(card ? STAGE_PHASE[card.stage] : "intake");
    const worker = [...own].reverse().find((event) => event.workerName);
    const stale = officeConnected === false && last?.source === "office";
    return {
      nodeId, title: names[nodeId] || nodeId, workerName: worker?.workerName || card?.lease?.holder || "",
      source: last?.source ?? null, phase: Math.max(0, phase), marker: markerOf(last, stale), trail: phaseTrail(own),
      last, lastMs: last?.ms || Date.parse(card?.lastEventAt ?? "") || 0,
      blocker: blockerOf(last, card), stale, card, events: [...own].reverse(),
    };
  });
  return lanes.sort((a, b) => Number(!!b.blocker) - Number(!!a.blocker) || b.lastMs - a.lastMs || a.nodeId.localeCompare(b.nodeId));
}

/** Pořadí řádků při hoveru myši nad mapou zamrzne (řádek pod kurzorem neujede); nové řádky jdou na konec. */
export function stableOrder(previous: string[], next: string[], frozen: boolean): string[] {
  if (!frozen) return next;
  const present = new Set(next);
  const kept = previous.filter((id) => present.has(id));
  const known = new Set(kept);
  return [...kept, ...next.filter((id) => !known.has(id))];
}
