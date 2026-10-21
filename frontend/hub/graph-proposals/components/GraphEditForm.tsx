import type { GraphProposalsView } from "../logic/use-graph-proposals";
import GraphNodeEdit from "./GraphNodeEdit";
import { EvidenceValue } from "./GraphChangeReview";

export default function GraphEditForm({ model }: { model: GraphProposalsView }) {
  const { context, edits } = model;
  if (!context?.workingGraph) return null;
  if (!context.graphManifestId) return context.requiresBaseAdoption && context.workingGraph.nodes.length > 0
    ? <section><h3>Úpravy stávajícího plánu</h3><p>Před změnami nejprve zkontrolujte a přijměte stávající graf. Tento krok nepřidává pomocné karty.</p>
      <button type="button" disabled={model.disabled} onClick={model.adoptExisting}>Převzít stávající graf</button></section> : null;
  const architectureNodes = new Set([...(context.architectureContext?.accepted?.nodes ?? []), ...(context.architectureContext?.working.nodes ?? [])].map(node => node.id));
  const architectureEdges = new Set([...(context.architectureContext?.accepted?.edges ?? []), ...(context.architectureContext?.working.edges ?? [])].map(edge => edge.id));
  return <fieldset disabled={model.disabled} className="graph-proposals__editor"><legend>Úpravy a odstranění existujících prvků</legend>
    <label>Důvod úprav plánu<input maxLength={500} value={model.form.subject} onChange={event => model.editSubject(event.target.value)} /></label>
    <p>Vyberte pouze pole, která chcete změnit. Ostatní pracovní rozdíly se nepřevezmou do přijatého plánu.</p>
    {context.architectureContext?.differs && <section className="graph-proposals__adoption">
      <h4>Sdílená architektura se od přijatého plánu změnila</h4>
      <p>Převzetí uloží aktuální architekturu jako kontext závislostí plánu. Samotnou sdílenou architekturu nemění.</p>
      <details><summary>Porovnat přijatý a aktuální kontext architektury</summary><h5>Přijatý kontext</h5><EvidenceValue value={context.architectureContext.accepted} /><h5>Aktuální kontext</h5><EvidenceValue value={context.architectureContext.working} /></details>
      <label><input type="checkbox" checked={!!edits.draft.adoptArchitectureContext} onChange={event => edits.adoptArchitecture(event.target.checked)} />Převzít aktuální kontext architektury</label>
    </section>}
    <label>Vybrat prvek k úpravě<select aria-label="Vybrat prvek k úpravě" value="" onChange={event => edits.addNode(event.target.value)}>
      <option value="">Vyberte kartu, sektor nebo oblast</option>{edits.nodes.filter(node => node.kind !== "comment" && !architectureNodes.has(node.id) && !edits.draft.nodes.some(item => item.id === node.id)).map(node => <option key={node.id} value={node.id}>{node.name} ({node.id})</option>)}
    </select></label>
    {edits.draft.nodes.map(node => <GraphNodeEdit key={node.id} node={node} nodes={edits.nodes} missing={!context.workingGraph?.nodes.some(item => item.id === node.id)}
      change={patch => edits.editNode(node.id, patch)} drop={() => edits.dropNode(node.id)} />)}
    <label>Vybrat vazbu k úpravě<select aria-label="Vybrat vazbu k úpravě" value="" onChange={event => edits.addEdge(event.target.value)}>
      <option value="">Vyberte vazbu next</option>{edits.edges.filter(edge => !architectureEdges.has(edge.id) && !edits.draft.edges.some(item => item.id === edge.id)).map(edge => <option key={edge.id} value={edge.id}>{edge.id}: {edge.source} → {edge.target}</option>)}
    </select></label>
    {edits.draft.edges.map(edge => <article className="graph-proposals__edit-row" key={edge.id}><h4>Vazba <code>{edge.id}</code></h4>
      <label>Operace s vazbou<select aria-label={`Operace s vazbou ${edge.id}`} value={edge.remove ? "remove" : "update"} onChange={event => edits.editEdge(edge.id, { remove: event.target.value === "remove" })}>
        <option value="update" disabled={!context.workingGraph?.edges.some(item => item.id === edge.id)}>Změnit oba konce</option><option value="remove">Odstranit vazbu</option></select></label>
      {!edge.remove && <div className="graph-proposals__row">{(["source", "target"] as const).map(field => <label key={field}>{field === "source" ? "Z" : "Do"}<select aria-label={`${field === "source" ? "Z" : "Do"} ${edge.id}`} value={edge[field]} onChange={event => edits.editEdge(edge.id, { [field]: event.target.value })}>
        {edits.nodes.map(node => <option key={node.id} value={node.id}>{node.name} ({node.id})</option>)}</select></label>)}</div>}
      <button type="button" onClick={() => edits.dropEdge(edge.id)}>Odebrat z výběru {edge.id}</button>
    </article>)}
    <p>Nové prvky ve formuláři výše patří do samostatného návrhu rozšíření. Tento návrh obsahuje jen zde vybrané úpravy a odstranění.</p>
    <button type="button" onClick={model.createChanges} disabled={!edits.draft.nodes.length && !edits.draft.edges.length && !edits.draft.adoptArchitectureContext}>Navrhnout úpravy a odstranění</button>
  </fieldset>;
}
