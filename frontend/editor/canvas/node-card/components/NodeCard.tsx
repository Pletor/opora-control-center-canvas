// Rodič karty: skládá hlavu, tělo, bloky obsahu, patu a porty. Děti nic nevědí o plátně ani o stavu; události
// (přejmenování, změna bloku, port bloku, klik na port, klik na štítek) bublají sem a odsud do dat React Flow uzlu.
import { memo } from "react";
import type { Node, NodeProps } from "@xyflow/react";
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
import CardBody, { type RenameHandlers } from "@/editor/canvas/node-card/components/CardBody";
import CardBlocks, { type CardBlockHandlers } from "@/editor/canvas/node-card/components/CardBlocks";
import CardFoot from "@/editor/canvas/node-card/components/CardFoot";
import CardPorts, { type BlockPort } from "@/editor/canvas/node-card/components/CardPorts";
import CardChecklist from "@/editor/canvas/card-checklist/components/CardChecklist";
import type { CardView } from "@/editor/canvas/node-card/logic/card-model";
import "@/editor/canvas/node-card/styles/node-card.css";

export type NodeCardData = {
  /** Kontrolní pás (deset polí ano / ne) ze serveru; chybí = pás se nekreslí. */
  checklist?: import("@/editor/canvas/card-checklist/logic/card-checklist").CheckItem[];
  moved?: boolean;
  inputSecurity?: { enabled: boolean; save: (enabled: boolean) => Promise<boolean> };
  scenario?: { command: string; history?: import("../logic/use-scenario-history").ScenarioHistory; error?: string };
  work?: import("../logic/use-work-overview").WorkRow;
  workCounts?: Record<import("../logic/use-work-overview").WorkStatus, number>;
  realization?: { value?: import("@/shared/types/logic/types").CanvasNode["realization"]; status?: import("../logic/use-source-status").SourceStatus; disabled: boolean; save: (commit: string, prUrl: string) => Promise<void> };
  facts?: ReturnType<typeof import("./CardFacts").resolveFacts>;
  autonomous?: boolean;
  evidence?: import("./CardEvidence").CompletionEvidence;
  saveEvidence?: (value: import("./CardEvidence").CompletionEvidence) => Promise<boolean>;
  sectorProgress?: ReturnType<typeof import("../logic/sector-status").sectorViews>[string];
  completion?: { confirm: () => Promise<boolean>; note?: string; pending: number;
    readiness?: import("../logic/evidence-readiness").EvidenceReadiness; error?: string };
  lease?: import("../logic/use-leases").CardLease;
  releaseLease?: () => Promise<unknown>;
  frontier?: import("../logic/use-frontier").FrontierItem;
  upstream?: { rows: import("../logic/upstream").UpstreamRow[]; open: (id: string) => void };
  assignmentWarning?: { project: string; workspace: string; nodeId: string; resultId: string; source?: "handoff" | "result" };
  usage?: Usage;
  inheritedRules?: EffectiveRule[];
  rules?: { items: Rule[]; write: (expected: Rule, item: Rule) => Promise<boolean>;
    review: (rule: Rule, decision: import("@/shared/desktop-state/logic/agent-rule").RuleReviewDecision) => Promise<boolean> };
  source?: { source: SourceRef; project: string; workspace: string };
  view: CardView;
  rename: RenameHandlers;
  ports: { open: BlockPort[]; toggle: (port: BlockPort) => void };
  /** Bloky obsahu v kartě i jejich porty: přidat / posunout / odebrat / přejmenovat / upravit text; ukládá rodič (App). */
  blocks: CardBlockHandlers & { disabled: boolean };
  /** Filtr štítků: karta bez vybraného štítku je ztlumená. */
  dimmed: boolean;
  onTag: (tag: string) => void;
  /** Id bloku vybraného na plátně (jen pro vybraný uzel); zvýrazní jeho rámeček v kartě. */
  selectedBlockId?: string;
};

