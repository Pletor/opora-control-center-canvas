import type { NodeCardData } from "@/editor/canvas/node-card/components/NodeCard";
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import type { CheckKey } from "@/editor/canvas/card-checklist/logic/card-checklist";
import ConfirmProposal from "@/editor/canvas/node-card/components/ConfirmProposal";
import CardFrontier from "@/editor/canvas/node-card/components/CardFrontier";
import CardLease from "@/editor/canvas/node-card/components/CardLease";
import CardUsage from "@/editor/canvas/node-card/components/CardUsage";
import CardFoot from "@/editor/canvas/node-card/components/CardFoot";
import InputSecurity from "@/editor/canvas/node-card/components/InputSecurity";
import SectorProgress from "@/editor/canvas/node-card/components/SectorProgress";
import { WorkDetails, WorkProgress } from "@/editor/canvas/node-card/components/WorkNow";
import { pipelineOf, pipelineSummary } from "@/editor/workflow/card-pipeline/logic/pipeline-model";
import type { CardDnaTab } from "./CardDnaDialog";

const targets: Record<CheckKey, CardDnaTab> = { goal: "spec", done: "spec", text: "spec", blocks: "spec", links: "workflow", source: "code", checks: "evidence", pipeline: "workflow", evidence: "evidence", handoff: "process" };
const labels: Record<CardDnaTab, string> = { overview: "Přehled", spec: "Zadání", process: "Proces", workflow: "Pipeline a workflow", evidence: "Důkazy a kontroly", code: "Kód a verze", dna: "DNA" };
/** Člověk nejprve vidí cíl a konkrétní požadavky; detaily práce jsou až pod nimi. */
export default function CardDnaOverview({ nodeId, data, state, onTab }: {
  nodeId: string; data: NodeCardData; state: DesktopState; onTab: (tab: CardDnaTab) => void;
}) {
  const wants = data.view.waitingOnHuman;
  const missing = data.checklist?.filter(item => item.state !== "yes") ?? [];
  const pipeline = pipelineSummary(pipelineOf(state, nodeId));
  return <>
    <h3>{data.view.name}</h3><p>{data.view.purpose || "Cíl zatím není popsán."}</p>
    <p>Stav: {data.work?.status ?? data.view.cardStatus ?? data.view.phaseLabel ?? "nezaznamenán"}</p>
    <h3>Co po tobě chci</h3>
    {!missing.length && !wants.length && <p>Žádná otevřená výzva.</p>}
    <ul className="card-dna__requests">{missing.map(item => <li key={item.key}>
      <strong>{item.label}</strong> · {item.hint} <button type="button" data-target-tab={targets[item.key]} onClick={() => onTab(targets[item.key])}>{labels[targets[item.key]]}</button>
    </li>)}</ul>
    {wants.map(item => <p key={item.blockId}>{item.ask} <button type="button" onClick={() => onTab("workflow")}>Otevřít workflow</button></p>)}
    {data.view.doneProposed && data.completion && <ConfirmProposal {...data.completion} serverError={data.completion.error} disabled={data.blocks.disabled} />}
    {data.completion?.pending ? <p>Ke schválení v sektoru: {data.completion.pending}</p> : null}
    <p>Další krok pipeline: {pipeline.current?.title || "Žádná otevřená etapa"} <button type="button" onClick={() => onTab("workflow")}>Pipeline</button></p>
    {data.lease && <CardLease lease={data.lease} release={data.releaseLease} />}
    {data.work && <WorkDetails row={data.work} />}{data.workCounts && <WorkProgress counts={data.workCounts} />}
    {data.sectorProgress && <SectorProgress value={data.sectorProgress} />}
    {data.frontier && <CardFrontier item={data.frontier} />}
    {data.inputSecurity && <InputSecurity {...data.inputSecurity} disabled={data.blocks.disabled} />}
    {data.usage && <CardUsage usage={data.usage} sector={data.view.kind === "sector"} />}
    <CardFoot view={data.view} onTag={data.onTag} />
  </>;
}
