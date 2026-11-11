// Uzly jedné vrstvy plátna jako čistá data (docs/navrhy/2026-10-14-vykon-platna.md, oprava 3). Board sem
// předá graf, stav, výběr a overlaye z pollingu a dostane uzly React Flow bez jediné funkce v `data`:
// akce karty jdou přes kontext (`node-card/logic/card-actions.ts`). Díky tomu jde porovnat novou kartu
// se starou (`stable-nodes.ts`) a nezměněnou kartu nepřekreslit.
import type { Node } from "@xyflow/react";
import type { Graph } from "@/shared/types/logic/types";
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import { nodeWorkflowOf } from "@/shared/desktop-state/logic/types";
import { childCount, ownNodeRules, type BoardIndex } from "@/editor/canvas/board/logic/board-index";
import type { NodeCardData } from "@/editor/canvas/node-card/components/NodeCard";
import type { CommentCardData } from "@/editor/canvas/comment-card/components/CommentCard";
import type { AreaCardData } from "@/editor/canvas/area/components/AreaCard";
import { upstreamRows } from "@/editor/canvas/node-card/logic/upstream";
import { areaSummary, type Checklists } from "@/editor/canvas/card-checklist/logic/card-checklist";
import { effectiveRules } from "@/editor/canvas/node-card/logic/effective-rules";
import { cardView, matchesTagFilter } from "@/editor/canvas/node-card/logic/card-model";
import { cardFace } from "@/editor/canvas/card-face/logic/card-face";
import { faceKind } from "@/editor/canvas/card-face/logic/face-family";
import { effectiveType } from "@/shared/card-context/logic/card-context";
import type { AgentCardStage, AgentDecision } from "@/hub/oporahub-agent-state/logic/agent-state";
import { commentView } from "@/editor/canvas/comment-card/logic/comment-model";
import { areaColorOf, areaLabel, membersOf } from "@/editor/canvas/area/logic/area-model";
import type { OpenBlocks } from "@/editor/workflow/blocks/logic/block-model";
import type { FrontierItem } from "@/editor/canvas/node-card/logic/use-frontier";
import type { WorkOverview } from "@/editor/canvas/node-card/logic/use-work-overview";
import type { CardLease } from "@/editor/canvas/node-card/logic/use-leases";
import type { SourceStatus } from "@/editor/canvas/node-card/logic/use-source-status";

/**
 * Kreslit jen viditelné uzly (oprava 5 v docs/navrhy/2026-10-14-vykon-platna.md) je zapnuté. Karta mimo
 * obraz se odmontuje bez `blur`; rozepsaný popis, název bloku i popisek portu proto žijí v úložišti draftů
 * (`node-card/logic/block-drafts.ts`, klíč karta + blok + pole, s uloženým základem), odkud je karta po
 * návratu převezme. Odmontování nic neukládá, ukládá dál jen rodič po blur. Nezměřená karta mimo obraz
 * dostane pro „Srovnat“ i dosednutí tahu odhad výšky (`layerFootprints(..., estimate=true)`).
 */
export const CULL_VISIBLE = true;
/** Od kolika uzlů ve vrstvě plátno kreslí jen viditelné; malé plátno by na tom jen tratilo. */
export const CULL_FROM = 80;
export const shouldCull = (count: number) => CULL_VISIBLE && count >= CULL_FROM;

export type LayerInput = {
  graph: Graph;
  state: DesktopState;
  index: BoardIndex;
  parent: string | null;
  selected: string | null;
  multiSelected: ReadonlySet<string>;
  selectedBlock: string | null;
  editing: string | null;
  disabled: boolean;
  openBlocks: OpenBlocks;
  tagFilter: string;
  moved: ReadonlySet<string>;
  checklists?: Checklists;
  frontier?: Record<string, FrontierItem>;
  work?: { data?: WorkOverview } | null;
  leases?: Record<string, CardLease>;
  sourceStatuses?: Record<string, SourceStatus>;
  /** Snímek agent-state: tvář každé karty (`cards[]`) a rozhodnutí člověka (`decisions[]`). */
  agent?: { cards: ReadonlyMap<string, AgentCardStage>; decisions: readonly AgentDecision[] };
  sourceContext?: { project: string; workspace: string };
  /** Aktivní milníky z příjmu (`milestone-focus`): název funkčního výsledku jde do hlavičky jejich oblasti. */
  milestones?: readonly { areaId: string; title: string }[];
  /** Které akce rodič vůbec umí; karta podle toho ukáže editor, nebo ne. */
  can: { realize: boolean; rules: boolean };
};

