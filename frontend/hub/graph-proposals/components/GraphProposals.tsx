import type { GraphProposalsView } from "../logic/use-graph-proposals";
import GraphProposalForm from "./GraphProposalForm";
import GraphProposalDetails from "./GraphProposalDetails";
import GraphEditForm from "./GraphEditForm";
import "../styles/graph-proposals.css";

export default function GraphProposals({ model }: { model: GraphProposalsView }) {
  return <section className="graph-proposals" aria-label="Rozšíření plánu">
    <header className="graph-proposals__head"><div><h2>Rozšíření plánu</h2>
      <p>Přidání, úpravy a odstranění karet, oblastí a vazeb jako neměnné návrhy ke kontrole před zápisem na plátno.</p></div>
      <button type="button" disabled={model.busy} onClick={model.refresh}>Obnovit rozšíření plánu</button>
    </header>
    {model.busy && <p role="status">Načítám nebo ukládám rozšíření plánu…</p>}
    {model.error && <p role="alert" className="graph-proposals__warning">{model.error}</p>}
    {model.notice && <p role="status">{model.notice}</p>}
    {!model.context && !model.busy && <p>Kontext pro zápis není dostupný. Zkontrolujte pracovní prostor a případný nesoulad v části „Změny zadání“, potom obnovte data. Historické návrhy lze dál prohlížet.</p>}
    {model.context && <>{model.context.acceptedHead ? <p>Přijatá revize: <code>{model.context.acceptedHead}</code></p>
      : <p>První plán — přijmete zobrazený základ a nové karty.</p>}
      {model.context.readOnly && <p>Pracovní prostor je pouze ke čtení.</p>}
      <GraphProposalForm model={model} /><GraphEditForm model={model} /></>}
    <h3>Historie návrhů rozšíření</h3>
    {!model.items.length && <p>Zatím žádné návrhy rozšíření.</p>}
    <ul className="graph-proposals__history">{model.items.map(item => <li key={item.id}>
      <button type="button" disabled={model.busy} aria-pressed={model.inspected?.id === item.id} onClick={() => model.inspect(item.id)}>{item.subject}</button>
      <span>{item.nodeCount} prvků · {item.edgeCount} vazeb · {item.accepted ? "Přijato" : "Navrženo"} · {item.by.name}</span>
    </li>)}</ul>
    {model.detailBusy && <p role="status">Načítám přesný obsah návrhu…</p>}
    {model.detailError && <p role="alert">{model.detailError}</p>}
    <GraphProposalDetails model={model} />
  </section>;
}
