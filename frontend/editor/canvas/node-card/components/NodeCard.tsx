// Rodič karty: skládá hlavu, tělo, bloky obsahu, patu a porty. Děti nic nevědí o plátně ani o stavu; události
// (přejmenování, změna bloku, port bloku, klik na port, klik na štítek) bublají sem a odsud přes kontext akcí
// (`logic/card-actions.ts`) do Boardu. `data` nenese žádnou funkci, takže `memo` kartu opravdu přeskočí, když
// se její data nezměnila (docs/navrhy/2026-10-14-vykon-platna.md, oprava 3). Při oddálení plátna pod práh
// (`logic/card-lod.ts`, oprava 4) kreslí nevybraná karta jen hlavu, název, stav a úchyty.
import { memo, useMemo } from "react";
import { useStore, type Node, type NodeProps } from "@xyflow/react";
import CardHead from "@/editor/canvas/node-card/components/CardHead";
import CardSource from "./CardSource";
import CardRules from "./CardRules";
import InheritedRules from "./InheritedRules";
import CardUsage from "./CardUsage";
import CardDesign from "./CardDesign";
import AssignmentWarning from "./AssignmentWarning";
import CardUpstream from "./CardUpstream";
import CardFrontier from "./CardFrontier";
import CardLease from "./CardLease";
import ConfirmProposal from "./ConfirmProposal";
import SectorProgress from "./SectorProgress";
import CardEvidence from "./CardEvidence";
import CardChecks from "./CardChecks";
import CardFacts from "./CardFacts";
import SourceRealization from "./SourceRealization";
import CardScenario from "./CardScenario";
import InputSecurity from "./InputSecurity";
import { WorkDetails, WorkProgress, workLabels } from "./WorkNow";
import EvidenceEditor from "./EvidenceEditor";
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
import CardChecklist from "@/editor/canvas/card-checklist/components/CardChecklist";
import type { CardView } from "@/editor/canvas/node-card/logic/card-model";
import { useCardActions, type CardActions } from "@/editor/canvas/node-card/logic/card-actions";
import { cardDetail, farZoomSelector, type CardDetail } from "@/editor/canvas/node-card/logic/card-lod";
import "@/editor/canvas/node-card/styles/node-card.css";

