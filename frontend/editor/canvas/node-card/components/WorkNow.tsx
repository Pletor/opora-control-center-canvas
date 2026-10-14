import type { CSSProperties } from "react";
import type { WorkOverview, WorkRow, WorkStatus } from "../logic/use-work-overview";

export const workLabels: Record<WorkStatus, string> = { waiting: "čeká", claimed: "pracuje", "waiting-human": "čeká na člověka", proposed: "ke schválení", done: "hotovo", blocked: "blokováno" };

export function WorkDetails({ row }: { row: WorkRow }) {
  return <>
    <span className="node-card__row-title">{row.agent || "Agent neuveden"}{row.startedAt ? ` · převzato ${new Date(row.startedAt).toLocaleString()}` : ""}</span>
    <p>Poslední aktivita: {row.lastActivity ? new Date(row.lastActivity).toLocaleString() : "nezaznamenána"}</p>
    {row.waitingOnHuman.map(item => <p key={item.blockId}>Čeká na tebe: {item.ask}</p>)}
    {!!row.blockedBy.length && <p>Blokuje: {row.blockedBy.map(item => item.name).join(", ")}</p>}
    <div className="node-card__chips" aria-label="Dotčené soubory">{row.touched === null ? "Dotčené soubory nedoloženy" : row.touched.length === 0 ? "Doloženo bez změněných souborů" : row.touched.map(path => <code key={path} className="node-card__chip">@{path}</code>)}</div>
  </>;
}

export function WorkProgress({ counts }: { counts: Record<WorkStatus, number> }) {
  const entries = Object.entries(counts) as [WorkStatus, number][];
  const total = entries.reduce((sum, [, count]) => sum + count, 0);
  return <div aria-label="Postup podle stavů">
    <div className="node-card__bar">{entries.filter(([, count]) => count > 0).map(([status, count]) => <span key={status} className={`node-card__bar-part node-card__bar-part--${status}`} title={`${count} ${workLabels[status]}`} style={{ "--w": `${100 * count / total}%` } as CSSProperties} />)}</div>
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
    <div className="node-card__scroll node-card__scroll--tall">{active.map(row => <article key={row.id} className={`node-card__work node-card__work--${row.status}`}>
      <button type="button" onClick={() => open(row.id)}>{row.name}</button> · {workLabels[row.status]}
      <WorkDetails row={row} />
    </article>)}</div>
    {overview && !active.length && <p>Žádná převzatá karta, blokace ani návrh ke schválení.</p>}
    </div>
  </details>;
}
