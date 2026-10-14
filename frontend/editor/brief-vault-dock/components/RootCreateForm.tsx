// Nové zadání do schránky: kořen se zakládá vždy se stopou (CX/UX/UI nebo Backend + DB), bez ní server
// kořen odmítne. Formulář je sbalený za jedním tlačítkem; zápis přes vaultOp, nová stopa se ohlásí nahoru,
// aby přepínač ukázal, kam zadání přibylo.
import { useState } from "react";
import type { Track } from "@/editor/node-detail/brief-vault/logic/brief-vault-model";
import { vaultOp, type VaultScope } from "../logic/vault-actions";
import { TRACK_VIEWS, type TrackView } from "../logic/vault-tracks";

export default function RootCreateForm({ scope, vaultScope, track, onCreated }: {
  scope: VaultScope;
  /** `""` = plátno, jinak id sektoru nebo karty, ke které se kořen připne. */
  vaultScope: string;
  /** Právě zobrazená stopa: výchozí volba formuláře. */
  track: TrackView;
  onCreated: (track: Track) => void;
}) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [choice, setChoice] = useState<Track>(track === "logic" ? "logic" : "ux");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  async function submit() {
    setBusy(true); setMessage("");
    try {
      await vaultOp(scope, { op: "create", scopeNodeId: vaultScope, title: title.trim(), text, track: choice });
      setOpen(false); setTitle(""); setText("");
      onCreated(choice);
    } catch (e) { setMessage(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  if (!open) {
    return (
      <div className="vault-actions vault-dock__create">
        <button type="button" className="vault-button" onClick={() => setOpen(true)}>Nové zadání</button>
      </div>
    );
  }
  return (
    <section className="vault-panel vault-dock__create" aria-label="Nové zadání">
      <h3 className="vault-panel__title">Nové zadání</h3>
      <div className="vault-actions" role="radiogroup" aria-label="Stopa nového zadání">
        {TRACK_VIEWS.filter((item) => item.id !== "none").map((item) => (
          <label key={item.id} className="vault-pill" title={item.hint}>
            <input type="radio" name="vault-root-track" checked={choice === item.id} onChange={() => setChoice(item.id as Track)} />
            {item.label}
          </label>
        ))}
      </div>
      <label className="vault-field">Název
        <input value={title} maxLength={160} onChange={(event) => setTitle(event.target.value)} placeholder="3. VRSTVA — ÚLOŽIŠTĚ" />
      </label>
      <label className="vault-field">Text zadání (doslova, rozdělí se na kapitoly později)
        <textarea rows={6} value={text} onChange={(event) => setText(event.target.value)} />
      </label>
      <div className="vault-actions">
        <button type="button" className="vault-button vault-button--primary" disabled={busy || !title.trim() || !text.trim()}
          onClick={() => void submit()}>Založit zadání</button>
        <button type="button" className="vault-button" disabled={busy} onClick={() => setOpen(false)}>Zrušit</button>
        {message && <span className="vault-dock__error" role="alert">{message}</span>}
      </div>
    </section>
  );
}
