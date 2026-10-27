import { portColor } from "../../model/logic/catalog";
import type { StudioModelEdge } from "../../model/logic/model-types";
import type { EditModel } from "../../studio-model/logic/model-edit";
import type { InspectorActions } from "./ModelInspector";

/** Vybraná vazba: datový typ (tečka v barvě čáry), odkud a kam vede, zapnutí, popisek a podmínka kontraktu a smazání.
 * Podmínka je definice pro implementaci; MODEL ji nevyhodnocuje jako kód. Změny jdou rodiči (`actions`). */
export default function EdgeInspector({ edge, model, actions }: { edge: StudioModelEdge; model: EditModel; actions: InspectorActions }) {
  const name = (id: string) => model.nodes.find((node) => node.id === id)?.name ?? id;
  return <>
    <section className="studio-model-inspector__identity">
      <small className="studio-model-inspector__kind">Datová vazba</small>
      <h2 className="studio-model-inspector__name"><span className="studio-model-inspector__type-dot" style={{ background: portColor(edge.type) }} aria-hidden="true"/>{edge.type}</h2>
      <p className="studio-model-inspector__route">{name(edge.from.nodeId)} <code>{edge.from.portId}</code> → {name(edge.to.nodeId)} <code>{edge.to.portId}</code></p>
    </section>
    <label className="studio-model-inspector__check">
      <input type="checkbox" checked={edge.enabled} data-testid="studio-model-edge-enabled" onChange={(event) => actions.onEdge(edge.id, { enabled: event.target.checked })}/>
      Vazba je aktivní
    </label>
    <label className="studio-model-inspector__field">Popisek
      <input className="studio-model-inspector__input" value={edge.label ?? ""} maxLength={200} data-testid="studio-model-edge-label" onChange={(event) => actions.onEdge(edge.id, { label: event.target.value })}/>
    </label>
    <label className="studio-model-inspector__field">Podmínka kontraktu
      <textarea className="studio-model-inspector__input studio-model-inspector__input--area" value={edge.condition ?? ""} maxLength={2000} rows={5}
        onChange={(event) => actions.onEdge(edge.id, { condition: event.target.value })}/>
    </label>
    <p className="studio-model-inspector__hint">Podmínka je definice pro implementaci. MODEL ji nevyhodnocuje jako spustitelný kód.</p>
    <button type="button" className="studio-model-inspector__delete" data-testid="studio-model-delete" onClick={actions.onDelete}>Odstranit vazbu</button>
  </>;
}
