import { useState } from "react";

export default function InputSecurity({ enabled, disabled, save }: { enabled: boolean; disabled: boolean; save: (enabled: boolean) => Promise<boolean> }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return <div className="nodrag nopan" style={{ padding: "6px 12px" }}><label>
    <input type="checkbox" checked={enabled} disabled={disabled || busy} onChange={async e => {
      setBusy(true); setError("");
      try { if (!await save(e.target.checked)) setError("Změna se neuložila; obnovte stav karty."); }
      catch (error) { setError(String(error)); }
      finally { setBusy(false); }
    }} />Stahuje obsah z URL</label>
    {enabled && <small style={{ display: "block" }}>Povinný blok: Bezpečnost vstupu</small>}
    {error && <p role="alert">{error}</p>}
  </div>;
}
