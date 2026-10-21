import { CONTRACT } from "../logic/contract";

/** Kontrakt: agent nečte obrazovku, čte JSON nebo data-oh-* atributy; tabulka říká, co kde najde. */
export default function ContractTable() {
  return <section className="oporahub-agents__panel" aria-label="Kontrakt data-oh">
    <header className="oporahub-agents__panel-head"><h2 className="oporahub-agents__title">Kontrakt: stejná data pro UI i agenta</h2>
      <span className="oporahub-agents__note">agent nečte obrazovku · čte JSON nebo data-oh-* atributy</span></header>
    <div className="oporahub-agents__map" role="table">
      <div className="oporahub-agents__map-row oporahub-agents__map-row--head" role="row">
        {["Prvek UI", "data-* atribut", "JSON cesta", "Zdroj"].map(name => <span key={name} role="columnheader">{name}</span>)}
      </div>
      {CONTRACT.map(row => <div key={row.element} className="oporahub-agents__map-row" role="row">
        <span role="cell">{row.element}</span><span role="cell"><code>{row.attribute}</code></span>
        <span role="cell"><code>{row.jsonPath}</code></span><span role="cell"><code>{row.source}</code></span>
      </div>)}
    </div>
    <pre className="oporahub-agents__snippet">{`document.querySelectorAll('[data-oh-action-status="ready"]')\nJSON.parse(document.getElementById("oh-agent-state").textContent)`}</pre>
  </section>;
}
