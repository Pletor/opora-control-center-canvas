// Živý proces (návrh „Opora Editor — lean“, rámy 5a/5b): události toku jako značky na drahách karet. Dráha =
// karta vrstvy v pořadí `topoIndex`, poloha značky = čas v okně (5 / 15 / 60 min), pronájem = pás od převzetí
// do konce (výsledek, vypršení, nebo „teď“, když karta lease drží), heartbeat = čárka. Čistá data.
import type { CardTab } from "@/hub/oporahub-card-drawer/open";
import { STAGE_WORD, gateWord, shortReason } from "@/editor/canvas/card-face/logic/face-labels";
import type { OporaEvent } from "./events-client";

export type MarkTone = "run" | "ok" | "bad" | "gate" | "human" | "merge" | "plain";
const KIND: Record<string, [string, MarkTone, CardTab]> = {
  "step.started": ["▸", "run", "steps"], "step.done": ["✓", "ok", "steps"], "step.failed": ["!", "bad", "steps"],
  "lease.claimed": ["▸", "run", "run"], "lease.heartbeat": ["|", "plain", "run"], "lease.expired": ["✕", "bad", "run"],
  "result.reported": ["✓", "ok", "run"], "pr.linked": ["#", "plain", "review"], "review.round": ["↻", "gate", "review"],
  "review.finding": ["!", "bad", "review"], "gate.changed": ["◆", "gate", "review"], "formal.result": ["∴", "plain", "review"],
  "decision.created": ["●", "human", "spec"], "decision.resolved": ["●", "ok", "spec"],
  "changeset.proposed": ["✎", "plain", "spec"], "changeset.accepted": ["✎", "ok", "spec"],
  "autorebase.done": ["↻", "ok", "spec"], "autorebase.conflict": ["↻", "bad", "spec"],
  "merge.done": ["⇥", "merge", "review"], "writeback.done": ["⇥", "merge", "history"], "card.closed": ["✓", "ok", "history"],
  "stage.changed": ["·", "plain", "run"],
};
export const markOf = (kind: string) => { const [glyph, tone, tab] = KIND[kind] ?? ["·", "plain" as MarkTone, "history" as CardTab]; return { glyph, tone, tab }; };

const text = (value: unknown) => typeof value === "string" ? value : value == null ? "" : String(value);
/** Krátký popis události do jednoho řádku („s4 zahájen“, „brána CI běží“); neznámý druh doslova. */
export function eventText(event: OporaEvent): string {
  const data = event.data ?? {};
  const step = event.stepId ?? text(data.stepId);
  switch (event.kind) {
    case "step.started": return `${step} zahájen`;
    case "step.done": return `${step} hotov`;
    case "step.failed": return `${step} selhal`;
    case "lease.claimed": return `převzato · ${event.actor.name.replace(/^agent:/, "")}`;
    case "lease.heartbeat": return "heartbeat";
    case "lease.expired": return "lease vypršel";
    case "result.reported": return "výsledek nahlášen";
    case "pr.linked": return `PR #${event.prNumber ?? ""}`;
    case "review.round": return `review · kolo ${text(data.round)}`;
    case "review.finding": return `nález ${text(data.severity)}`;
    case "gate.changed": { const gate = data.gate as { status: string; rule: string | null } | null; return gate ? `brána ${gateWord(gate)}` : "brána zrušena"; }
    case "formal.result": return `formální ověření · ${text(data.outcome)}`;
    case "decision.created": return "rozhodnutí";
    case "decision.resolved": return "rozhodnuto";
    case "changeset.proposed": return "návrh zadání";
    case "changeset.accepted": return "zadání přijato";
    case "autorebase.done": return "auto-rebase";
    case "autorebase.conflict": return "konflikt auto-rebase";
    case "merge.done": return "sloučeno";
    case "writeback.done": return "zapsáno do plánu";
    case "card.closed": return "uzavřeno";
    case "stage.changed": return `${STAGE_WORD[event.stage as keyof typeof STAGE_WORD] ?? event.stage} · ${shortReason(text(data.reason))}`;
    default: return event.kind;
  }
}

export type Lane = { nodeId: string; name: string; glyph: string;
  marks: { id: number; x: number; glyph: string; tone: MarkTone; title: string; tab: CardTab }[];
  ticks: number[]; spans: { from: number; to: number }[] };
export type LaneCard = { nodeId: string; name: string; glyph: string; leased: boolean };

const clamp = (value: number) => Math.max(0, Math.min(100, value));
/** Dráhy karet pro okno `[now - windowMs, now]`; x v procentech šířky. */
export function lanes(events: readonly OporaEvent[], cards: readonly LaneCard[], windowMs: number, now: number): Lane[] {
  const start = now - windowMs;
  const x = (at: string) => clamp(((Date.parse(at) - start) / windowMs) * 100);
  return cards.map((card) => {
    const own = events.filter((event) => event.nodeId === card.nodeId);
    const inWindow = own.filter((event) => Date.parse(event.at) >= start && Date.parse(event.at) <= now);
    const spans: Lane["spans"] = [];
    let open: number | null = null;
    for (const event of own) {
      if (event.kind === "lease.claimed") open = x(event.at);
      else if (open !== null && (event.kind === "lease.expired" || event.kind === "result.reported")) { spans.push({ from: open, to: x(event.at) }); open = null; }
    }
    if (open !== null || (card.leased && !spans.length)) spans.push({ from: open ?? 0, to: card.leased ? 100 : open ?? 0 });
    return { nodeId: card.nodeId, name: card.name, glyph: card.glyph,
      ticks: inWindow.filter((event) => event.kind === "lease.heartbeat").map((event) => x(event.at)),
      spans: spans.filter((span) => span.to > span.from),
      marks: inWindow.filter((event) => event.kind !== "lease.heartbeat").map((event) => {
        const mark = markOf(event.kind);
        return { id: event.id, x: x(event.at), glyph: mark.glyph, tone: mark.tone, tab: mark.tab,
          title: `${event.kind} · ${eventText(event)} · #${event.id} · ${event.at.slice(11, 19)} · ${event.actor.name}` };
      }) };
  });
}

/** Časové značky osy: celé minuty po kroku podle okna. */
export function axis(windowMs: number, now: number): { x: number; label: string }[] {
  const step = windowMs <= 5 * 60_000 ? 60_000 : windowMs <= 15 * 60_000 ? 120_000 : 600_000;
  const start = now - windowMs;
  const out: { x: number; label: string }[] = [];
  for (let t = Math.ceil(start / step) * step; t < now; t += step)
    out.push({ x: ((t - start) / windowMs) * 100, label: new Date(t).toLocaleTimeString("cs-CZ", { hour: "2-digit", minute: "2-digit" }) });
  return out;
}
