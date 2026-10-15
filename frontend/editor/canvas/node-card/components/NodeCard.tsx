// Rodič karty: skládá pět zón v pevném pořadí (docs/proces-karty.md): hlavu, název s podstatou, proces (kuličky
// etap + sloty dokladů + stavová věta), kontrolní pás, bloky s porty a patu; vybraná karta má navíc jeden fold
// „Podrobnosti“. Děti nic nevědí o plátně ani o stavu; události bublají sem a odsud přes kontext akcí
// (`logic/card-actions.ts`) do Boardu. `data` nenese žádnou funkci, takže `memo` kartu opravdu přeskočí, když
// se její data nezměnila (docs/navrhy/2026-10-14-vykon-platna.md, oprava 3). Při oddálení plátna pod práh
// (`logic/card-lod.ts`, oprava 4) kreslí nevybraná karta jen hlavu, název, kuličky a úchyty.
import { memo, useMemo } from "react";
import { useStore, type Node, type NodeProps } from "@xyflow/react";
import CardHead from "@/editor/canvas/node-card/components/CardHead";
import AssignmentWarning from "./AssignmentWarning";
import SectorProgress from "./SectorProgress";
import CardUsage from "./CardUsage";
import CardDetails from "./CardDetails";
import CardState from "./CardState";
import ConfirmProposal from "./ConfirmProposal";
import { WorkProgress } from "./WorkNow";
import type { Usage } from "../logic/use-usage";
import type { EffectiveRule } from "../logic/effective-rules";
import type { Rule } from "@/shared/desktop-state/logic/types";
import type { SourceRef } from "@/shared/types/logic/types";
import CardBody from "@/editor/canvas/node-card/components/CardBody";
import CardBlocks, { type CardBlockHandlers } from "@/editor/canvas/node-card/components/CardBlocks";
import CardFoot from "@/editor/canvas/node-card/components/CardFoot";
import CardPorts, { type BlockPort } from "@/editor/canvas/node-card/components/CardPorts";
import CardProcess from "@/editor/canvas/node-card/components/CardProcess";
import type { CardProcessView } from "@/editor/canvas/node-card/logic/card-process";
import type { CardStateLine } from "@/editor/canvas/node-card/logic/card-state";
import CardChecklist from "@/editor/canvas/card-checklist/components/CardChecklist";
import type { CardView } from "@/editor/canvas/node-card/logic/card-model";
import { useCardActions, type CardActions } from "@/editor/canvas/node-card/logic/card-actions";
import { cardDetail, farZoomSelector, type CardDetail } from "@/editor/canvas/node-card/logic/card-lod";
import "@/editor/canvas/node-card/styles/node-card.css";

/** Data karty: jen hodnoty (žádné funkce), aby šla porovnat se starou verzí (board/logic/stable-nodes.ts). */
export type NodeCardData = {
  /** Proces karty (pipeline etap + sloty dokladů); jen uzel, sektor pipeline nemá. */
  process?: CardProcessView;
  /** Stavová věta karty (jedna, podle přednosti); jen uzel. */
  state?: CardStateLine;
  /** Kontrolní pás (deset polí ano / ne) ze serveru; chybí = pás se nekreslí. */
  checklist?: import("@/editor/canvas/card-checklist/logic/card-checklist").CheckItem[];
  moved?: boolean;
  work?: import("../logic/use-work-overview").WorkRow;
  workCounts?: Record<import("../logic/use-work-overview").WorkStatus, number>;
  realization?: { value?: import("@/shared/types/logic/types").CanvasNode["realization"]; status?: import("../logic/use-source-status").SourceStatus; disabled: boolean };
  autonomous?: boolean;
  evidence?: import("./CardEvidence").CompletionEvidence;
  sectorProgress?: ReturnType<typeof import("../logic/sector-status").sectorViews>[string];
  completion?: { note?: string; pending: number; readiness?: import("../logic/evidence-readiness").EvidenceReadiness; error?: string };
  lease?: import("../logic/use-leases").CardLease;
  /** Lease jde uvolnit (karta ho má a plátno zná projekt). */
  releaseLease?: boolean;
  frontier?: import("../logic/use-frontier").FrontierItem;
  upstream?: { rows: import("../logic/upstream").UpstreamRow[] };
  assignmentWarning?: { project: string; workspace: string; nodeId: string; resultId: string; source?: "handoff" | "result" };
  usage?: Usage;
  inheritedRules?: EffectiveRule[];
  rules?: { items: Rule[] };
  source?: { source: SourceRef; project: string; workspace: string };
  view: CardView;
  rename: { editing: boolean };
  ports: { open: BlockPort[] };
  /** Bloky obsahu v kartě i jejich porty jsou jen ke čtení (plátno zamčené nebo karta uzavřená). */
  blocks: { disabled: boolean };
  /** Filtr štítků: karta bez vybraného štítku je ztlumená. */
  dimmed: boolean;
  /** Id bloku vybraného na plátně (jen pro vybraný uzel); zvýrazní jeho rámeček v kartě. */
  selectedBlockId?: string;
};

