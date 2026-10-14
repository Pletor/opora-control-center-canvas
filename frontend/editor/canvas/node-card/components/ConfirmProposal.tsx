import { useState } from "react";
import { missingLabel, type EvidenceReadiness } from "../logic/evidence-readiness";
export default function ConfirmProposal({ disabled, confirm, note, readiness, serverError }: {
  disabled: boolean; confirm: () => Promise<boolean>; note?: string;
  /** Hotovost důkazů karty; chybí-li něco, potvrzení je zamčené (server by ho stejně odmítl). */
  readiness?: EvidenceReadiness;
  /** Poslední chyba uložení stavu ze serveru; ukáže se místo obecné hlášky. */
  serverError?: string;
}) {
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const [error, setError] = useState("");
  const blocked = !!readiness && !readiness.ready;
  async function save() {
    if (busy || disabled || blocked) return;
    setBusy(true); setError(""); setFailed(false);
    try { if (!await confirm()) setFailed(true); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  const shown = error || (failed ? serverError || "Potvrzení se nepodařilo uložit. Obnovte stav karty." : "");
  const missing = readiness && blocked ? missingLabel(readiness) : "";
  return <div className="nodrag nopan node-card__row">
    <button type="button" disabled={disabled || busy || blocked}
      title={missing ? `Nelze potvrdit, ${missing}` : note || "Potvrdit návrh agenta jako člověk"}
      onClick={event => { event.stopPropagation(); void save(); }}>✓ {busy ? "Ukládám…" : "Potvrdit"}</button>
    {missing && <small className="node-card__row-note node-card__row-note--warn" title="Doplňte důkazy v editoru důkazů karty; server bez nich uzavření odmítne.">{missing}</small>}
    {note && <small className="node-card__row-note">{note}</small>}
    {shown && <p role="alert">{shown}</p>}
  </div>;
}
