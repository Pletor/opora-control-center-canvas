import type { CanvasNode } from "@/shared/types/logic/types";
import { editFields, editLabels, type NodeEdit } from "../logic/graph-edits";

export default function GraphNodeEdit({ node, nodes, missing, change, drop }: { node: NodeEdit; nodes: CanvasNode[]; missing: boolean;
  change: (patch: Partial<NodeEdit>) => void; drop: () => void }) {
  const original = nodes.find(item => item.id === node.id);
  return <article className="graph-proposals__edit-row">
    <h4>{original?.name} · <code>{node.id}</code></h4>
    <label>Operace pro {node.id}<select aria-label={`Operace pro ${node.id}`} value={node.remove ? "remove" : "update"} onChange={event => change({ remove: event.target.value === "remove" })}>
      <option value="update" disabled={missing}>Změnit vybraná pole</option><option value="remove">Odstranit prvek</option>
    </select></label>
    {missing && <p>Prvek chybí v pracovním grafu. Lze výslovně odstranit jeho přijatou podobu.</p>}
    {node.remove ? <p className="graph-proposals__warning">Odstranění je součástí návrhu. Potomky a navazující vazby musíte vybrat samostatně; nic se nepřidá automaticky.</p>
      : <>{editFields.filter(field => field !== "size" || original?.kind === "area").map(field => <div key={field} className="graph-proposals__field-edit">
        <label><input type="checkbox" checked={node.selected.includes(field)} onChange={event => change({ selected: event.target.checked ? [...node.selected, field] : node.selected.filter(item => item !== field) })} />
          Změnit {editLabels[field]} · {node.id}</label>
        {node.selected.includes(field) && (field === "sourceRef" ? <div className="graph-proposals__row">
          <label>Původ zdroje<select aria-label={`Původ zdroje ${node.id}`} value={node.sourceOrigin} onChange={event => change({ sourceOrigin: event.target.value as NodeEdit["sourceOrigin"] })}>
            <option value="">Odstranit odkaz na zdroj</option><option value="existing">Existující</option><option value="planned">Plánovaný</option></select></label>
          {node.sourceOrigin && <><label>Cesta<input aria-label={`Cesta ${node.id}`} value={node.sourcePath} onChange={event => change({ sourcePath: event.target.value })} /></label>
            <label>Druh zdroje<select aria-label={`Druh zdroje ${node.id}`} value={node.sourceKind} onChange={event => change({ sourceKind: event.target.value as NodeEdit["sourceKind"] })}><option value="file">Soubor</option><option value="directory">Adresář</option></select></label></>}
        </div> : field === "size" ? <div className="graph-proposals__row">
          <label><input type="checkbox" checked={node.clearSize} onChange={event => change({ clearSize: event.target.checked })} />Vymazat explicitní rozměry</label>
          {!node.clearSize && <>{(["width", "height"] as const).map(dimension => <label key={dimension}>{dimension === "width" ? "Šířka" : "Výška"}<input aria-label={`${dimension === "width" ? "Šířka" : "Výška"} ${node.id}`} type="number" min="120" max="20000" value={node[dimension]} onChange={event => change({ [dimension]: event.target.value })} /></label>)}</>}
        </div> : field === "parentId" ? <label>Nový rodič<select aria-label={`Nový rodič ${node.id}`} value={node.parentId} onChange={event => change({ parentId: event.target.value })}>
          <option value="">Kořen</option>{nodes.filter(item => item.id !== node.id).map(item => <option key={item.id} value={item.id}>{item.name} ({item.id})</option>)}</select></label>
          : <label>{editLabels[field]}<input aria-label={`${editLabels[field]} ${node.id}`} type={field === "x" || field === "y" ? "number" : "text"} value={node[field]} onChange={event => change({ [field]: event.target.value })} /></label>)}
      </div>)}</>}
    <button type="button" onClick={drop}>Odebrat z výběru {node.id}</button>
  </article>;
}
