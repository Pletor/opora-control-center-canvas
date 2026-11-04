import { useState } from "react";
import "../styles/command-bar.css";

type Props = { selection: readonly string[]; busy: boolean; error: string; onSubmit: (text: string) => void; onClose: () => void };

/** Textové pole se zadáním pro srdce nad plátnem. Enter odešle, Esc zavře. Pod polem stojí, na co se zadání vztahuje
 * (vybrané uzly, jinak celé plátno), aby bylo jasné, co srdce dostane. Odeslání i zápis do plátna drží rodič. */
export default function CommandBar({ selection, busy, error, onSubmit, onClose }: Props) {
  const [text, setText] = useState("");
  const submit = () => { if (text.trim() && !busy) onSubmit(text.trim()); };
  return <form className="command-bar" aria-label="Zadání pro srdce" data-testid="command-bar" onSubmit={(event) => { event.preventDefault(); submit(); }}>
    <input className="command-bar__input" autoFocus value={text} disabled={busy} data-testid="command-bar-input" aria-label="Zadání pro srdce"
      placeholder="Co má srdce nakreslit nebo upravit? Např. po kontrole přidej výpočet BMI a ulož ho do tabulky měření"
      onChange={(event) => setText(event.target.value)} onKeyDown={(event) => { if (event.key === "Escape") onClose(); }}/>
    <button type="submit" className="command-bar__send" disabled={busy || !text.trim()} data-testid="command-bar-send">{busy ? "Odesílám…" : "Zadat"}</button>
    <button type="button" className="command-bar__close" aria-label="Zavřít zadání" onClick={onClose}>×</button>
    <small className="command-bar__scope">{selection.length ? `Týká se uzlů: ${selection.join(", ")}` : "Týká se celého plátna"} · Enter odešle, Esc zavře</small>
    {error && <span className="command-bar__error" role="alert">{error}</span>}
  </form>;
}
