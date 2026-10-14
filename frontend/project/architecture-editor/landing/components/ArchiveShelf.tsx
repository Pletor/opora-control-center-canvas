import { useState } from "react";
import { archivedDate, type ArchiveShelfState } from "@/project/architecture-editor/live-status/logic/worktree-archive";
import { domainLabel, type DomainChoice } from "../logic/domain-choices";

/**
 * Skladiště na konci přehledu: sbalený seznam uzavřených worktree (větev, doména, důvod, datum), jen
 * ke čtení. Načte se až při prvním rozbalení; obnova ze skladiště je pozdější kus.
 */
export default function ArchiveShelf({ shelf, choices, onLoad }: { shelf: ArchiveShelfState; choices: DomainChoice[]; onLoad: () => void }) {
  const [open, setOpen] = useState(false);
  const toggle = () => { if (!open && shelf.items === null && !shelf.loading) onLoad(); setOpen(!open); };
  const items = shelf.items ?? [];
  return <section className="arch-landing__group arch-landing__shelf" data-testid="architecture-archive">
    <button type="button" className="arch-landing__shelf-toggle" aria-expanded={open} onClick={toggle}>
      <span aria-hidden="true">{open ? "▾" : "▸"}</span> Skladiště{shelf.items !== null && ` (${items.length})`}
      <span className="arch-landing__note"> · uzavřené worktree, jen ke čtení</span>
    </button>
    {open && <div className="arch-landing__shelf-body">
      {shelf.loading && <p className="arch-landing__empty">Načítám skladiště…</p>}
      {shelf.error && <p className="arch-landing__alert" role="alert">Skladiště se nepodařilo načíst: {shelf.error}
        <button type="button" className="arch-landing__quiet arch-landing__retry" onClick={onLoad}>Zkusit znovu</button></p>}
      {shelf.items !== null && !items.length && !shelf.error && <p className="arch-landing__empty">Skladiště je prázdné.</p>}
      {items.length > 0 && <ul className="arch-landing__shelf-list">
        {items.map((item) => <li key={item.id} className="arch-landing__shelf-item" data-testid={"archived-" + item.id}>
          <code className="arch-landing__shelf-branch">{item.branch || item.id}</code>
          <span className="arch-landing__shelf-domain">{domainLabel(choices, item.nodeId)}</span>
          <span className="arch-landing__shelf-reason">{item.reason || "bez důvodu"}</span>
          <small className="arch-landing__shelf-date">{archivedDate(item.archivedAt)}{item.actor && ` · ${item.actor}`}</small>
        </li>)}
      </ul>}
    </div>}
  </section>;
}
