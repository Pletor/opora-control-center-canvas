import type { WorkOverview, WorkRow, WorkStatus } from "../logic/use-work-overview";

export const workLabels: Record<WorkStatus, string> = { waiting: "čeká", claimed: "pracuje", "waiting-human": "čeká na člověka", proposed: "ke schválení", done: "hotovo", blocked: "blokováno" };
export const workColors: Record<WorkStatus, string> = { waiting: "#94a3b8", claimed: "#60a5fa", "waiting-human": "#f59e0b", proposed: "#4ade80", done: "#22c55e", blocked: "#f87171" };

export function WorkDetails({ row }: { row: WorkRow }) {
  return <>
    <span>{row.agent || "Agent neuveden"}{row.startedAt ? ` · převzato ${new Date(row.startedAt).toLocaleString()}` : ""}</span>
    <p>Poslední aktivita: {row.lastActivity ? new Date(row.lastActivity).toLocaleString() : "nezaznamenána"}</p>
    {row.waitingOnHuman.map(item => <p key={item.blockId}>Čeká na tebe: {item.ask}</p>)}
    {!!row.blockedBy.length && <p>Blokuje: {row.blockedBy.map(item => item.name).join(", ")}</p>}
    <div aria-label="Dotčené soubory">{row.touched === null ? "Dotčené soubory nedoloženy" : row.touched.length === 0 ? "Doloženo bez změněných souborů" : row.touched.map(path => <code key={path} style={{ display: "inline-block", margin: 3, padding: "2px 5px", border: "1px solid currentColor", borderRadius: 4 }}>@{path}</code>)}</div>
  </>;
}

export function WorkProgress({ counts }: { counts: Record<WorkStatus, number> }) {
  const entries = Object.entries(counts) as [WorkStatus, number][];
  const total = entries.reduce((sum, [, count]) => sum + count, 0);
  return <div aria-label="Postup podle stavů">
    <div style={{ display: "flex", height: 7 }}>{entries.filter(([, count]) => count > 0).map(([status, count]) => <span key={status} title={`${count} ${workLabels[status]}`} style={{ width: `${100 * count / total}%`, background: workColors[status] }} />)}</div>
    <small>{entries.filter(([, count]) => count > 0).map(([status, count]) => `${count} ${workLabels[status]}`).join(" · ") || "Sektor je prázdný"}</small>
  </div>;
}

export default function WorkNow({ overview, error, sectorId, open }: { overview?: WorkOverview; error?: string; sectorId: string | null; open: (id: string) => void }) {
  const active = Object.values(overview?.nodes ?? {}).filter(row => row.status !== "waiting" && row.status !== "done");
  const waiting = active.filter(row => row.status === "waiting-human").length;
  return <details className="nodrag nopan board-bar__pop">
    <summary className={"board-bar__chip" + (waiting ? " board-bar__chip--warn" : active.length ? " board-bar__chip--on" : "")}>
      Teď se děje · {active.length}{waiting ? ` · čeká na tebe ${waiting}` : ""}
    </summary>
    <div className="board-bar__panel">
    {error && <p role="alert">{error}</p>}
    {!overview && !error && <p>Načítám přehled…</p>}
    {sectorId && overview?.sectors[sectorId] && <WorkProgress counts={overview.sectors[sectorId]} />}
    <p>Přehled celého plátna. Soubory uvádí agent podle git diff.</p>
    <div style={{ maxHeight: "50vh", overflowY: "auto" }}>{active.map(row => <article key={row.id} style={{ borderLeft: `3px solid ${workColors[row.status]}`, padding: 6, margin: "8px 0" }}>
      <button type="button" onClick={() => open(row.id)}>{row.name}</button> · {workLabels[row.status]}
      <WorkDetails row={row} />
    </article>)}</div>
    {overview && !active.length && <p>Žádná převzatá karta, blokace ani návrh ke schválení.</p>}
    </div>
  </details>;
}
