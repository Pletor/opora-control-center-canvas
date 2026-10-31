// Celý obsah bočního menu (panel karty) z hotových dat: blok z Desktop v3 (je-li vybraný), karta ze snímku
// agent-state, stopa práce z `card-trail`. Bez bloku (karty srdce a kanceláře bloky nemají) je to režim karty:
// hlavička ukáže název a účel karty, zbytek je stejný. Rodič jen načte data; dílky dostanou hotové props.
import type { CardEntry } from "@/hub/oporahub-card-drawer/logic/card-header";
import { changeWhen, orderBadge } from "@/editor/canvas/card-face/logic/face-change";
import type { Block } from "@/shared/desktop-state/logic/types";
import type { GraphEdge } from "@/shared/types/logic/types";
import type { CardTrail, TrailJudgment } from "./card-trail";
import { judgmentView, portViews, workView, type JudgmentView, type PortView, type WorkView } from "./panel-work";
import { groupByDay, nowLine, timeline, TRAIL_SETTINGS, whoName, type TimelineGroup, type TrailSettings } from "./trail-timeline";

export type PanelView = {
  /** `kind` = co je otevřené: blok karty, nebo karta sama; `id` je ID bloku, resp. karty. */
  head: { kind: "block" | "card"; number: string; id: string; title: string; text: string; cardName: string; order: string | null;
    change: { who: string; whoKind: string; when: string; what: string } | null };
  work: WorkView; live: { text: string; at: string } | null; judgments: TrailJudgment[]; judgmentViews: JudgmentView[];
  timeline: TimelineGroup[]; filesKnown: boolean; ports: PortView[];
  /** Karty, ze kterých do této karty vede vazba (prázdný port: „Vstup přichází z …“). */
  incoming: string[];
};

/** Jak se v panelu jmenuje jiná karta: pořadí podle záměru a název („3·02 Zápis metrik“). */
export function cardLabel(name: string, order: number | null | undefined): string {
  return [orderBadge(order), name].filter(Boolean).join(" ");
}

/** Poslední viditelná změna karty („kdo · kdy · co“) ze stopy; `tool.use` je „teď“, ne změna. */
function lastChange(trail: CardTrail | null, now: Date): PanelView["head"]["change"] {
  const latest = trail?.recent.find((item) => item.kind !== "tool.use");
  if (!latest) return null;
  const who = whoName(latest.who);
  return { who: who.name, whoKind: who.kind, when: changeWhen(latest.at, now), what: latest.label || latest.kind };
}

export function panelView(input: {
  /** Vybraný blok; `null` = režim karty (panel otevřený z karty bez bloku). */
  block: Block | null; blocks: Block[]; cardId: string; cardName: string; cardPurpose?: string;
  card: CardEntry | null; trail: CardTrail | null; edges: GraphEdge[];
  /** Čitelné jméno jiné karty podle id (předchůdci z `blockedBy`, zdroje vazeb do karty). */
  labelOf?: (id: string) => string;
  settings?: TrailSettings; now?: Date;
}): PanelView {
  const { block, trail } = input;
  const now = input.now ?? new Date();
  const judgments = trail?.judgment ?? [];
  const labelOf = input.labelOf ?? ((id: string) => id);
  const subject = block
    ? { kind: "block" as const, number: block.number, id: block.id, title: block.title, text: block.text }
    : { kind: "card" as const, number: "", id: input.cardId, title: input.cardName, text: input.cardPurpose ?? "" };
  return {
    head: { ...subject, cardName: input.cardName, order: orderBadge(input.card?.order), change: lastChange(trail, now) },
    work: workView(input.card, trail, { waitingFor: (input.card?.blockedBy ?? []).map((id) => labelOf(id)) }),
    live: trail ? nowLine(trail) : null,
    judgments,
    judgmentViews: judgments.map(judgmentView),
    timeline: trail ? groupByDay(timeline(trail, input.settings ?? TRAIL_SETTINGS), now) : [],
    filesKnown: trail?.filesKnown ?? false,
    // Porty: stopa nese všechny vazby z karty (`source == karta`), v obou režimech stejně.
    ports: trail ? portViews(trail.ports, input.edges, input.blocks) : [],
    incoming: [...new Set(input.edges.filter((edge) => edge.target === input.cardId).map((edge) => labelOf(edge.source)))],
  };
}
