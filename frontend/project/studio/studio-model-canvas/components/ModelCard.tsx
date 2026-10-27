import { useContext } from "react";
import type { NodeProps } from "@xyflow/react";
import type { ModelCardNode } from "../logic/model-flow";
import { CardActionsContext } from "../logic/card-actions";
import ModelPort from "./ModelPort";

/** Technická karta MODELu v designu TechViz: hlavička s ikonou typu, názvem a štítkem MODEL, řádek typu a skupiny,
 * tři stupně vnitřního fungování a pata s vazbou na kartu OPORY (a jejím skutečným stavem). Porty jsou tečky na
 * obvodu v barvě datového typu; stisk portu hlásí plátnu (klik nebo tah vazby). Tah karty řídí React Flow. */
export default function ModelCard({ data, selected }: NodeProps<ModelCardNode>) {
  const { card } = data;
  const actions = useContext(CardActionsContext);
  return <article className={"studio-model-canvas__card" + (selected ? " studio-model-canvas__card--selected" : "")}
    style={{ width: card.width, height: card.height }} data-testid={"studio-model-card-" + card.id} aria-label={`${card.typeName} ${card.name}`}>
    <header className="studio-model-canvas__card-head">
      <span className="studio-model-canvas__card-icon" aria-hidden="true">{card.icon}</span>
      <strong className="studio-model-canvas__card-name" title={card.name}>{card.name}</strong>
      <span className="studio-model-canvas__card-badge">MODEL</span>
    </header>
    <div className="studio-model-canvas__card-type">{card.typeName}{card.provider && ` · ${card.provider}`}<span className="studio-model-canvas__card-group">{card.group} · {card.category}</span></div>
    <div className="studio-model-canvas__card-stages">
      {card.stages.map((stage) => <span key={stage} className="studio-model-canvas__card-stage">{stage}</span>)}
    </div>
    <footer className={"studio-model-canvas__card-foot" + (card.binding ? " studio-model-canvas__card-foot--" + card.binding.state : "")}>
      {card.binding ? <>OPORA · {card.binding.name}<span className="studio-model-canvas__card-state">{card.binding.stateLabel}</span></> : "bez vazby na kartu OPORY"}
    </footer>
    {card.ports.map((port) => <ModelPort key={port.id} nodeId={card.id} nodeName={card.name} port={port}
      onDown={(event) => actions.onPortDown(card.id, port.id, event)} onKey={() => actions.onPortKey(card.id, port.id)}/>)}
  </article>;
}
