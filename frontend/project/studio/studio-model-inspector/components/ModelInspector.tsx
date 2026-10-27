import type { ReactNode } from "react";
import type { EditModel, EdgePatch, Selection } from "../../studio-model/logic/model-edit";
import type { BindingCard } from "../../studio-layer/logic/studio-layer";
import { counted } from "../../studio-model/logic/proposal-rows";
import NodeInspector from "./NodeInspector";
import EdgeInspector from "./EdgeInspector";
import "../styles/studio-model-inspector.css";

export type InspectorActions = {
  onRename: (id: string, name: string) => void; onBinding: (id: string, cardId: string | null) => void;
  onParameter: (id: string, key: string, value: number | string | undefined) => void; onEdge: (id: string, patch: EdgePatch) => void;
  onDelete: () => void; onClear: () => void;
};

/** Inspektor vpravo od plátna MODELu (v MODELu místo detailu Skutečnosti): bez výběru nápověda k ovládání, s vybranou
 * komponentou její název, typ, parametry simulace a vazba na kartu OPORY, s vybranou vazbou její typ, zapnutí,
 * popisek a podmínka. Nad výběrem leží panel telemetrie běhu, který skládá rodič (`telemetry`). Každou změnu hlásí
 * rodiči; nic neukládá. */
export default function ModelInspector({ model, selection, bindings, actions, telemetry }: { model: EditModel; selection: Selection; bindings: BindingCard[]; actions: InspectorActions; telemetry?: ReactNode }) {
  const node = selection?.kind === "node" ? model.nodes.find((item) => item.id === selection.id) : undefined;
  const edge = selection?.kind === "edge" ? model.edges.find((item) => item.id === selection.id) : undefined;
  return <aside className="studio-model-inspector" aria-label="Inspektor modelu" data-testid="studio-model-inspector">
    <header className="studio-model-inspector__title">
      <span>{node ? "Komponenta" : edge ? "Vazba" : "Inspektor"}</span>
      {(node || edge) && <button type="button" className="studio-model-inspector__close" onClick={actions.onClear} title="Zrušit výběr (Escape)">×</button>}
    </header>
    {(node || edge) && telemetry}
    {node ? <NodeInspector key={node.id} node={node} bindings={bindings} actions={actions}/>
      : edge ? <EdgeInspector key={edge.id} edge={edge} model={model} actions={actions}/>
      : <div className="studio-model-inspector__help">
          <p className="studio-model-inspector__hint">Přidejte komponentu z katalogu vlevo (klik nebo přetažení). Vazbu vytvoříte klikem na výstupní port a pak na vstupní, nebo tažením z portu na port; nekompatibilní porty se ztlumí.</p>
          <p className="studio-model-inspector__hint">Klik na kartu nebo vazbu ji vybere. Delete smaže výběr, Escape zruší výběr i rozdělanou vazbu, Ctrl+Z vrátí a Ctrl+Shift+Z zopakuje krok.</p>
          <p className="studio-model-inspector__hint">{counted(model.nodes.length, ["komponenta", "komponenty", "komponent"])} · {counted(model.edges.length, ["vazba", "vazby", "vazeb"])}</p>
        </div>}
  </aside>;
}