/** Data karty: jen hodnoty (žádné funkce), aby šla porovnat se starou verzí (board/logic/stable-nodes.ts). */
export type NodeCardData = {
  /** Proces karty (pipeline etap) jako řada kuliček; jen uzel, sektor pipeline nemá. */
  process?: CardProcessView;
  /** Kontrolní pás (deset polí ano / ne) ze serveru; chybí = pás se nekreslí. */
  checklist?: import("@/editor/canvas/card-checklist/logic/card-checklist").CheckItem[];
  moved?: boolean;
  inputSecurity?: { enabled: boolean };
  scenario?: { command: string; history?: import("../logic/use-scenario-history").ScenarioHistory; error?: string };
  work?: import("../logic/use-work-overview").WorkRow;
  workCounts?: Record<import("../logic/use-work-overview").WorkStatus, number>;
  realization?: { value?: import("@/shared/types/logic/types").CanvasNode["realization"]; status?: import("../logic/use-source-status").SourceStatus; disabled: boolean };
  facts?: ReturnType<typeof import("./CardFacts").resolveFacts>;
  autonomous?: boolean;
  evidence?: import("./CardEvidence").CompletionEvidence;
  /** Rodič umí uložit důkazy: vybraná karta ukáže jejich editor. */
  saveEvidence?: boolean;
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
      saveEvidence: (value: import("./CardEvidence").CompletionEvidence) => actions.saveEvidence(id, value),
      confirm: () => actions.confirm(id),
      urlDownload: (enabled: boolean) => actions.urlDownload(id, enabled),
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
  return (
    <div
      className={
        "node-card" + (data.frontier ? " node-card--frontier-" + data.frontier.status : "") +
        (data.work ? " node-card--work-" + data.work.status : "") +
        (data.moved ? " node-card__added-pulse" : "") +
        (view.kind === "sector" ? " node-card--sector" : "") +
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
      {data.process && <CardProcess view={data.process} detail={full ? "full" : "far"} kind={view.kind} />}
      {full && data.checklist && <CardChecklist items={data.checklist} />}
      {/* Přepínače a editory jen u vybrané karty (nebo když jsou zapnuté): plátno zůstane čitelné. */}
      {full && data.inputSecurity && (selected || data.inputSecurity.enabled) && <InputSecurity {...data.inputSecurity} save={on.urlDownload} disabled={blocks.disabled} />}
      {full && data.scenario && <CardScenario {...data.scenario} />}
      {selected && data.work && <details className="nodrag nopan" style={{ padding: "6px 12px" }}><summary>{data.work.status === "claimed" ? "🔵 " : data.work.status === "done" ? "✓ " : ""}{workLabels[data.work.status]}{data.work.status === "claimed" ? ` · ${data.work.agent}` : ""}</summary><WorkDetails row={data.work} /></details>}
      {full && data.workCounts && <WorkProgress counts={data.workCounts} />}
      {/* Podrobnosti (fakta, kontroly, důkazy, vychází z, zdroj, pravidla) má nevybraná karta v kontrolním pásu;
          rozepsané jsou u vybrané karty a v panelu detailu. */}
      {selected && data.facts && <CardFacts facts={data.facts} />}
      {selected && <CardChecks checks={view.checks} goal_mode={view.goal_mode} evidence={data.evidence} />}
      {selected && <CardEvidence evidence={data.evidence} autonomous={data.autonomous} />}
      {selected && data.saveEvidence && <div className="nodrag nopan"><EvidenceEditor nodeId={id} evidence={data.evidence} disabled={blocks.disabled} save={on.saveEvidence} /></div>}
      {full && data.sectorProgress && <SectorProgress value={data.sectorProgress} />}
      {full && view.doneProposed && data.completion && <ConfirmProposal confirm={on.confirm} note={data.completion.note} readiness={data.completion.readiness} serverError={data.completion.error} disabled={blocks.disabled} />}
      {full && view.kind === "sector" && !!data.completion?.pending && <div style={{ padding: "6px 12px" }}>Ke schválení: {data.completion.pending}</div>}
      {full && data.lease && <CardLease lease={data.lease} release={data.releaseLease ? on.release : undefined} />}
      {/* Stav frontier a práce nese barva rámečku; vypsané důvody jen u vybrané karty. */}
      {selected && data.frontier && <CardFrontier item={data.frontier} />}
      {selected && data.upstream && <CardUpstream rows={data.upstream.rows} open={actions.open} />}
      {full && data.assignmentWarning && <AssignmentWarning key={JSON.stringify(data.assignmentWarning)} {...data.assignmentWarning} />}
      {full && view.design && <CardDesign key={JSON.stringify(view.design)} design={view.design} />}
      {full && (selected || data.usage?.tokens != null || data.usage?.durationMs != null) && <CardUsage usage={data.usage} sector={view.kind === "sector"} />}
      {selected && !!data.inheritedRules?.length && <InheritedRules rules={data.inheritedRules} />}
      {selected && data.rules && data.rules.items.length > 0 && <CardRules rules={data.rules.items} write={actions.ruleWrite} review={actions.ruleReview} disabled={blocks.disabled} />}
      {selected && data.source && <CardSource key={JSON.stringify(data.source)} {...data.source} />}
      {selected && data.realization && <SourceRealization key={JSON.stringify(data.realization.value)} nodeId={id} {...data.realization} save={on.realize} mergePassed={data.evidence?.merge.status === "passed"} />}
      <CardBlocks id={id} rows={view.rows} disabled={blocks.disabled} handlers={on.blocks} selectedBlockId={selectedBlockId} selected={selected} detail={detail} />
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
