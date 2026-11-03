import type { RunRow, StallRow } from "../logic/run-list";
import "../styles/run-list.css";

type Props = {
  rows: RunRow[]; stalls: StallRow[]; selected: string | null; onlyVersion: boolean;
  onSelect: (runId: string) => void; onStall: (stall: StallRow) => void; onOnlyVersion: (value: boolean) => void;
};

/** Levý sloupec Běhů: nahoře prostoje s důvodem (klik otevře běh a vybere stojící uzel), pod nimi běhy od nejnovějšího
 * s časem, stavem, verzí, spouštěčem a souhrnem doby a ceny. Filtr omezí běhy na zobrazenou verzi. */
export default function RunList({ rows, stalls, selected, onlyVersion, onSelect, onStall, onOnlyVersion }: Props) {
  return <aside className="run-list" aria-label="Běhy srdce" data-testid="run-list">
    {stalls.length > 0 && <section className="run-list__stalls" aria-label="Prostoje">
      <h3 className="run-list__title run-list__title--stall">Prostoje · {stalls.length}</h3>
      {stalls.map((stall) => <button key={stall.id} type="button" className="run-list__stall" onClick={() => onStall(stall)}>
        <b className="run-list__stall-node">{stall.nodeId} · {stall.version}</b><span className="run-list__stall-reason">{stall.reason}</span>
      </button>)}
    </section>}
    <header className="run-list__head">
      <h3 className="run-list__title">Běhy · {rows.length}</h3>
      <label className="run-list__filter"><input type="checkbox" checked={onlyVersion} onChange={(event) => onOnlyVersion(event.target.checked)}/> jen zobrazená verze</label>
    </header>
    {!rows.length && <p className="run-list__empty">Zatím žádný běh.</p>}
    <ol className="run-list__rows">
      {rows.map((row) => <li key={row.id} className="run-list__item">
        <button type="button" className={`run-list__row run-list__row--${row.status}${row.id === selected ? " run-list__row--selected" : ""}`}
          aria-pressed={row.id === selected} data-testid={`run-${row.id}`} onClick={() => onSelect(row.id)}>
          <span className="run-list__line"><b className="run-list__status">{row.statusLabel}</b><span className="run-list__when">{row.when}</span></span>
          <span className="run-list__line run-list__line--meta">{row.version} · {row.trigger}{row.facts ? ` · ${row.facts}` : ""}</span>
          {row.stalled && <span className="run-list__flag">prostoj</span>}
        </button>
      </li>)}
    </ol>
  </aside>;
}
