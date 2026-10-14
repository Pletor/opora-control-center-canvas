import type { sectorViews } from "../logic/sector-status";
export default function SectorProgress({ value }: { value: ReturnType<typeof sectorViews>[string] }) {
  return <div className="node-card__row">
    <div className="node-card__row-title">{value.verified ? "✓ Ověřeno" : "Probíhá"} · {value.closed}/{value.total}</div>
    <progress className="node-card__progress" aria-label="Dokončení sektoru" value={value.closed} max={Math.max(1, value.total)} />
    <small className="node-card__row-note">Brána: {value.gateName}</small>
    {!!value.blockedBy.length && <strong className="node-card__row-title">Blokuje: {value.blockedBy.join(", ")}</strong>}
  </div>;
}
