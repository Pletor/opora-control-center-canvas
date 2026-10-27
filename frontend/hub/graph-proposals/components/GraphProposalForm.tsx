import type { GraphProposalsView } from "../logic/use-graph-proposals";
import { kindNames } from "../logic/graph-proposals";
import { EDGE_CARRIES } from "@/shared/types/logic/types";
import { CARRIES_LABEL, parseCarries } from "@/shared/edge-carries/logic/edge-carries";
import { fieldKeys, fieldLabels, fieldLimits } from "@/hub/plan-changes/logic/plan-changes";

export default function GraphProposalForm({ model }: { model: GraphProposalsView }) {
  const choices = [...model.form.nodes.map(node => ({ id: node.ref, label: `${node.name || "Nový prvek"} (${node.ref})` })),
    ...model.existing.map(node => ({ id: `@${node.id}`, label: `${node.name} (@${node.id})` }))];
  return <fieldset className="graph-proposals__form" disabled={model.disabled}>
    <legend>Nové prvky plánu</legend>
    <label className="graph-proposals__field">Důvod rozšíření plánu
      <input value={model.form.subject} maxLength={500} onChange={event => model.editSubject(event.target.value)} />
    </label>
    <p>Vytvoření návrhu Canvas nemění. Přesná ID a umístění určí server; před přijetím je uvidíte v návrhu.</p>
    {model.form.nodes.map((node, index) => <fieldset className="graph-proposals__row" key={node.ref}>
      <legend>Prvek {index + 1} · {node.ref}</legend>
      <div className="graph-proposals__columns">
        <label className="graph-proposals__field">Název prvku {index + 1}<input value={node.name} maxLength={300} onChange={event => model.editNode(index, "name", event.target.value)} /></label>
        <label className="graph-proposals__field">Typ prvku {index + 1}<select aria-label={`Typ prvku ${index + 1}`} value={node.kind} onChange={event => model.editNode(index, "kind", event.target.value)}>
          {Object.entries(kindNames).map(([kind, name]) => <option key={kind} value={kind}>{name}</option>)}
        </select></label>
        <label className="graph-proposals__field">Rodič prvku {index + 1}<select aria-label={`Rodič prvku ${index + 1}`} value={node.parent} onChange={event => model.editNode(index, "parent", event.target.value)}>
          <option value="">Kořen plátna</option>{choices.filter(choice => choice.id !== node.ref).map(choice => <option key={choice.id} value={choice.id}>{choice.label}</option>)}
        </select></label>
      </div>
      {node.kind === "area" && <div className="graph-proposals__columns">{(["width", "height"] as const).map(field => <label className="graph-proposals__field" key={field}>
        {field === "width" ? "Šířka" : "Výška"} oblasti {index + 1}<input type="number" min={120} max={20000} step={1}
          value={node[field]} onChange={event => model.editNode(index, field, event.target.value)} />
      </label>)}</div>}
      {node.kind !== "area" && <div className="graph-proposals__columns">{fieldKeys.map(field => <label className="graph-proposals__field" key={field}>
        {fieldLabels[field]} · prvek {index + 1}<textarea value={node[field]} maxLength={fieldLimits[field]} onChange={event => model.editNode(index, field, event.target.value)} />
      </label>)}</div>}
      <button type="button" onClick={() => model.removeNode(index)}>Odebrat prvek {index + 1}</button>
    </fieldset>)}
    <button type="button" onClick={model.addNode}>Přidat prvek</button>
    <h3>Vazby mezi prvky</h3>
    <p>Volitelné navazující vazby mohou spojovat nové prvky i existující karty.</p>
    {model.form.edges.map((edge, index) => <div className="graph-proposals__columns graph-proposals__row" key={index}>
      {(["from", "to"] as const).map(field => <label className="graph-proposals__field" key={field}>
        {field === "from" ? "Odkud" : "Kam"} · vazba {index + 1}<select aria-label={`${field === "from" ? "Odkud" : "Kam"} · vazba ${index + 1}`} value={edge[field]} onChange={event => model.editEdge(index, field, event.target.value)}>
          <option value="">Vyberte prvek</option>{choices.map(choice => <option key={choice.id} value={choice.id}>{choice.label}</option>)}
        </select>
      </label>)}
      <label className="graph-proposals__field">Co po vazbě teče · vazba {index + 1}<select aria-label={`Co po vazbě teče · vazba ${index + 1}`} value={edge.carries}
        onChange={event => model.editEdge(index, "carries", parseCarries(event.target.value) ?? "")}>
        <option value="">neurčeno</option>{EDGE_CARRIES.map(value => <option key={value} value={value}>{CARRIES_LABEL[value]}</option>)}</select></label>
      <button type="button" onClick={() => model.removeEdge(index)}>Odebrat vazbu {index + 1}</button>
    </div>)}
    <div className="graph-proposals__actions"><button type="button" onClick={model.addEdge}>Přidat vazbu</button>
      <button type="button" onClick={model.create} disabled={!model.form.subject.trim() || !model.form.nodes.length}>Uložit návrh rozšíření</button></div>
  </fieldset>;
}
