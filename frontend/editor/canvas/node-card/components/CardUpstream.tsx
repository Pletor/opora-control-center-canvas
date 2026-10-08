import type { UpstreamRow } from "../logic/upstream";

export default function CardUpstream({ rows, open }: { rows: UpstreamRow[]; open: (id: string) => void }) {
  if (!rows.length) return null;
  return <div className="nodrag nopan" style={{ padding: "6px 12px" }}>
    {rows.map(row => <details key={row.edgeId}>
      <summary title={row.details}>{row.rejected ? "Zamítnutá větev z: " : "Vychází z: "}
        {row.assumptionChanged && <span style={{ color: "#eab308" }}>⚠ Předpoklad se změnil · </span>}
        {row.name}{row.label ? ` → ${row.label}` : ""}</summary>
      <button type="button" onClick={event => { event.stopPropagation(); open(row.nodeId); }}>Otevřít {row.name}</button>
      <p style={{ whiteSpace: "pre-wrap" }}>{row.details || "Předávka ani rozhodnutí zatím nejsou uložené."}</p>
    </details>)}
  </div>;
}
