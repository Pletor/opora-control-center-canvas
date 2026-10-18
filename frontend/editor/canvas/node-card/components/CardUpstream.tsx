import type { UpstreamRow } from "../logic/upstream";

export default function CardUpstream({ rows, open }: { rows: UpstreamRow[]; open: (id: string) => void }) {
  if (!rows.length) return null;
  return <div className="nodrag nopan node-card__row">
    {rows.map(row => <details key={row.edgeId} className="node-card__fold">
      <summary title={row.details}>{row.rejected ? "Zamítnutá větev z: " : "Vychází z: "}
        {row.assumptionChanged && <span className="node-card__row-note--warn">⚠ Předpoklad se změnil · </span>}
        {row.name}{row.label ? ` → ${row.label}` : ""}</summary>
      <button type="button" onClick={event => { event.stopPropagation(); open(row.nodeId); }}>Otevřít {row.name}</button>
      <p className="node-card__row-text">{row.details || "Předávka ani rozhodnutí zatím nejsou uložené."}</p>
    </details>)}
  </div>;
}
