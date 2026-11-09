import {EvidenceValue} from '@/hub/graph-proposals/components/GraphChangeReview';
import {impact, object} from './review-impact';

const names: Record<string, string> = {node: 'karta', sector: 'sektor', area: 'oblast', comment: 'komentář'};
export default function ReviewImpact({before, after, input, operation}: {before: unknown; after: unknown; input: unknown; operation?: string}) {
  const value = impact(before, after), request = object(input);
  return <section className="working-review__impact" aria-label="Přehled dopadů">
    <h3>Co se změní</h3>
    {value.projectArchive ? <p>Projekt bude odpojen z aplikace. Soubory repozitáře zůstávají zachované.</p>
      : <p><strong>{value.nodes.length} prvků · {value.edges.length} vazeb</strong> se změní. Plátno má nyní {value.oldNodeCount} prvků, po změně {value.nextNodeCount}.</p>}
    <ul>{value.nodes.map(change => {const item = change.after ?? change.before!; return <li key={change.id}>
      <strong>{change.action}: {String(item.name || change.id)}</strong> · {names[String(item.kind)] ?? String(item.kind)} · <code>{change.id}</code>
      <details><summary>Porovnat tento prvek</summary><div className="graph-proposals__comparison"><section><h4>Před změnou</h4><EvidenceValue value={change.before}/></section><section><h4>Po změně</h4><EvidenceValue value={change.after}/></section></div></details>
    </li>;})}</ul>
    {!!value.edges.length && <details><summary>Změněné vazby ({value.edges.length})</summary>{value.edges.map(change => <article key={change.id}>
      <h4>{change.action} · {change.id}</h4><p>Před změnou</p><EvidenceValue value={change.before}/><p>Po změně</p><EvidenceValue value={change.after}/>
    </article>)}</details>}
    {!value.projectArchive && <p>Obsah stavu: {value.stateNodes} karet, {value.stateEdges} reportů vazeb, {value.rules} pravidel a {value.decisions} rozhodnutí.
      {' '}Historie prostoru agenta: {value.workspaceRemoved} odebraných a {value.workspaceAdded} obnovených záznamů.</p>}
    {operation === 'remove_item' && !value.projectArchive && <p>Vznikne nativní záznam pro jednorázovou obnovu odstraněného grafu, stavu a historie prostoru. Jeho ID se zobrazí po provedení.</p>}
    {operation === 'restore_removed' && <p>Spotřebuje se záznam obnovy <code>{String(request.recoveryId ?? '')}</code>. Obnoví se pouze chybějící položky; současné položky se nepřepíší.</p>}
    <details><summary>Úplné uložené podklady před změnou a po změně</summary><div className="graph-proposals__comparison">
      <section><h3>Před změnou</h3><EvidenceValue value={before}/></section><section><h3>Po změně</h3><EvidenceValue value={after}/></section>
    </div></details>
  </section>;
}
