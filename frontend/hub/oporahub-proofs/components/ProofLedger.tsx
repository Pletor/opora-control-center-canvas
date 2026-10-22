import { useState } from "react";
import { ToneChip } from "@/hub/oporahub-health/components/HealthMark";
import JsonMirror from "@/hub/oporahub-mirror/components/JsonMirror";
import { useHubRead } from "@/hub/oporahub-mirror/logic/use-hub-read";
import { ledgerEndpoint, ledgerRows, ledgerTiles, parseLedger, type LedgerFilter } from "../logic/proof-ledger";
import "../styles/oporahub-proofs.css";

const when = (value: string | null) => {
  const time = value ? Date.parse(value) : NaN;
  return Number.isFinite(time) ? new Date(time).toLocaleString("cs-CZ") : "—";
};

/** Kniha důkazů: co je dokázané nebo zkontrolované, na jakém commitu a s jakou důvěrou. Jen ke čtení. */
export default function ProofLedger({ project, workspace }: { project: string; workspace: string }) {
  const read = useHubRead(project && workspace ? ledgerEndpoint(project, workspace) : null, parseLedger);
  const [filter, setFilter] = useState<LedgerFilter>({ tool: "all", status: "all" });
  const ledger = read.data;
  return <div className="oporahub-proofs oporahub-proofs--ledger" data-oh-view="proof-ledger">
    <JsonMirror id="oh-proof-ledger" value={ledger} />
    {read.busy && !ledger && <p className="oporahub-proofs__note" role="status">Načítám knihu důkazů…</p>}
    {read.error && <p className="oporahub-proofs__note" role="alert">{read.error}</p>}
    {ledger && <>
      <div className="oporahub-proofs__tiles">
        {ledgerTiles(ledger).map(tile => <button type="button" key={tile.status} aria-pressed={filter.status === tile.status}
          className={`oporahub-proofs__tile oporahub-proofs__tile--${tile.tone}`} data-oh-metric={`counts.${tile.status}`} data-oh-value={tile.count}
          onClick={() => setFilter(current => ({ ...current, status: current.status === tile.status ? "all" : tile.status }))}>
          <b className="oporahub-proofs__count">{tile.count}</b><span>{tile.glyph} {tile.word}</span>
        </button>)}
      </div>
      <div className="oporahub-proofs__filters">
        <label>Nástroj <select value={filter.tool} onChange={event => setFilter({ ...filter, tool: event.target.value as LedgerFilter["tool"] })}>
          <option value="all">vše</option><option value="lean">Lean</option><option value="tlc">TLC</option></select></label>
        <span className="oporahub-proofs__note">Povolené axiomy: {ledger.allowedAxioms.join(", ") || "—"}</span>
        <button type="button" className="oporahub-proofs__button" onClick={read.reload} disabled={read.busy}>Obnovit</button>
      </div>
      <div className="oporahub-proofs__table" role="table" aria-label="Kniha důkazů">
        <div role="row" className="oporahub-proofs__trow oporahub-proofs__trow--head">
          {["tvrzení", "stav", "důvěra", "commit", "naposledy", "axiomy"].map(name => <span key={name} role="columnheader">{name}</span>)}
        </div>
        {ledgerRows(ledger, filter).map(row => <div key={row.id} role="row" className="oporahub-proofs__trow"
          data-oh-ledger-entry={row.id} data-oh-ledger-status={row.status} data-oh-trust={row.trust ?? ""}>
          <span role="cell"><code className="oporahub-proofs__mono">{row.id}</code>{!row.declared && <small className="oporahub-proofs__note"> (mimo katalog)</small>}
            {row.source && <small className="oporahub-proofs__note oporahub-proofs__source">{row.source}</small>}</span>
          <span role="cell"><ToneChip tone={row.tone}>{row.glyph} {row.word}</ToneChip></span>
          <span role="cell">{row.trust ? <ToneChip tone={row.trust === "ci-verified" ? "ok" : "warn"}>{row.trustLabel}</ToneChip> : "—"}</span>
          <span role="cell"><code className="oporahub-proofs__mono">{row.commit}</code></span>
          <span role="cell">{when(row.lastChecked)}</span>
          <span role="cell">{row.axioms === null ? "—" : row.axioms.join(", ") || "žádné"}
            {row.foreignAxioms.length > 0 && <ToneChip tone="bad">✕ nepovolené: {row.foreignAxioms.join(", ")}</ToneChip>}</span>
        </div>)}
        {!ledgerRows(ledger, filter).length && <p className="oporahub-proofs__note">Filtru nic neodpovídá.</p>}
      </div>
    </>}
  </div>;
}
