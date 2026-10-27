import { useContext } from "react";
import type { NodeProps } from "@xyflow/react";
import type { ModelCardNode } from "../logic/model-flow";
import { CardActionsContext } from "../logic/card-actions";
import { formatNumber, formatPercent } from "../../studio-model-run/logic/run-view";
import ModelPort from "./ModelPort";

/** Technická karta MODELu v designu TechViz: hlavička s ikonou typu, názvem a štítkem MODEL, řádek typu a skupiny,
 * tři stupně vnitřního fungování a pata s vazbou na kartu OPORY (a jejím skutečným stavem). Za běhu nesou stupně
 * vypočtená čísla (přijato, buffer nebo využití, dokončeno), pod nimi řádek propustnost · využití · latence · chyby
 * a rám barvu vypočteného stavu; zpomalená karta pulzuje, spadlá je ztlumená s křížkem. Porty jsou tečky na obvodu
 * v barvě datového typu; stisk portu hlásí plátnu (klik nebo tah vazby). Tah karty řídí React Flow. */
export default function ModelCard({ data, selected }: NodeProps<ModelCardNode>) {
  const { card } = data, { run } = card;
  const actions = useContext(CardActionsContext);
  const modifiers = (selected ? " studio-model-canvas__card--selected" : "") + (run ? ` studio-model-canvas__card--${run.state}` : "")
    + (run?.slow ? " studio-model-canvas__card--slow" : "") + (run?.failed ? " studio-model-canvas__card--failed" : "");
  return <article className={"studio-model-canvas__card" + modifiers} style={{ width: card.width, height: card.height }}
    data-testid={"studio-model-card-" + card.id} data-run-state={run?.state} aria-label={`${card.typeName} ${card.name}${run ? `, výpočet modelu: ${run.stateLabel}` : ""}`}>
    <header className="studio-model-canvas__card-head">
      <span className="studio-model-canvas__card-icon" aria-hidden="true">{card.icon}</span>
      <strong className="studio-model-canvas__card-name" title={card.name}>{card.name}</strong>
      {run ? <span className="studio-model-canvas__card-run" data-testid={"studio-model-card-state-" + card.id}>{run.stateLabel}</span>
        : <span className="studio-model-canvas__card-badge">MODEL</span>}
    </header>
    <div className="studio-model-canvas__card-type">{card.typeName}{card.provider && ` · ${card.provider}`}<span className="studio-model-canvas__card-group">{card.group} · {card.category}</span></div>
    <div className="studio-model-canvas__card-stages">
      {card.stages.map((stage, index) => <span key={stage} className="studio-model-canvas__card-stage" title={stage}>
        <b className="studio-model-canvas__card-stage-name">{stage}</b>
        {run && <small className="studio-model-canvas__card-stage-value">{run.stages[index]}</small>}
      </span>)}
    </div>
    {run && <p className="studio-model-canvas__card-metrics" title="Výpočet modelu: jednotky za modelovou sekundu, ne měření projektu" data-testid={"studio-model-card-metrics-" + card.id}>
      <span>{formatNumber(run.rps)}/s</span><span>{formatPercent(Math.min(1, run.utilization))}</span><span>{formatNumber(run.latencyMs)} ms</span>
      <span className={run.errors ? "studio-model-canvas__card-errors" : undefined}>{formatNumber(run.errors)} chyb</span>
    </p>}
    {run?.failed && <span className="studio-model-canvas__card-cross" aria-hidden="true">✕</span>}
    <footer className={"studio-model-canvas__card-foot" + (card.binding ? " studio-model-canvas__card-foot--" + card.binding.state : "")}>
      {card.binding ? <>OPORA · {card.binding.name}<span className="studio-model-canvas__card-state">{card.binding.stateLabel}</span></> : "bez vazby na kartu OPORY"}
    </footer>
    {card.ports.map((port) => <ModelPort key={port.id} nodeId={card.id} nodeName={card.name} port={port}
      onDown={(event) => actions.onPortDown(card.id, port.id, event)} onKey={() => actions.onPortKey(card.id, port.id)}/>)}
  </article>;
}
