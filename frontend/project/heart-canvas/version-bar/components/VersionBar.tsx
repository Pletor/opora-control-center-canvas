import type { VersionChip } from "../logic/version-bar";
import "../styles/version-bar.css";

type Props = {
  chips: VersionChip[]; compareId: string | null; diffText: string; editing: boolean; dirty: boolean; canPropose: boolean; busy: boolean;
  onView: (id: string) => void; onCompare: (id: string | null) => void; onSaveDraft: () => void; onDiscard: () => void; onPropose: () => void;
};

/** Lišta verzí: štítky verzí se stavem (draft, kandidát, aktivní, vyřazená), srovnání s jinou verzí a jeho souhrn.
 * V editoru nese akce úpravy: neuložená změna jde uložit jen jako nový draft a draft jde navrhnout ke evalu jako
 * kandidát. Aktivní verzi tady nikdo nepřepne; to udělá až eval. */
export default function VersionBar({ chips, compareId, diffText, editing, dirty, canPropose, busy, onView, onCompare, onSaveDraft, onDiscard, onPropose }: Props) {
  return <div className="version-bar" data-testid="version-bar">
    <div className="version-bar__chips" role="group" aria-label="Verze workflow">
      {chips.map((chip) => <button key={chip.id} type="button" title={chip.title} aria-pressed={chip.current} disabled={busy}
        className={`version-bar__chip version-bar__chip--${chip.status}${chip.current ? " version-bar__chip--current" : ""}`} onClick={() => onView(chip.id)}>
        {chip.label}<small className="version-bar__status">{chip.statusLabel}</small>
      </button>)}
    </div>
    <label className="version-bar__compare">rozdíl proti
      <select value={compareId ?? ""} onChange={(event) => onCompare(event.target.value || null)}>
        <option value="">— nic —</option>
        {chips.filter((chip) => !chip.current).map((chip) => <option key={chip.id} value={chip.id}>{chip.label} · {chip.statusLabel}</option>)}
      </select>
    </label>
    {diffText && <span className="version-bar__diff" data-testid="version-diff">{diffText}</span>}
    {editing && <span className="version-bar__actions">
      {dirty && <>
        <span className="version-bar__dirty">neuložená úprava</span>
        <button type="button" className="version-bar__button version-bar__button--primary" disabled={busy} onClick={onSaveDraft}>Uložit jako draft</button>
        <button type="button" className="version-bar__button" disabled={busy} onClick={onDiscard}>Zahodit</button>
      </>}
      {canPropose && <button type="button" className="version-bar__button" disabled={busy} title="draft → candidate; aktivní verzi přepne až eval"
        onClick={onPropose}>Navrhnout ke evalu</button>}
    </span>}
  </div>;
}
