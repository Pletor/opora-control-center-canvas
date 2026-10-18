// Jeden vstup dole jako v terminálu: Enter odešle, Shift+Enter dá nový řádek. Co text znamená, rozhodne rodič
// (`onSend` vrací chybu, nebo prázdný text při úspěchu); s chybou text zůstane a pod vstupem je česky proč.
// Nápověda je jeden tichý řádek s nejčastějšími příkazy; zbytek se rozbalí v „další příkazy“. Žádná tlačítka akcí.
import { useState } from "react";
import { MORE_COMMANDS } from "../logic/duel-command";

export default function DuelInput({ placeholder, help, readOnly, onSend }: {
  placeholder: string;
  /** Jeden řádek nejčastějších příkazů (v duelu jiný než v seznamu). */
  help: string;
  readOnly: boolean;
  /** Odeslat text; vrátí chybu k zobrazení, nebo "" (pak se vstup vyprázdní). */
  onSend: (text: string) => Promise<string>;
}) {
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function send() {
    if (busy || !text.trim()) return;
    setBusy(true);
    const problem = await onSend(text);
    setBusy(false);
    setError(problem);
    if (!problem) setText("");
  }
  if (readOnly) return <p className="duel__help">Duel je tady jen ke čtení.</p>;
  return (
    <div className="duel__input">
      <span className="duel__prompt" aria-hidden="true">›</span>
      <textarea className="duel__field" rows={2} value={text} placeholder={placeholder} aria-label="Zpráva do duelu" disabled={busy}
        onChange={(event) => { setText(event.target.value); if (error) setError(""); }}
        onKeyDown={(event) => {
          if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) return;
          event.preventDefault();
          void send();
        }} />
      {error && <p className="duel__error" role="alert">{error}</p>}
      <div className="duel__help">
        <span>{help}</span>
        <details className="duel__more">
          <summary className="duel__more-toggle">další příkazy</summary>
          <ul className="duel__more-list">
            {MORE_COMMANDS.map((line) => <li key={line}>{line}</li>)}
          </ul>
        </details>
      </div>
    </div>
  );
}
