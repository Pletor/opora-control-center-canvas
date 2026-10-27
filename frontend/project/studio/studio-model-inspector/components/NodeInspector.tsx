import { useMemo } from "react";
import { componentType } from "../../model/logic/catalog";
import type { StudioModelNode } from "../../model/logic/model-types";
import type { BindingCard } from "../../studio-layer/logic/studio-layer";
import { parameterRows } from "../logic/inspector-fields";
import ParameterField from "./ParameterField";
import type { InspectorActions } from "./ModelInspector";

/** Vybraná komponenta: identita (ikona, typ, skupina), název, vazba na kartu OPORY domény s jejím skutečným stavem,
 * parametry simulace podle typu a smazání. Změny jdou rodiči (`actions`). */
export default function NodeInspector({ node, bindings, actions }: { node: StudioModelNode; bindings: BindingCard[]; actions: InspectorActions }) {
  const type = componentType(node.type);
  const rows = useMemo(() => parameterRows(node), [node]);
  const bound = node.binding ? bindings.find((card) => card.id === node.binding!.nodeId) : undefined;
  return <>
    <section className="studio-model-inspector__identity">
      <small className="studio-model-inspector__kind">{type?.group} · {type?.category}{type?.provider ? ` · ${type.provider}` : ""}</small>
      <h2 className="studio-model-inspector__name"><span aria-hidden="true">{type?.icon} </span>{type?.name ?? node.type}</h2>
      <code className="studio-model-inspector__id">{node.id}</code>
    </section>
    <label className="studio-model-inspector__field">Název
      <input className="studio-model-inspector__input" value={node.name} maxLength={200} data-testid="studio-model-name" onChange={(event) => actions.onRename(node.id, event.target.value)}/>
    </label>
    <label className="studio-model-inspector__field">Karta OPORY
      <select className="studio-model-inspector__input" value={node.binding?.nodeId ?? ""} data-testid="studio-model-binding" onChange={(event) => actions.onBinding(node.id, event.target.value || null)}>
        <option value="">— bez vazby —</option>
        {node.binding && !bound && <option value={node.binding.nodeId}>{node.binding.nodeId} (karta chybí)</option>}
        {bindings.map((card) => <option key={card.id} value={card.id}>{card.kindLabel}: {card.name}</option>)}
      </select>
    </label>
    {node.binding && <p className={"studio-model-inspector__bound studio-model-inspector__bound--" + (bound?.state ?? "missing")} data-testid="studio-model-bound-state">
      Skutečnost: {bound ? `${bound.name} · ${bound.stateLabel}` : "karta v grafu chybí"}
    </p>}
    <section className="studio-model-inspector__section">
      <h3 className="studio-model-inspector__heading">Parametry simulace<small className="studio-model-inspector__count">{rows.length}</small></h3>
      <p className="studio-model-inspector__hint">Prázdné pole = výchozí hodnota (šedě). Čísla jsou vstup výpočtu modelu, ne měření.</p>
      {rows.map((row) => <ParameterField key={row.key} node={node} row={row} onChange={(value) => actions.onParameter(node.id, row.key, value)}/>)}
    </section>
    <button type="button" className="studio-model-inspector__delete" data-testid="studio-model-delete" onClick={actions.onDelete}>Odstranit komponentu</button>
  </>;
}
