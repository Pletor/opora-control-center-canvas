import { useState } from "react";
import { conflictLine, type ViewConflict } from "../logic/view-conflicts";
import "../styles/view-conflicts.css";

const SHOWN = 3;

/**
 * Pruh pod hlavičkou editoru: uzly tohoto worktree, které se liší od architektury projektu. Ukáže
 * první tři, zbytek rozbalí; nic nepřepisuje, jen říká, co pohled skryl.
 */
export default function ConflictBanner({ conflicts }: { conflicts: ViewConflict[] }) {
  const [all, setAll] = useState(false);
  if (!conflicts.length) return null;
  const shown = all ? conflicts : conflicts.slice(0, SHOWN);
  return <section className="view-conflicts" role="status" aria-label="Rozdíly proti architektuře projektu" data-testid="architecture-conflicts">
    <p className="view-conflicts__title"><span className="view-conflicts__icon" aria-hidden="true">⚠</span>Architektura projektu má přednost: {conflicts.length === 1 ? "1 uzel se" : `${conflicts.length} uzlů se`} v tomto worktree liší a pohled ukazuje verzi z architektury.</p>
    <ul className="view-conflicts__list">
      {shown.map((item) => <li key={item.id} className="view-conflicts__item">{conflictLine(item)}</li>)}
    </ul>
    {conflicts.length > SHOWN && <button type="button" className="view-conflicts__more" onClick={() => setAll(!all)}>{all ? "Zobrazit méně" : `Zobrazit všech ${conflicts.length}`}</button>}
  </section>;
}
