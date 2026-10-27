import { counted, type UnresolvedRow } from "../logic/proposal-rows";

/** Pás pod plátnem po návrhu z architektury: vazby OPORY, které návrh nepřevedl, s důvodem. Člověk je dořeší ručně
 * (jiný typ komponenty, jiný port) a pás zavře. */
export default function ModelUnresolved({ rows, onClose }: { rows: UnresolvedRow[]; onClose: () => void }) {
  return <section className="studio-model__unresolved" aria-label="Nepřevedené vazby" data-testid="studio-model-unresolved">
    <header className="studio-model__unresolved-head">
      <span>K ručnímu dořešení: {counted(rows.length, ["vazba", "vazby", "vazeb"])} architektury</span>
      <button type="button" className="studio-model__tool" onClick={onClose} aria-label="Zavřít seznam">×</button>
    </header>
    <ul className="studio-model__unresolved-list">
      {rows.map((row) => <li key={row.edgeId} className="studio-model__unresolved-row">
        <strong className="studio-model__unresolved-route">{row.from} → {row.to}</strong>
        <span className="studio-model__unresolved-reason">{row.reason}</span>
      </li>)}
    </ul>
  </section>;
}
