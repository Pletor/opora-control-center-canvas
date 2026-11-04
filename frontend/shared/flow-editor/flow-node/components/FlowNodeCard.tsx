import type { NodeProps } from "@xyflow/react";
import type { FlowCardNode } from "../../logic/flow-view";
import { formatCost, STATUS_LABEL } from "../../logic/run-overlay";
import { LAYER_BADGE } from "../../flow-lanes/logic/layers";
import FlowPort from "./FlowPort";
import "../styles/flow-node.css";

const STATUS_GLYPH = { queued: "◷", running: "⟳", waiting: "⧗", succeeded: "✓", failed: "✕" } as const;
const MARK_LABEL = { added: "nový", removed: "odebraný", changed: "změněný" } as const;

/** Karta uzlu toku: tvar podle role (spouštěč, krok, širší agent, kulatý sub-uzel), stav běhu v rámečku a odznaku,
 * čekání s důvodem, prostoj, značka rozdílu verzí a připnutý výstup. Jméno a typ stojí pod kartou, u agenta uvnitř. */
export default function FlowNodeCard({ data, selected }: NodeProps<FlowCardNode>) {
  const { run, mark } = data;
  const state = run ? ` flow-node--${run.status}` : "";
  const classes = `flow-node flow-node--${data.role}${state}${run?.stall ? " flow-node--stall" : ""}${mark ? ` flow-node--${mark}` : ""}`
    + `${selected || data.highlighted ? " flow-node--selected" : ""}${data.pinned ? " flow-node--pinned" : ""}${data.layer ? ` flow-node--layer-${data.layer}` : ""}`;
  const title = [data.nodeId, `${data.family}.${data.name}`, data.layer && `vrstva ${data.layer}`, run && `${STATUS_LABEL[run.status]} (pokus ${run.attempt})`, run?.stall && `prostoj: ${run.stall}`,
    run?.error, mark && MARK_LABEL[mark]].filter(Boolean).join(" · ");
  return <div className={classes} title={title} data-testid={`flow-node-${data.nodeId}`} data-run-status={run?.status} data-mark={mark ?? undefined}>
    {data.layer && <span className="flow-node__stripe" aria-hidden="true"/>}
    <div className="flow-node__body">
      <span className="flow-node__glyph" aria-hidden="true">{data.glyph}</span>
      {data.role === "agent" && <span className="flow-node__inside"><b className="flow-node__name">{data.nodeId}</b><small className="flow-node__type">{data.name}</small></span>}
      {run && <span className={`flow-node__status flow-node__status--${run.status}`} aria-label={STATUS_LABEL[run.status]}>{STATUS_GLYPH[run.status]}</span>}
      {data.issue && <span className="flow-node__issue" aria-label="Chybí povinné nastavení">!</span>}
      {data.layer && data.layer !== "neutral" && <span className="flow-node__layer" data-testid={`flow-node-layer-${data.nodeId}`}>{LAYER_BADGE[data.layer]}</span>}
      {data.pinned && <span className="flow-node__pin" aria-label="Připnutý výstup">pin</span>}
    </div>
    {data.role !== "agent" && <div className="flow-node__caption">
      <b className="flow-node__name">{data.nodeId}</b><small className="flow-node__type">{data.name}</small>
      {data.subtitle && <small className="flow-node__subtitle" data-testid={`flow-node-subtitle-${data.nodeId}`}>{data.subtitle}</small>}
    </div>}
    {data.role === "agent" && data.subtitle && <small className="flow-node__subtitle flow-node__subtitle--above" data-testid={`flow-node-subtitle-${data.nodeId}`}>{data.subtitle}</small>}
    {run?.status === "waiting" && <p className="flow-node__waiting">čeká na {run.waitingFor ?? "?"}{run.deadline ? ` do ${new Date(run.deadline).toLocaleString("cs-CZ")}` : ""}</p>}
    {run?.stall && <p className="flow-node__stall">prostoj · {run.stall}</p>}
    {run && run.costUsd > 0 && <span className="flow-node__cost">{formatCost(run.costUsd)}{run.model ? ` · ${run.model}` : ""}</span>}
    {mark && <span className={`flow-node__mark flow-node__mark--${mark}`}>{MARK_LABEL[mark]}</span>}
    {data.ports.map((port) => <FlowPort key={port.handleId} nodeId={data.nodeId} port={port} readOnly={data.readOnly}/>)}
  </div>;
}
