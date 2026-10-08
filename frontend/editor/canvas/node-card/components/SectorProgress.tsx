import type { sectorViews } from "../logic/sector-status";
export default function SectorProgress({ value }: { value: ReturnType<typeof sectorViews>[string] }) {
  return <div style={{ padding: "6px 12px" }}>
    <div>{value.verified ? "✓ Ověřeno" : "Probíhá"} · {value.closed}/{value.total}</div>
    <progress aria-label="Dokončení sektoru" value={value.closed} max={Math.max(1, value.total)} />
    <small style={{ display: "block" }}>Brána: {value.gateName}</small>
    {!!value.blockedBy.length && <strong>🔒 Blokuje: {value.blockedBy.join(", ")}</strong>}
  </div>;
}
