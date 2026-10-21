import type { ActionRow } from "@/hub/oporahub-agent-state/logic/actions-model";

/** Fronta akcí: jeden řádek = jeden přesný zápis (metoda, cesta, preconditions) a jeho stav. */
export default function ActionQueue({ rows, onOpenTarget }: { rows: ActionRow[]; onOpenTarget: (row: ActionRow) => void }) {
  return <section className="oporahub-agents__panel" data-oh-list="actions" aria-label="Fronta dalších akcí">
    <header className="oporahub-agents__panel-head"><h2 className="oporahub-agents__title">Fronta dalších akcí</h2>
      <span className="oporahub-agents__note">{rows.length} akcí · pořadí: sloveso → cíl · ID stabilní, dokud se nezmění hlava</span></header>
    <div className="oporahub-agents__queue" role="table" aria-label="Akce">
      <div className="oporahub-agents__queue-row oporahub-agents__queue-row--head" role="row">
        {["id", "akce", "endpoint", "preconditions", "rozpočet", "stav"].map(name => <span key={name} role="columnheader">{name}</span>)}
      </div>
      {rows.map(row => <div key={row.id} role="row" className={`oporahub-agents__queue-row oporahub-agents__queue-row--${row.status}`}
        data-oh-action-id={row.id} data-oh-action-status={row.status} data-oh-verb={row.verb} data-oh-method={row.method}
        data-oh-path={row.path} data-oh-target={row.targetId ?? ""} data-oh-block-reason={row.blockReason}>
        <span role="cell" className="oporahub-agents__id">{row.id}</span>
        <span role="cell"><b className="oporahub-agents__verb">{row.verb}</b><br />
          {row.targetId ? <button type="button" className="oporahub-agents__target" onClick={() => onOpenTarget(row)} title={`${row.verbLabel} · ${row.targetId}`}>{row.targetId.length > 16 ? `${row.targetId.slice(0, 12)}…` : row.targetId}</button> : <span className="oporahub-agents__note">{row.verbLabel}</span>}</span>
        <span role="cell"><span className="oporahub-agents__method">{row.method}</span>{row.path}</span>
        <span role="cell">{row.preconditions.map(item => <span key={item.key} className="oporahub-agents__pre"><b>{item.key}</b>={item.value} </span>)}{row.human && <span className="oporahub-agents__pre">vyžaduje session člověka</span>}</span>
        <span role="cell">{row.budget}</span>
        <span role="cell"><span className={`oporahub-agents__status oporahub-agents__status--${row.human ? "human" : row.status === "ready" ? "ready" : row.blockReason === "not_implemented" ? "missing" : "blocked"}`}>{row.statusLabel}</span></span>
      </div>)}
      {!rows.length && <p className="oporahub-agents__note oporahub-agents__empty">Žádná akce není připravená ani blokovaná.</p>}
    </div>
  </section>;
}
