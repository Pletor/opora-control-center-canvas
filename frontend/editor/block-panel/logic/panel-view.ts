// Celý obsah bočního menu bloku z hotových dat: blok z Desktop v3, karta ze snímku agent-state, stopa
// práce z `card-trail`. Rodič (zásuvka v App) jen načte data a předá je sem; dílky dostanou hotové props.
import type { CardEntry } from "@/hub/oporahub-card-drawer/logic/card-header";
import { changeWhen, orderBadge } from "@/editor/canvas/card-face/logic/face-change";
import type { Block } from "@/shared/desktop-state/logic/types";
import type { GraphEdge } from "@/shared/types/logic/types";
import type { CardTrail, TrailJudgment } from "./card-trail";
import { judgmentView, portViews, workView, type JudgmentView, type PortView, type WorkView } from "./panel-work";
import { groupByDay, nowLine, timeline, TRAIL_SETTINGS, whoName, type TimelineGroup, type TrailSettings } from "./trail-timeline";

export type PanelView = {
  head: { number: string; blockId: string; title: string; text: string; cardName: string; order: string | null;
    change: { who: string; whoKind: string; when: string; what: string } | null };
  work: WorkView; live: { text: string; at: string } | null; judgments: TrailJudgment[]; judgmentViews: JudgmentView[];
  timeline: TimelineGroup[]; filesKnown: boolean; ports: PortView[];
};

/** Poslední viditelná změna karty („kdo · kdy · co“) ze stopy; `tool.use` je „teď“, ne změna. */
function lastChange(trail: CardTrail | null, now: Date): PanelView["head"]["change"] {
  const latest = trail?.recent.find((item) => item.kind !== "tool.use");
  if (!latest) return null;
  const who = whoName(latest.who);
  return { who: who.name, whoKind: who.kind, when: changeWhen(latest.at, now), what: latest.label || latest.kind };
}

export function panelView(input: {
  block: Block; blocks: Block[]; cardName: string; card: CardEntry | null; trail: CardTrail | null; edges: GraphEdge[];
  settings?: TrailSettings; now?: Date;
}): PanelView {
  const { block, trail } = input;
  const now = input.now ?? new Date();
  const judgments = trail?.judgment ?? [];
  return {
    head: { number: block.number, blockId: block.id, title: block.title, text: block.text, cardName: input.cardName,
      order: orderBadge(input.card?.order), change: lastChange(trail, now) },
    work: workView(input.card, trail),
    live: trail ? nowLine(trail) : null,
    judgments,
    judgmentViews: judgments.map(judgmentView),
    timeline: trail ? groupByDay(timeline(trail, input.settings ?? TRAIL_SETTINGS), now) : [],
    filesKnown: trail?.filesKnown ?? false,
    ports: trail ? portViews(trail.ports, input.edges, input.blocks) : [],
  };
}
