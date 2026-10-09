// Akce nad vybraným fragmentem v sekci Zadání: „Zadat výzkum agentovi“ (otázka proveditelnosti → fragment
// research se stavem zadáno) a „Položit otázku“ (K upřesnění). Formulář je inline, zápis přes vaultOp.
import { useState } from "react";
import { vaultOp, type VaultScope } from "../logic/vault-actions";

type Mode = "research" | "question" | null;

export default function FragmentActions({ scope, fragmentId, onSection }: {
  scope: VaultScope;
  fragmentId: string;
  onSection: (section: "research" | "questions") => void;
}) {
  const [mode, setMode] = useState<Mode>(null);
  const [text, setText] = useState("");
  const [askedFor, setAskedFor] = useState<"human" | "agent">("human");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  async function submit() {
    const value = text.trim();
    setBusy(true); setMessage("");
    try {
      if (mode === "research") await vaultOp(scope, { op: "research", fragmentId, title: value.slice(0, 160), question: value.slice(0, 1000), text: "" });
      else await vaultOp(scope, { op: "question", fragmentId, title: value.slice(0, 160), askedFor, ...(value.length > 160 ? { text: value } : {}) });
      const target = mode === "research" ? "research" : "questions";
      setMode(null); setText("");
      onSection(target);
    } catch (e) { setMessage(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  return (
    <>
      <button type="button" className="vault-button vault-button--primary" aria-expanded={mode === "research"}
        onClick={() => setMode(mode === "research" ? null : "research")}>Zadat výzkum agentovi</button>
      <button type="button" className="vault-button" aria-expanded={mode === "question"}
        onClick={() => setMode(mode === "question" ? null : "question")}>Položit otázku</button>
      {mode && (
        <div className="vault-panel vault-panel--full">
          <label className="vault-field">{mode === "research" ? "Co má výzkum ověřit (otázka proveditelnosti)" : "Otázka k upřesnění"}
            <textarea rows={2} value={text} maxLength={1000} onChange={(event) => setText(event.target.value)}
              placeholder={mode === "research" ? "Jde atomicky přepnout verzi bez výpadku vyhledávání?" : "Co přesně znamená JEV a kam patří?"} />
          </label>
          {mode === "question" && (
            <label className="vault-field">Kdo odpoví
              <select value={askedFor} onChange={(event) => setAskedFor(event.target.value as "human" | "agent")}>
                <option value="human">člověk</option>
                <option value="agent">agent</option>
              </select>
            </label>
          )}
          <div className="vault-actions">
            <button type="button" className="vault-button vault-button--primary" disabled={busy || !text.trim()} onClick={() => void submit()}>
              {mode === "research" ? "Zadat výzkum" : "Položit otázku"}</button>
            {message && <span className="vault-window__error" role="alert">{message}</span>}
          </div>
        </div>
      )}
    </>
  );
}
