// Pravý sloupec Velínu: nejvýš tři rozhodnutí pro člověka (zlatá, vždy nahoře) a pět dalších připravených akcí
// v pořadí agent-state. Akce agenta člověk nespouští; tlačítko jen otevře detail karty, kde je vidět proč.
import type { VelinView } from "../logic/velin-model";

export default function VelinSide({ decisions, next, onOpen }: {
  decisions: VelinView["decisions"]; next: VelinView["next"]; onOpen: (nodeId: string) => void;
}) {
  return (
    <aside className="velin__side">
      <section className="velin__panel velin__panel--human" aria-label="Rozhodnutí pro tebe">
        <header className="velin__panel-head"><span className="velin__avatar velin__avatar--human">H</span><b>Rozhodnutí pro tebe</b>
          <span className="velin__grow" /><span className="velin__badge">{decisions.length}</span></header>
        {!decisions.length && <p className="velin__muted velin__panel-row">Nic nečeká na tvé rozhodnutí.</p>}
        {decisions.map(item => (
          <div key={item.id} className="velin__panel-row velin__panel-row--waiting" data-oh-decision={item.kind} data-oh-action-id={item.actionId}>
            <small className="velin__muted">{item.cardName || "projekt"} · {item.kind}</small>
            <p className="velin__decision">{item.title}</p>
            {item.nodeId && <button type="button" className="velin__button velin__button--human" onClick={() => onOpen(item.nodeId!)}>Otevřít detail</button>}
          </div>
        ))}
      </section>
      <section className="velin__panel" aria-label="Další akce">
        <header className="velin__panel-head"><b>Další akce</b><span className="velin__grow" /><small className="velin__muted">podle pořadí v DAG</small></header>
        {!next.length && <p className="velin__muted velin__panel-row">Žádná připravená akce.</p>}
        {next.map(item => (
          <div key={item.id} className="velin__panel-row velin__action" data-oh-action-id={item.id} data-oh-verb={item.verb}>
            <span className="velin__avatar">A</span>
            <div className="velin__action-text"><b>{item.label}</b><small className="velin__muted">{item.cardName}</small></div>
            {item.nodeId && <button type="button" className="velin__button" onClick={() => onOpen(item.nodeId!)}>Detail</button>}
          </div>
        ))}
      </section>
    </aside>
  );
}
