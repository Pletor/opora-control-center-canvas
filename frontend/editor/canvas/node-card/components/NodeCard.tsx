import { memo } from "react";
import type { Node, NodeProps } from "@xyflow/react";
import CardHead from "@/editor/canvas/node-card/components/CardHead";
import type { CardBlockHandlers } from "@/editor/canvas/node-card/components/CardBlocks";
import CardPorts, { type BlockPort } from "@/editor/canvas/node-card/components/CardPorts";
import CardChecklist from "@/editor/canvas/card-checklist/components/CardChecklist";
import CardDnaCompactBlocks from "@/editor/card-dna/components/CardDnaCompactBlocks";
import CardDnaCompactIndicators from "@/editor/card-dna/components/CardDnaCompactIndicators";
import type { CardView } from "@/editor/canvas/node-card/logic/card-model";
import type { Usage } from "../logic/use-usage";
import type { EffectiveRule } from "../logic/effective-rules";
import type { Rule } from "@/shared/desktop-state/logic/types";
import type { SourceRef } from "@/shared/types/logic/types";
import "@/editor/canvas/node-card/styles/node-card.css";

export type NodeCardData = {
  sourceStatus?: import("../logic/use-source-status").SourceStatus;
  assignmentStatus?: import("@/editor/card-dna/logic/card-status").AssignmentStatus;
  checklist?: import("@/editor/canvas/card-checklist/logic/card-checklist").CheckItem[];
  moved?: boolean; inputSecurity?: { enabled: boolean; save: (enabled: boolean) => Promise<boolean> }; scenario?: { command: string; history?: import("../logic/use-scenario-history").ScenarioHistory; error?: string }; work?: import("../logic/use-work-overview").WorkRow;
  workCounts?: Record<import("../logic/use-work-overview").WorkStatus, number>; sectorProgress?: ReturnType<typeof import("../logic/sector-status").sectorViews>[string];
  realization?: { value?: import("@/shared/types/logic/types").CanvasNode["realization"]; status?: import("../logic/use-source-status").SourceStatus; disabled: boolean; save: (commit: string, prUrl: string) => Promise<void> };
  facts?: ReturnType<typeof import("./CardFacts").resolveFacts>; autonomous?: boolean; evidence?: import("./CardEvidence").CompletionEvidence; saveEvidence?: (value: import("./CardEvidence").CompletionEvidence) => Promise<boolean>;
  completion?: { confirm: () => Promise<boolean>; note?: string; pending: number; readiness?: import("../logic/evidence-readiness").EvidenceReadiness; error?: string }; lease?: import("../logic/use-leases").CardLease;
  releaseLease?: () => Promise<unknown>; assignmentWarning?: { project: string; workspace: string; nodeId: string; resultId: string; source?: "handoff" | "result" };
  pipeline?: { finished: number; total: number; failed: number };
  frontier?: import("../logic/use-frontier").FrontierItem; upstream?: { rows: import("../logic/upstream").UpstreamRow[]; open: (id: string) => void };
  usage?: Usage; inheritedRules?: EffectiveRule[]; rules?: { items: Rule[]; write: (expected: Rule, item: Rule) => Promise<boolean> };
  source?: { source: SourceRef; project: string; workspace: string }; view: CardView;
  rename: import("@/editor/canvas/node-card/components/CardBody").RenameHandlers;
  ports: { open: BlockPort[]; toggle: (port: BlockPort) => void };
  blocks: CardBlockHandlers & { disabled: boolean }; dimmed: boolean; onTag: (tag: string) => void; selectedBlockId?: string;
};

/** Lehký obraz uzlu: žádné editory; čas lease jde z jediného tickeru a detail otevírá DNA dialog Boardu. */
const NodeCard = memo(function NodeCard({ id, data }: NodeProps<Node<NodeCardData>>) {
  const { view, ports, dimmed, selectedBlockId } = data;
  return <div className={"node-card node-card--compact" + (data.moved ? " node-card__added-pulse" : "") + (view.kind === "sector" ? " node-card--sector" : "") + (dimmed ? " node-card--dimmed" : "") + (view.closed ? " node-card--closed" : "")} data-testid={`node-card-${id}`}>
    <CardHead view={view} />
    <div className="node-card__body"><h3 className="node-card__title" title={view.name}>{view.name}</h3></div>
    {data.checklist && <CardChecklist items={data.checklist} />}
    <CardDnaCompactIndicators pipeline={data.pipeline} view={view} evidence={data.evidence} lease={data.lease} assignmentChanged={!!data.assignmentWarning} commit={data.realization?.value?.commit} tokens={data.usage?.tokens} />
    <CardDnaCompactBlocks id={id} rows={view.rows} selectedBlockId={selectedBlockId} />
    <CardPorts id={id} open={ports.open} onToggle={ports.toggle} />
  </div>;
});
export default NodeCard;
