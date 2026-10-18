// Nové zadání do schránky: kořen se zakládá vždy s disciplínou (seskupený výběr Kreslení · Logika · Provoz),
// bez ní server kořen odmítne (400). Formulář je sbalený za jedním tlačítkem; zápis přes vaultOp, nová
// disciplína se ohlásí nahoru, aby přepínač ukázal, kam zadání přibylo.
import { useState } from "react";
import { vaultOp, type VaultScope } from "../logic/vault-actions";
import { UNASSIGNED, type DisciplineView } from "../logic/disciplines";
import DisciplineSelect from "./DisciplineSelect";

export default function RootCreateForm({ scope, vaultScope, view, onCreated }: {
  scope: VaultScope;
  /** `""` = plátno, jinak id sektoru nebo karty, ke které se kořen připne. */
  vaultScope: string;
  /** Právě zobrazená disciplína: výchozí volba formuláře (u Nezařazené musí člověk vybrat). */
  view: DisciplineView;
  onCreated: (view: DisciplineView) => void;
}) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [choice, setChoice] = useState(view === UNASSIGNED ? "" : view);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  async function submit() {
    setBusy(true); setMessage("");
    try {
      await vaultOp(scope, { op: "create", scopeNodeId: vaultScope, title: title.trim(), text, discipline: choice });
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
      <label className="vault-field">Disciplína (kořen ji nese vždy; kapitoly ji dědí, dokud je nepřeřadíš)
        <DisciplineSelect value={choice} label="Disciplína nového zadání" placeholder="vyber disciplínu…" onChange={setChoice} />
      </label>
      <label className="vault-field">Název
        <input value={title} maxLength={160} onChange={(event) => setTitle(event.target.value)} placeholder="3. VRSTVA — ÚLOŽIŠTĚ" />
      </label>
      <label className="vault-field">Text zadání (doslova, rozdělí se na kapitoly později)
        <textarea rows={6} value={text} onChange={(event) => setText(event.target.value)} />
      </label>
      <div className="vault-actions">
        <button type="button" className="vault-button vault-button--primary" disabled={busy || !choice || !title.trim() || !text.trim()}
          onClick={() => void submit()}>Založit zadání</button>
        <button type="button" className="vault-button" disabled={busy} onClick={() => setOpen(false)}>Zrušit</button>
        {message && <span className="vault-dock__error" role="alert">{message}</span>}
      </div>
    </section>
  );
}
