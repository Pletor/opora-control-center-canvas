import { useState } from "react";
import { batchIds, confirmLabel, type SectorProposal } from "../logic/sector-proposals";
import "../styles/sector-proposals.css";

// Čip „Ke schválení: N“ v hlavě sektoru. Otevře seznam návrhů a jedno tlačítko potvrdí všechny s hotovými
// důkazy; otevření a stisk jsou dva kroky, protože potvrzení je nevratné. Ukládá rodič přes `confirm`.
export default function SectorProposals({ proposals, disabled, confirm }: {
  proposals: SectorProposal[]; disabled: boolean; confirm: (ids: string[]) => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(0);
  const [error, setError] = useState("");
  const ids = batchIds(proposals);
  async function run() {
    if (busy || disabled || !ids.length) return;
    setBusy(true); setError(""); setSaved(0);
    try { await confirm(ids); setSaved(ids.length); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  if (!proposals.length) return <button type="button" className="sector-proposals__idle" disabled
    title="V sektoru nečeká žádný návrh uzavření od agenta">{confirmLabel(0, false)}</button>;
  return <details className="board-bar__pop sector-proposals" data-testid="sector-proposals">
    <summary className={"board-bar__chip" + (error ? " board-bar__chip--warn" : " board-bar__chip--on")}>Ke schválení: {proposals.length}</summary>
    <div className="board-bar__panel">
      <p>Agent navrhl uzavřít tyto karty. Hromadně se potvrdí jen ty s hotovými důkazy bez N/A; ostatní potvrď jednotlivě na kartě.</p>
      <ul className="sector-proposals__list">
        {proposals.map((p) => <li key={p.id} className="sector-proposals__item">
          <span className="sector-proposals__name">{p.name || "Nepojmenovaná karta"}</span>
          <small className={"sector-proposals__why sector-proposals__why--" + (p.batch ? "ok" : "warn")}>
            {p.batch ? "důkazy deklarovány" : `${p.why} · potvrď jednotlivě`}</small>
          {p.note && <small className="sector-proposals__note">{p.note}</small>}
        </li>)}
      </ul>
      <button type="button" className="sector-proposals__confirm" disabled={disabled || busy || !ids.length} onClick={() => void run()}>
        {confirmLabel(ids.length, busy)}</button>
      {saved > 0 && <p role="status" className="sector-proposals__done">Potvrzeno {saved}.</p>}
      {error && <p role="alert" className="sector-proposals__error">{error}</p>}
    </div>
  </details>;
}
