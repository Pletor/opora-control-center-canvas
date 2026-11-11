import { useEffect, useRef, useState } from "react";
import type { ProductDraft } from "@/project/product-tree/logic/product-tree";
import { pageSiteForSave } from "../../../domain-site/logic/page-site";
import { pathFromName } from "../logic/page-path";
import "../styles/page-dialog.css";

type Props = {
  parentId: string; parentName: string; parentPath: string; disabled: boolean;
  onSave: (draft: ProductDraft) => Promise<void>; onClose: () => void;
};

/** Vyskakovací okno + Stránka / + Podstránka jen s nutným: Název, Adresa (z názvu, dokud ji člověk nepřepíše) a Účel
 * jednou větou (`site.goal`). Esc a Zrušit zavřou, uložení hlásí rodiči; chyba zůstane v okně. */
export default function PageDialog({ parentId, parentName, parentPath, disabled, onSave, onClose }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [name, setName] = useState("");
  const [path, setPath] = useState<string | null>(null);
  const [goal, setGoal] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { const element = dialog.current!; element.showModal(); return () => element.close(); }, []);
  const address = path ?? pathFromName(name, parentPath);
  const locked = disabled || saving;
  async function submit() {
    if (locked || !name.trim()) return;
    setSaving(true); setError("");
    try {
      await onSave({ parentId, name, purpose: "", site: pageSiteForSave({ kind: "page", path: address, goal }) });
      onClose();
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setSaving(false); }
  }
  return <dialog ref={dialog} className="page-dialog" aria-labelledby="page-dialog-title" data-testid="architecture-page-dialog"
    onCancel={(event) => { event.preventDefault(); if (!saving) onClose(); }}>
    <form className="page-dialog__form" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
      <h2 id="page-dialog-title" className="page-dialog__title">{parentPath ? `Nová podstránka: ${parentName}` : "Nová stránka"}</h2>
      <label className="page-dialog__field">Název
        <input autoFocus required maxLength={160} disabled={locked} data-testid="architecture-product-name" value={name} onChange={(event) => setName(event.target.value)}/></label>
      <label className="page-dialog__field">Adresa
        <input required maxLength={2048} disabled={locked} data-testid="architecture-product-path" value={address} onChange={(event) => setPath(event.target.value)}/></label>
      <label className="page-dialog__field">Účel jednou větou <small>(nepovinné)</small>
        <input maxLength={200} disabled={locked} placeholder="Poptávka odeslaná do 2 minut" data-testid="architecture-product-goal" value={goal} onChange={(event) => setGoal(event.target.value)}/></label>
      {error && <p className="page-dialog__error" role="alert">{error}</p>}
      <div className="page-dialog__actions">
        <button type="submit" disabled={locked || !name.trim()} data-testid="architecture-product-save">{saving ? "Ukládám…" : "Uložit"}</button>
        <button type="button" disabled={saving} onClick={onClose}>Zrušit</button>
      </div>
    </form>
  </dialog>;
}