/** Obsluha dílků karty z jednoho stabilního objektu akcí; mění se jen s id karty. */
function useCardHandlers(actions: CardActions, id: string) {
  return useMemo(() => {
    const block = (event: Parameters<CardActions["cardBlock"]>[1]) => actions.cardBlock(id, event);
    const blocks: CardBlockHandlers = {
      add: () => block({ type: "add" }),
      move: (blockId, delta) => block({ type: "move", blockId, delta }),
      remove: (blockId) => block({ type: "remove", blockId }),
      rename: (blockId, title) => block({ type: "rename", blockId, title }),
      text: (blockId, text) => block({ type: "text", blockId, text }),
      addPort: (blockId) => block({ type: "add-port", blockId }),
      renamePort: (blockId, portId, label) => block({ type: "rename-port", blockId, portId, label }),
      removePort: (blockId, portId) => block({ type: "remove-port", blockId, portId }),
      decidePort: (blockId, portId, status, reason) => block({ type: "decide-port", blockId, portId, status, reason }),
      configureSpawn: (blockId, portId, action) => block({ type: "configure-spawn", blockId, portId, action }),
    };
    return {
      blocks,
      rename: { start: () => actions.renameStart(id), cancel: () => actions.renameCancel(id), commit: (name: string) => actions.renameCommit(id, name) },
      toggle: (port: BlockPort) => actions.togglePort(id, port),
      confirm: () => actions.confirm(id),
      realize: (commit: string, prUrl: string) => actions.realize(id, commit, prUrl),
      release: () => actions.releaseLease(id),
    };
  }, [actions, id]);
}

/** Karta bez napojení na React Flow store: detail dostává zvenku (testy, měření). */
export function NodeCardView({ id, data, selected, detail }: { id: string; data: NodeCardData; selected: boolean; detail: CardDetail }) {
  const actions = useCardActions();
  const on = useCardHandlers(actions, id);
  const { view, blocks, dimmed, selectedBlockId } = data;
  const full = detail === "full";
  const sector = view.kind === "sector";
  return (
    <div
      className={
        "node-card" + (data.frontier ? " node-card--frontier-" + data.frontier.status : "") +
        (data.work ? " node-card--work-" + data.work.status : "") +
        (data.moved ? " node-card__added-pulse" : "") +
        (sector ? " node-card--sector" : "") +
        (selected ? " node-card--selected" : " node-card--compact") +
        (full ? "" : " node-card--far") +
        (dimmed ? " node-card--dimmed" : "") +
        (view.closed ? " node-card--closed" : "") +
        (view.doneProposed ? " node-card--proposed" : "")
        + (data.realization?.status?.status === "missing" ? " node-card--source-missing" : "")
      }
      data-testid={"node-card-" + id}
      data-detail={detail}
    >
      <CardHead view={view} />
      <CardBody id={id} name={view.name} purpose={view.purpose} rename={{ ...on.rename, editing: data.rename.editing }} />
      {data.process && <CardProcess view={data.process} detail={full ? "full" : "far"} />}
      {data.state && (full
        ? <CardState line={data.state} completion={data.completion} confirm={data.completion ? on.confirm : undefined} disabled={blocks.disabled} />
        : data.state.tone === "warn" && <span className="node-card__state-far" role="status" title={data.state.text}>◷</span>)}
      {full && data.checklist && <CardChecklist items={data.checklist} />}
      {full && data.assignmentWarning && <AssignmentWarning key={JSON.stringify(data.assignmentWarning)} {...data.assignmentWarning} />}
      {/* Sektor: pruh stavů jeho karet, postup k bráně a počet návrhů ke schválení. */}
      {full && sector && data.workCounts && <WorkProgress counts={data.workCounts} />}
      {full && sector && data.sectorProgress && <SectorProgress value={data.sectorProgress} />}
      {full && sector && !!data.completion?.pending && <div className="node-card__row">Ke schválení: {data.completion.pending}</div>}
      {full && sector && view.doneProposed && data.completion && <ConfirmProposal confirm={on.confirm} note={data.completion.note} readiness={data.completion.readiness} serverError={data.completion.error} disabled={blocks.disabled} />}
      {full && sector && !selected && (data.usage?.tokens != null || data.usage?.durationMs != null) && <CardUsage usage={data.usage} sector />}
      <CardBlocks id={id} rows={view.rows} disabled={blocks.disabled} handlers={on.blocks} selectedBlockId={selectedBlockId} selected={selected} detail={detail} />
      {selected && <CardDetails id={id} data={data} actions={actions} release={data.releaseLease ? on.release : undefined} realize={on.realize} />}
      {full && <CardFoot view={view} onTag={actions.tag} />}
      <CardPorts id={id} open={data.ports.open} onToggle={on.toggle} />
    </div>
  );
}

const NodeCard = memo(function NodeCard({ id, data, selected }: NodeProps<Node<NodeCardData>>) {
  // Jediný boolean ze store: karta se překreslí jen při překročení prahu, ne v každém snímku zoomu.
  const far = useStore(farZoomSelector);
  return <NodeCardView id={id} data={data} selected={!!selected} detail={cardDetail(far, !!selected)} />;
});

export default NodeCard;
