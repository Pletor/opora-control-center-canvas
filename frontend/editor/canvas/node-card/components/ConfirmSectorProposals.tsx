import { useState } from "react";
import { batchConfirmable, missingLabel, type EvidenceReadiness } from "../logic/evidence-readiness";

export type SectorProposal = { id: string; name: string; note: string; readiness?: EvidenceReadiness };

/** Hromadně jdou jen karty s hotovými důkazy bez N/A; bez údaje o důkazech se karta nenabídne. */
export const selectableIds = (proposals: SectorProposal[]) =>
  proposals.filter(p => p.readiness && batchConfirmable(p.readiness)).map(p => p.id);

function evidenceStatus(readiness?: EvidenceReadiness): { text: string; color: string } {
  if (!readiness || !readiness.ready) return { text: readiness ? missingLabel(readiness) : "důkazy neznámé", color: "#b45309" };
  if (readiness.notApplicable.length) return { text: `obsahuje N/A: ${readiness.notApplicable.join(", ")} · potvrďte jednotlivě`, color: "#b45309" };
  return { text: "důkazy deklarovány", color: "#16a34a" };
}

export default function ConfirmSectorProposals({ proposals, disabled, confirm }: {
  proposals: SectorProposal[]; disabled: boolean; confirm: (ids: string[]) => Promise<void>;
}) {
  const [excluded, setExcluded] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const allowed = selectableIds(proposals);
  const selected = allowed.filter(id => !excluded.includes(id));
  async function save() {
    if (busy || disabled || !selected.length) return;
    setBusy(true); setError("");
    try { await confirm(selected); setSaved(true); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  return <details className="nodrag nopan board-bar__pop">
    <summary className={"board-bar__chip" + (proposals.length ? " board-bar__chip--on" : "")}>Ke schválení: {proposals.length}</summary>
    <div className="board-bar__panel">
    <div style={{ maxHeight: 300, overflowY: "auto" }}>
      {proposals.map(p => {
        const status = evidenceStatus(p.readiness);
        const ok = allowed.includes(p.id);
        return <label key={p.id} style={{ display: "block" }} title={ok ? p.note : `${status.text}. Kartu potvrďte jednotlivě.`}>
          <input type="checkbox" checked={ok && !excluded.includes(p.id)} disabled={!ok || busy || disabled || saved}
            onChange={event => setExcluded(value => event.target.checked ? value.filter(id => id !== p.id) : [...value, p.id])} />
          {p.name}
          <small style={{ display: "block", color: status.color }}>{status.text}</small>
          {p.note && <small style={{ display: "block" }}>{p.note}</small>}
        </label>;
      })}
    </div>
    <button type="button" disabled={disabled || busy || saved || !selected.length} onClick={() => void save()}>✓ Potvrdit vybrané ({selected.length})</button>
    {saved && <p role="status">Potvrzeno.</p>}
    {error && <p role="alert">{error}</p>}
    </div>
  </details>;
}
