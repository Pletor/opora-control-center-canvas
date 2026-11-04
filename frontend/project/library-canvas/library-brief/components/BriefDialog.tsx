import { useEffect, useState } from "react";
import { loadBrief } from "../logic/library-brief";
import "../styles/library-brief.css";

/** Dialog „Zadání pro agenta“: načte hotový text zadání pro zobrazenou verzi plátna, ukáže ho monospace se zalamováním
 * a nabídne Kopírovat a Zavřít. Chybu serveru (např. plátno bez kroků) řekne věcně v dialogu. Nic neukládá. */
export default function BriefDialog({ flowId, version, onClose }: { flowId: string; version: number | null; onClose: () => void }) {
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    let alive = true;
    setText(null); setError("");
    loadBrief(flowId, version).then((made) => { if (alive) setText(made); }, (cause) => { if (alive) setError(cause instanceof Error ? cause.message : String(cause)); });
    return () => { alive = false; };
  }, [flowId, version]);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  const copy = async () => {
    try { await navigator.clipboard.writeText(text ?? ""); setCopied(true); setError(""); } catch { setError("Schránku se nepodařilo zapsat, text označte a zkopírujte ručně."); }
  };
  return <div className="library-brief" data-testid="library-brief">
    <section className="library-brief__dialog" role="dialog" aria-label="Zadání pro agenta">
      <header className="library-brief__head">
        <h3 className="library-brief__title">Zadání pro agenta{version ? <small className="library-brief__version">verze {version}</small> : null}</h3>
        <button type="button" className="library-brief__button" onClick={onClose}>Zavřít</button>
      </header>
      {text === null && !error && <p className="library-brief__status">Generuji zadání…</p>}
      {error && <p className="library-brief__error" role="alert">{error}</p>}
      {text !== null && <pre className="library-brief__text" data-testid="library-brief-text">{text}</pre>}
      <footer className="library-brief__foot">
        <small className="library-brief__hint">Vygenerováno z uložené verze plátna. Odchylku od plátna agent hlásí, plátno se nemění tiše.</small>
        <button type="button" className="library-brief__button library-brief__button--primary" disabled={text === null} onClick={copy}>{copied ? "Zkopírováno" : "Kopírovat"}</button>
      </footer>
    </section>
  </div>;
}