/** Klíč pulsu přesunuté karty (`useAddedPulse` nad pozicemi). */
export const movedKey = (n: Pick<Graph["nodes"][number], "id" | "parentId" | "x" | "y">) => `${n.id}:${n.parentId}:${n.x}:${n.y}`;

export function buildLayerNodes(input: LayerInput): Node[] {
  const { graph, state, index, parent, selected, multiSelected, disabled, can, sourceContext } = input;
  const isSelected = (id: string) => id === selected || multiSelected.has(id);
  const out: Node[] = [];
  for (const n of graph.nodes) {
    if (n.parentId !== parent) continue;
    if (n.kind === "comment") {
      const data: CommentCardData = { view: commentView(n), disabled };
      out.push({ id: n.id, type: "comment", position: { x: n.x, y: n.y }, selected: isSelected(n.id), connectable: false, data });
      continue;
    }
    if (n.kind === "area") {
      const size = n.size ?? { w: 720, h: 480 };
      const members = membersOf(n, graph.nodes);
      const data: AreaCardData = {
        view: { label: areaLabel(n), unnamed: !n.name.trim(), members: members.length, w: size.w, h: size.h, color: areaColorOf(n),
          purpose: n.purpose, milestone: input.milestones?.find((m) => m.areaId === n.id)?.title ?? "", sectors: members.filter((m) => m.kind === "sector").length,
          closed: members.filter((m) => state.nodes[m.id]?.done?.confirmed).length,
          summary: input.checklists ? areaSummary(members.flatMap((m) => input.checklists?.[m.id] ? [input.checklists[m.id]] : [])) : undefined },
        disabled,
      };
      // Oblast musí zůstat pod kartami vždy, i vybraná — proto vlastní z-index i mimo CSS.
      out.push({ id: n.id, type: "area", position: { x: n.x, y: n.y }, selected: isSelected(n.id), zIndex: -1,
        style: { width: size.w, height: size.h }, data });
      continue;
    }
    const workflow = nodeWorkflowOf(state, n.id);
    const view = cardView(n, workflow, childCount(index, n.id));
    const own = state.nodes[n.id];
    const face = cardFace({ nodeId: n.id, card: input.agent?.cards.get(n.id), sector: n.kind === "sector", layer: view.cardLayer ?? undefined,
      decisions: input.agent?.decisions ?? [], nameOf: (id) => index.byId.get(id)?.name ?? id });
    const data: NodeCardData = {
      view,
      face,
      kind: faceKind({ nodeId: n.id, type: effectiveType(n), element: n.element?.kind, sector: n.kind === "sector", order: input.agent?.cards.get(n.id)?.order }),
      upstream: { rows: upstreamRows(graph, state, n.id, index) },
      frontier: input.frontier?.[n.id],
      evidence: own?.evidence,
      work: input.work?.data?.nodes[n.id],
      moved: input.moved.has(movedKey(n)),
      realization: n.sourceRef && can.realize ? { value: n.realization, status: input.sourceStatuses?.[n.id], disabled } : undefined,
      autonomous: own?.done?.by === "autonomy" && own?.done?.confirmed,
      lease: input.leases?.[n.id],
      releaseLease: !!input.leases?.[n.id] && !!sourceContext,
      inheritedRules: effectiveRules(graph, state, n.id, index).filter((rule) => rule.inherited || rule.origin.storage === "node" || !can.rules),
      rules: can.rules ? { items: ownNodeRules(index, n.id) } : undefined,
      source: n.sourceRef && sourceContext ? { source: n.sourceRef, ...sourceContext } : undefined,
      dimmed: !matchesTagFilter(workflow, input.tagFilter),
      // Vybraný blok patří jen kartě svého uzlu; jinou kartu jeho výběr nezvýrazní.
      selectedBlockId: n.id === selected ? (input.selectedBlock ?? undefined) : undefined,
      ports: { open: input.openBlocks[n.id] ?? [] },
      // Uzavřená karta má bloky i porty jen ke čtení; do hloubky se jít dál smí.
      blocks: { disabled: disabled || view.closed },
      rename: { editing: input.editing === n.id },
    };
    out.push({ id: n.id, type: "canvas", position: { x: n.x, y: n.y }, selected: isSelected(n.id), data });
  }
  return out;
}