const NodeCard = memo(function NodeCard({ id, data, selected }: NodeProps<Node<NodeCardData>>) {
  const { view, rename, ports, blocks, dimmed, onTag, selectedBlockId } = data;
  return (
    <div
      className={
        "node-card" + (data.frontier ? " node-card--frontier-" + data.frontier.status : "") +
        (data.work ? " node-card--work-" + data.work.status : "") +
        (data.moved ? " node-card__added-pulse" : "") +
        (view.kind === "sector" ? " node-card--sector" : "") +
        (selected ? " node-card--selected" : " node-card--compact") +
        (dimmed ? " node-card--dimmed" : "") +
        (view.closed ? " node-card--closed" : "") +
        (view.doneProposed ? " node-card--proposed" : "")
        + (data.realization?.status?.status === "missing" ? " node-card--source-missing" : "")
      }
      data-testid={"node-card-" + id}
    >
      <CardHead view={view} />
      <CardBody id={id} name={view.name} purpose={view.purpose} rename={rename} />
      {data.checklist && <CardChecklist items={data.checklist} />}
      {/* Přepínače a editory jen u vybrané karty (nebo když jsou zapnuté): plátno zůstane čitelné. */}
      {data.inputSecurity && (selected || data.inputSecurity.enabled) && <InputSecurity {...data.inputSecurity} disabled={blocks.disabled} />}
      {data.scenario && <CardScenario {...data.scenario} />}
      {selected && data.work && <details className="nodrag nopan" style={{ padding: "6px 12px" }}><summary>{data.work.status === "claimed" ? "🔵 " : data.work.status === "done" ? "✓ " : ""}{workLabels[data.work.status]}{data.work.status === "claimed" ? ` · ${data.work.agent}` : ""}</summary><WorkDetails row={data.work} /></details>}
      {data.workCounts && <WorkProgress counts={data.workCounts} />}
      {/* Podrobnosti (fakta, kontroly, důkazy, vychází z, zdroj, pravidla) má nevybraná karta v kontrolním pásu;
          rozepsané jsou u vybrané karty a v panelu detailu. */}
      {selected && data.facts && <CardFacts facts={data.facts} />}
      {selected && <CardChecks checks={view.checks} goal_mode={view.goal_mode} evidence={data.evidence} />}
      {selected && <CardEvidence evidence={data.evidence} autonomous={data.autonomous} />}
      {selected && data.saveEvidence && <div className="nodrag nopan"><EvidenceEditor nodeId={id} evidence={data.evidence} disabled={blocks.disabled} save={data.saveEvidence} /></div>}
      {data.sectorProgress && <SectorProgress value={data.sectorProgress} />}
      {view.doneProposed && data.completion && <ConfirmProposal confirm={data.completion.confirm} note={data.completion.note} readiness={data.completion.readiness} serverError={data.completion.error} disabled={blocks.disabled} />}
      {view.kind === "sector" && !!data.completion?.pending && <div style={{ padding: "6px 12px" }}>Ke schválení: {data.completion.pending}</div>}
      {data.lease && <CardLease lease={data.lease} release={data.releaseLease} />}
      {/* Stav frontier a práce nese barva rámečku; vypsané důvody jen u vybrané karty. */}
      {selected && data.frontier && <CardFrontier item={data.frontier} />}
      {selected && data.upstream && <CardUpstream {...data.upstream} />}
      {data.assignmentWarning && <AssignmentWarning key={JSON.stringify(data.assignmentWarning)} {...data.assignmentWarning} />}
      {view.design && <CardDesign key={JSON.stringify(view.design)} design={view.design} />}
      {(selected || data.usage?.tokens != null || data.usage?.durationMs != null) && <CardUsage usage={data.usage} sector={view.kind === "sector"} />}
      {selected && !!data.inheritedRules?.length && <InheritedRules rules={data.inheritedRules} />}
      {selected && data.rules && data.rules.items.length > 0 && <CardRules rules={data.rules.items} write={data.rules.write} review={data.rules.review} disabled={blocks.disabled} />}
      {selected && data.source && <CardSource key={JSON.stringify(data.source)} {...data.source} />}
      {selected && data.realization && <SourceRealization key={JSON.stringify(data.realization.value)} nodeId={id} {...data.realization} mergePassed={data.evidence?.merge.status === "passed"} />}
      <CardBlocks id={id} rows={view.rows} disabled={blocks.disabled} handlers={blocks} selectedBlockId={selectedBlockId} />
      <CardFoot view={view} onTag={onTag} />
      <CardPorts id={id} open={ports.open} onToggle={ports.toggle} />
    </div>
  );
});

export default NodeCard;
