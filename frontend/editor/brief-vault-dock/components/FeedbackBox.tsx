// Zpětná vazba člověka k výzkumu: Souhlasím · Nesouhlasím · komentář pro další kolo (append-only, server
// ji přijme jen od člověka). Seznam ukazuje, co agent dostane v příštím balíčku research-brief.
import { useState } from "react";
import type { Feedback } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { shortWhen } from "../logic/vault-dock-model";
import { vaultOp, type VaultScope } from "../logic/vault-actions";

export const FEEDBACK_LABEL = { agree: "Souhlasím", disagree: "Nesouhlasím", comment: "Komentář" } as const;

export function FeedbackList({ items, titles }: { items: Feedback[]; titles?: Record<string, string> }) {
  if (!items.length) return null;
  return (
    <div>
      {items.map((item) => (
        <div key={item.id} className="vault-row">
          <span className={"vault-badge vault-badge--" + item.verdict}>{FEEDBACK_LABEL[item.verdict]}</span>
          <span className="vault-row__main">{item.text || "(bez komentáře)"}</span>
          <span className="vault-row__side">{titles ? (titles[item.fragmentId] ?? "fragment") + " · " : ""}{item.by} · {shortWhen(item.at)}</span>
        </div>
      ))}
    </div>
  );
}

export default function FeedbackBox({ scope, fragmentId }: { scope: VaultScope; fragmentId: string }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  async function send(verdict: "agree" | "disagree" | "comment") {
    setBusy(true); setMessage("");
    try {
      await vaultOp(scope, { op: "feedback", fragmentId, verdict, text });
      setText(""); setMessage("Uloženo; agent to dostane v dalším kole.");
    } catch (e) { setMessage(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  return (
    <div className="vault-panel" aria-label="Tvoje zpětná vazba">
      <h4 className="vault-panel__title">Tvoje zpětná vazba</h4>
      <div className="vault-actions">
        <button type="button" className="vault-button vault-button--agree" disabled={busy} onClick={() => void send("agree")}>Souhlasím</button>
        <button type="button" className="vault-button vault-button--disagree" disabled={busy} onClick={() => void send("disagree")}>Nesouhlasím</button>
      </div>
      <label className="vault-field">Komentář pro další kolo
        <textarea rows={2} value={text} maxLength={4000} placeholder="Např.: hledej i řešení bez nové databáze"
          onChange={(event) => setText(event.target.value)} />
      </label>
      <div className="vault-actions">
        <button type="button" className="vault-button" disabled={busy || !text.trim()} onClick={() => void send("comment")}>Uložit komentář</button>
        {message && <span className="vault-dock__notice" role="status">{message}</span>}
      </div>
    </div>
  );
}
