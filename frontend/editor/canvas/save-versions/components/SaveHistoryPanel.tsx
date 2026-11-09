// Panel Historie uložení u pravého okraje pod lištou. Dostane hotový seznam verzí a obnovu hlásí
// nahoru (`onRestore`); sám drží jen to, co patří panelu: vybranou verzi, otázku potvrzení a chybu
// poslední obnovy. Potvrzení je jedna věta uvnitř panelu, ne `window.confirm`.
import { useEffect, useState } from "react";
import { authorLine, canRestore, versionLabel, type CanvasVersion } from "@/editor/canvas/save-versions/logic/save-versions";

export default function SaveHistoryPanel({ initialSelected = null, reviewNodes, versions, loading, error, disabled, onRestore, onPrepareRestore, onClose }: {
  initialSelected?: string | null;
  reviewNodes?: { id: string; name?: string }[];
  versions: CanvasVersion[];
  loading: boolean;
  /** Chyba načtení seznamu. */
  error: string;
  disabled: boolean;
  onRestore: (versionId: string) => Promise<void>;
  onPrepareRestore: (versionId: string) => Promise<void>;
  onClose: () => void;
}) {
  const [selected, setSelected] = useState<string | null>(initialSelected);
  const [confirming, setConfirming] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [restoreError, setRestoreError] = useState("");
  const now = new Date();
  const ready = canRestore(versions, selected) && !disabled && !restoring;
  const chosen = versions.find((item) => item.id === selected);
  async function prepare() {
    if (!selected) return;
    setRestoring(true); setRestoreError("");
    try { await onPrepareRestore(selected); setConfirming(true); }
    catch (cause) { setRestoreError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setRestoring(false); }
  }

  useEffect(() => {
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [onClose]);

  async function restore() {
    if (!selected) return;
    setRestoring(true);
    setRestoreError("");
    try {
      await onRestore(selected);
      onClose();
    } catch (e) {
      setRestoreError(e instanceof Error ? e.message : String(e));
      setConfirming(false);
    } finally {
      setRestoring(false);
    }
  }

  return (
    <section className="save-versions__panel" role="dialog" aria-label="Historie uložení" data-testid="save-history-panel">
      <header className="save-versions__panel-head">
        <h2 className="save-versions__panel-title">Historie uložení</h2>
        <button type="button" className="save-versions__panel-close" aria-label="Zavřít historii uložení" onClick={onClose}>×</button>
      </header>
      <p className="save-versions__panel-info">
        Pro obnovení starší uložené verze klikněte na verzi, kterou chcete obnovit, a klikněte na tlačítko Obnovit.
      </p>
      <p className="save-versions__panel-info">Úplná verze zahrnuje plátno, pracovní stav, zadání, texty, deníky, kresby a dokumentaci pracovního prostoru. Cíl a nastavení projektu jsou společné; tato obnova je nemění. Git a externí soubory se neobnovují.</p>
      {(error || restoreError) && <p className="save-versions__panel-error" role="alert">{restoreError || error}</p>}
      {selected === initialSelected && reviewNodes && <details open><summary>Obsah vybrané verze · {reviewNodes.length} karet</summary>
        <ul>{reviewNodes.map(node => <li key={node.id}>{node.name || node.id}</li>)}</ul>
      </details>}
      <ul className="save-versions__panel-list" role="listbox" aria-label="Uložené verze">
        {loading && versions.length === 0 && <li className="save-versions__panel-empty">Načítám verze…</li>}
        {!loading && versions.length === 0 && !error && <li className="save-versions__panel-empty">Zatím žádná uložená verze.</li>}
        {versions.map((item) => (
          <li key={item.id} role="option" aria-selected={item.id === selected}
            className={"save-versions__panel-item" + (item.id === selected ? " save-versions__panel-item--selected" : "")}
            tabIndex={0}
            onClick={() => { setSelected(item.id); setConfirming(false); }}
            onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSelected(item.id); setConfirming(false); } }}>
            <span className="save-versions__panel-when">{versionLabel(item.createdAt, now)}</span>
            <span className="save-versions__panel-author">{authorLine(item.author)}</span>
            <span>{item.actor === "agent" ? "🤖 Agent" : item.actor === "human" ? "👤 Člověk" : "Původce nedostupný"} · Změněné karty: {item.changedCardCount ?? "nedostupné"}</span>
            <span>{item.coverage === "full" ? "Úplná verze pracovního prostoru" : "Starší verze: pouze graf a pracovní stav"}</span>
            {!!item.unavailableAssets && <span>Chybějící podklady: {item.unavailableAssets}</span>}
          </li>
        ))}
      </ul>
      {confirming && chosen ? (
        <footer className="save-versions__panel-foot save-versions__panel-foot--confirm">
          <p className="save-versions__panel-question">
            Opravdu obnovit plátno do verze {versionLabel(chosen.createdAt, now)}?
          </p>
          <button type="button" className="primary" disabled={!ready} onClick={() => void restore()}>
            {restoring ? "Obnovuji…" : "Ano, obnovit"}
          </button>
          <button type="button" disabled={restoring} onClick={() => setConfirming(false)}>Ne</button>
        </footer>
      ) : (
        <footer className="save-versions__panel-foot">
          <button type="button" className="primary" disabled={!ready} onClick={() => void prepare()}>{restoring ? "Připravuji…" : "OBNOVIT"}</button>
          <button type="button" onClick={onClose}>STORNO</button>
        </footer>
      )}
    </section>
  );
}
