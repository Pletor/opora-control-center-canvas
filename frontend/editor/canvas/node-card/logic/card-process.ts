// Proces karty jako řada kuliček: čistý pohled na pipeline etap (docs/karta-pro-agenty.md, „Pipeline karty“).
// Co je na řadě a kde proces uvízl, počítá `pipelineSummary` z pipeline-model; tady se jen překládá do kuliček.
// Výstup jsou čistá data (žádné funkce ani Date), aby je `stable-nodes.ts` mohl porovnat hluboce.
import {
  KIND_LABEL, LENS_LABEL, PROFILE_LABEL, STATUS_LABEL, pipelineSummary,
  type CardPipeline, type CriticLens, type PipelineProfile, type StageKind, type StageStatus,
} from "@/editor/workflow/card-pipeline/logic/pipeline-model";

export type ProcessDot = {
  id: string;
  kind: StageKind;
  lens: CriticLens | "";
  status: StageStatus;
  /** Etapa, na které proces právě stojí. */
  current: boolean;
  /** Selhaná etapa bez dalšího pokusu: autonomní smyčka došla, čeká člověk. */
  stuck: boolean;
  /** Opakování dřívější selhané etapy. */
  retry: boolean;
  title: string;
  note: string;
  doneBy: string;
};

export type CardProcessView = {
  routed: boolean;
  profile: PipelineProfile;
  profileLabel: string;
  dots: ProcessDot[];
  finished: number;
  total: number;
  waitingOnHuman: boolean;
  /** Etapy navržené agentem, které člověk ještě neschválil; kuličky nemají, jen tichý počet. */
  proposed: number;
};

/** Pohled na proces karty; `undefined`, když karta pipeline vůbec nemá. Bez schválených etap = nenasměrovaná.
 *  Kuličky staví ze stejné množiny jako `pipelineSummary` (jen schválené etapy), aby čísla seděla s řadou. */
export function processView(pipeline: CardPipeline | undefined): CardProcessView | undefined {
  if (!pipeline) return undefined;
  const summary = pipelineSummary(pipeline);
  const stuck = new Set(summary.stuck.map((s) => s.id));
  const active = pipeline.items.filter((s) => s.approved);
  const dots = active.map((s): ProcessDot => ({
    id: s.id, kind: s.kind, lens: s.lens, status: s.status,
    current: summary.current?.id === s.id,
    stuck: stuck.has(s.id),
    retry: !!s.retryOf,
    title: s.title, note: s.note, doneBy: s.doneBy,
  }));
  return {
    routed: dots.length > 0,
    profile: pipeline.profile,
    profileLabel: PROFILE_LABEL[pipeline.profile],
    dots,
    finished: summary.finished,
    total: summary.total,
    waitingOnHuman: stuck.size > 0,
    proposed: pipeline.items.length - active.length,
  };
}

const who = (dot: ProcessDot) => {
  const kind = KIND_LABEL[dot.kind];
  return kind.charAt(0).toUpperCase() + kind.slice(1) + (dot.lens ? ": " + LENS_LABEL[dot.lens] : "");
};

/** Textový ekvivalent řady pro čtečku: „Proces: 3/6, na řadě Kritik: hacker, 1 selhalo“. */
export function processSentence(view: CardProcessView): string {
  if (!view.routed) return "Proces: čeká na router" + (view.proposed ? ", " + view.proposed + " ke schválení" : "");
  const parts = ["Proces: " + view.finished + "/" + view.total];
  const current = view.dots.find((d) => d.current);
  if (current) parts.push("na řadě " + who(current));
  const stuck = view.dots.filter((d) => d.stuck).length;
  if (stuck) parts.push(stuck + " selhalo, čeká na člověka");
  if (view.proposed) parts.push(view.proposed + " ke schválení");
  return parts.join(", ");
}

/** Text tooltipu kuličky: „Kritik: hacker · selhalo · poznámka“. */
export function DOT_TITLE(dot: ProcessDot): string {
  const parts = [who(dot)];
  if (dot.title) parts.push(dot.title);
  parts.push(STATUS_LABEL[dot.status]);
  if (dot.retry) parts.push("↺ opakování");
  if (dot.current) parts.push("na řadě");
  if (dot.stuck) parts.push("čeká na člověka");
  if (dot.doneBy) parts.push(dot.doneBy);
  if (dot.note) parts.push(dot.note);
  return parts.join(" · ");
}
