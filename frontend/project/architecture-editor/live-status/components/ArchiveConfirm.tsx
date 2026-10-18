import { useEffect, useRef, useState } from "react";
import { reasonProblem, REASON_LIMIT } from "../logic/worktree-archive";

/**
 * Potvrzení přesunu worktree do skladiště: povinný důvod („nápad nevyšel“), věta, co se stane
 * (větev zůstane, worktree zmizí z práce), a odmítnutí backendu (změny, živá relace) přímo u tlačítka.
 */
export default function ArchiveConfirm({ name, onConfirm, onCancel }: {
  name: string; onConfirm: (reason: string) => Promise<void>; onCancel: () => void;
}) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const field = useRef<HTMLTextAreaElement>(null);
  useEffect(() => { field.current?.focus(); }, []);
  async function submit() {
    const problem = reasonProblem(reason);
    if (problem) { setError(problem); return; }
    setSaving(true); setError("");
    try { await onConfirm(reason.trim()); }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); setSaving(false); }
  }
  return <form className="live-status__archive" role="dialog" aria-label={`Přesunout ${name} do skladiště`} data-testid="worktree-archive-confirm"
    onSubmit={(event) => { event.preventDefault(); void submit(); }} onKeyDown={(event) => { if (event.key === "Escape" && !saving) onCancel(); }}>
    <p className="live-status__archive-title">Přesunout {name} do skladiště?</p>
    <p className="live-status__archive-note">Worktree zmizí z aktivní práce, větev zůstane v gitu a záznam půjde jen číst. Worktree se změnami nebo s živou relací se nepřesune.</p>
    <label className="live-status__archive-label">Proč worktree končí
      <textarea ref={field} rows={2} maxLength={REASON_LIMIT} required disabled={saving} className="live-status__archive-reason" placeholder="nápad nevyšel"
        data-testid="worktree-archive-reason" value={reason} onChange={(event) => setReason(event.target.value)}/>
    </label>
    {error && <p className="live-status__archive-error" role="alert">{error}</p>}
    <div className="live-status__actions">
      <button type="submit" className="live-status__danger" disabled={saving} data-testid="worktree-archive-submit">{saving ? "Přesouvám…" : "Do skladiště"}</button>
      <button type="button" className="live-status__quiet" disabled={saving} onClick={onCancel}>Zrušit</button>
    </div>
  </form>;
}
