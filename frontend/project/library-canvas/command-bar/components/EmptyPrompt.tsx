import { useState } from "react";
import { enterSubmits, EXAMPLES, promptText } from "../logic/empty-prompt";
import "../styles/empty-prompt.css";

type Props = { initial?: string; busy: boolean; error: string; onSubmit: (text: string) => void;
  /** Plátno logiky prvku: vlastní nadpis a věta, co na plátno patří (`element-context`). */
  title?: string; lead?: string };

/** Výzva uprostřed prázdného plátna: velké vždy aktivní pole se zadáním, „Postavit“ a tři příklady, které text jen vloží.
 * Odeslání i zápis drží rodič; při chybě pole zůstane s původním textem a chyba stojí hned pod ním. */
export default function EmptyPrompt({ initial = "", busy, error, onSubmit, title = "Popište, co má proces dělat", lead }: Props) {
  const [text, setText] = useState(initial);
  const submit = () => { const ready = promptText(text, busy); if (ready) onSubmit(ready); };
  return <div className="empty-prompt" data-testid="empty-prompt">
    <form className="empty-prompt__card" aria-label="Zadání procesu" onSubmit={(event) => { event.preventDefault(); submit(); }}>
      <h3 className="empty-prompt__title">{title}</h3>
      {lead && <p className="empty-prompt__lead" data-testid="empty-prompt-lead">{lead}</p>}
      <textarea className="empty-prompt__input" autoFocus rows={4} value={text} aria-label="Zadání procesu" data-testid="empty-prompt-input"
        placeholder="Např. formulář s výškou a váhou, kontrola, výpočet BMI a uložení do DB"
        onChange={(event) => setText(event.target.value)} onKeyDown={(event) => { if (enterSubmits(event.nativeEvent)) { event.preventDefault(); submit(); } }}/>
      {error && <span className="empty-prompt__error" role="alert" data-testid="empty-prompt-error">{error}</span>}
      <div className="empty-prompt__actions">
        <small className="empty-prompt__hint">Enter odešle, Shift+Enter nový řádek</small>
        <button type="submit" className="empty-prompt__send" disabled={busy || !text.trim()} data-testid="empty-prompt-send">{busy ? "Odesílám…" : "Postavit"}</button>
      </div>
      <ul className="empty-prompt__examples">
        {EXAMPLES.map((example) => <li key={example}><button type="button" className="empty-prompt__example" data-testid="empty-prompt-example" onClick={() => setText(example)}>{example}</button></li>)}
      </ul>
    </form>
  </div>;
}
