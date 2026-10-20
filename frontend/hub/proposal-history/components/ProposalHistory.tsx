import type { OporaProposalsView } from "../logic/use-opora-proposals";
import { diffValue } from "../logic/proposals";
import "../styles/proposal-history.css";

export default function ProposalHistory({ model }: { model: OporaProposalsView }) {
  return <section className="proposal-history" aria-label="Historické snímky zadání" aria-busy={model.busy}>
    <header className="proposal-history__head">
      <div><h2>Snímky uložených zadání</h2><p>Uložené zadání → neměnný snímek → porovnání změn</p></div>
      <button type="button" disabled={model.busy || !model.scope} onClick={model.refresh}>Obnovit kontext</button>
    </header>
    {!model.choices.length ? <p>Vytvořte v Canvasu oblast, sektor nebo uzel. Zde pak vznikne historie jeho zadání.</p> : <>
      <div className="proposal-history__controls">
        <label className="proposal-history__field">Rozsah plánu
          <select value={model.scope} onChange={event => model.select(event.target.value)}>
            {model.choices.map(node => <option key={node.id} value={node.id}>{node.name} ({node.kind === "area" ? "oblast" : node.kind === "sector" ? "sektor" : "uzel"})</option>)}
          </select>
        </label>
        <label className="proposal-history__field proposal-history__field--subject">Důvod návrhu
          <input value={model.subject} maxLength={200} placeholder="Co se v zadání změnilo a proč?"
            onChange={event => model.setSubject(event.target.value)} disabled={model.readOnly || model.busy} />
        </label>
        <button type="button" className="proposal-history__submit"
          disabled={model.busy || model.readOnly || !model.context || !model.subject.trim()}
          onClick={() => void model.create()}>Vytvořit návrh</button>
      </div>
      <p className="proposal-history__hint">Nejprve uložte zadání v Editoru. Návrh zachytí uložený obsah; nevytváří schválení ani merge.</p>
      {model.readOnly && <p className="proposal-history__hint">Tento prostor je jen pro čtení. Pro návrh otevřete pracovní prostor.</p>}
      {model.context && <p className="proposal-history__context">Revize zadání {model.context.specRevision} · kontext <code title={model.context.contextVersion}>{model.context.contextVersion.slice(0, 12)}</code> · předchozí návrh <code>{model.context.head?.slice(0, 10) ?? "žádný"}</code></p>}
      {model.busy && <p role="status">Načítám…</p>}
      {model.notice && <p role="status">{model.notice}</p>}
      {model.error && <p className="proposal-history__error" role="alert">{model.error}</p>}
      {!model.busy && !model.error && !model.items.length && <p>Zatím žádné návrhy. První návrh založí historii tohoto rozsahu.</p>}
      {!!model.items.length && <div className="proposal-history__table-wrap"><table className="proposal-history__table">
        <caption>Historie rozsahu (nejvýše 100 posledních záznamů)</caption>
        <thead><tr><th>Návrh</th><th>Autor a čas</th><th>Revize</th><th>Stav</th><th>Porovnání</th></tr></thead>
        <tbody>{model.items.map(item => <tr key={item.id}>
          <td><strong>{item.subject}</strong><br /><code title={item.id}>{item.id.slice(0, 10)}</code></td>
          <td>{item.by.name} ({item.by.kind})<br /><time dateTime={item.createdAt}>{new Date(item.createdAt).toLocaleString("cs-CZ")}</time></td>
          <td>{item.specRevision}</td><td><span className="proposal-history__status">{item.inMain ? "Přijato do plánu" : "Návrh"}</span></td>
          <td>{item.parent ? <button type="button" disabled={model.busy}
            onClick={() => void model.compare(item.parent!, item.id)}>Rozdíl proti rodiči</button> : "První záznam"}</td>
        </tr>)}</tbody>
      </table></div>}
      {model.diff && <section className="proposal-history__diff" aria-label="Historický rozdíl">
        <h3>Rozdíl {model.diff.before.slice(0, 10)} → {model.diff.after.slice(0, 10)}</h3>
        {!model.diff.changes.length && <p>Obsah zadání je shodný.</p>}
        {model.diff.changes.map((change, index) => <article className="proposal-history__change" key={index}>
          <h4>{change.op === "add" ? "Přidáno" : change.op === "remove" ? "Odebráno" : "Změněno"} <code>{change.path || "/"}</code></h4>
          <div className="proposal-history__values"><div><h5>Před</h5><pre>{diffValue(change.before)}</pre></div>
            <div><h5>Po</h5><pre>{diffValue(change.after)}</pre></div></div>
        </article>)}
      </section>}
    </>}
  </section>;
}
