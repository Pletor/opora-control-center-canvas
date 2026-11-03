import { useState } from "react";
import type { LogRow } from "../logic/log-view";
import "../styles/run-log.css";

type Props = { rows: LogRow[]; selectedNode: string | null; error: string; onSelectNode: (nodeId: string) => void };

/** Spodní panel logu běhu: append-only události v pořadí `seq` s časem, uzlem, plátnem a popisem. Klik na událost
 * vybere její uzel na plátně, vybraný uzel zvýrazní své řádky; filtr „jen vybraný uzel“ zbytek schová. Sbalitelný. */
export default function RunLogPanel({ rows, selectedNode, error, onSelectNode }: Props) {
  const [open, setOpen] = useState(true);
  const [onlyNode, setOnlyNode] = useState(false);
  const shown = onlyNode && selectedNode ? rows.filter((row) => row.nodeId === selectedNode) : rows;
  return <section className={`run-log${open ? "" : " run-log--closed"}`} aria-label="Log běhu" data-testid="run-log">
    <header className="run-log__head">
      <button type="button" className="run-log__toggle" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? "▾" : "▸"} Log běhu · {rows.length}</button>
      <label className="run-log__filter"><input type="checkbox" checked={onlyNode} disabled={!selectedNode} onChange={(event) => setOnlyNode(event.target.checked)}/>
        jen {selectedNode ?? "vybraný uzel"}</label>
      {error && <span className="run-log__error" role="alert">{error}</span>}
    </header>
    {open && <ol className="run-log__rows">
      {!shown.length && <li className="run-log__empty">Vyberte běh vlevo.</li>}
      {shown.map((row) => <li key={row.seq} className="run-log__item">
        <button type="button" disabled={!row.nodeId} data-testid={`log-${row.seq}`}
          className={`run-log__row run-log__row--${row.tone}${row.nodeId && row.nodeId === selectedNode ? " run-log__row--selected" : ""}`}
          onClick={() => row.nodeId && onSelectNode(row.nodeId)}>
          <span className="run-log__seq">#{row.seq}</span><span className="run-log__time">{row.time}</span>
          <span className="run-log__canvas" title="Plátno, ze kterého událost přišla">P{row.canvas}</span>
          <span className="run-log__node">{row.nodeId ?? "běh"}</span><span className="run-log__type">{row.type}</span><span className="run-log__text">{row.text}</span>
        </button>
      </li>)}
    </ol>}
  </section>;
}
