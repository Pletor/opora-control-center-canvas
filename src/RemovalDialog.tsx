import { useEffect, useRef, useState } from "react";
import type { RemovalPreview } from "@/types";

export default function RemovalDialog({ preview, onClose, onConfirm }: {
  preview: RemovalPreview; onClose: () => void;
  onConfirm: (preview: RemovalPreview) => Promise<void>;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const cancel = useRef<HTMLButtonElement>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const isProject = preview.kind === "project";
  useEffect(() => {
    const el = dialog.current!;
    el.showModal(); cancel.current?.focus();
    return () => { el.close(); };
  }, []);
  async function confirm() {
    if (pending) return;
    setPending(true); setError("");
    try { await onConfirm(preview); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setPending(false); }
  }
  return <dialog ref={dialog} className="removal-dialog" aria-labelledby="removal-title"
    onCancel={(e) => { e.preventDefault(); if (!pending) onClose(); }}>
    <h2 id="removal-title">{isProject ? "Odebrat repozitář" : "Smazat z plátna"}</h2>
    <p><strong>{preview.label}</strong></p>
    {isProject ? <>
      <p>Projekt zmizí ze seznamu OporaCC. <strong>GitHub ani lokální soubory se nesmažou.</strong></p>
      <p>Zachované pracovní prostory: <strong data-testid="removal-workspace-count">{preview.workspaceCount}</strong>.</p>
      <p>Historie a pracovní kopie zůstanou uložené. Neuložené rozepsané změny tohoto projektu budou zahozeny.</p>
    </> : <>
      <p>Uzly včetně všech potomků: <strong data-testid="removal-node-count">{preview.nodeCount}</strong></p>
      <p>Vazby k odstranění: <strong data-testid="removal-edge-count">{preview.edgeCount}</strong></p>
      <p>Ostatní uzly a pracovní prostory zůstanou. Předchozí graf a uložená zadání zachováme v lokální historii; obnovení přes UI zatím není dostupné.</p>
      {preview.nodeCount > 0 && <p>Neuložené rozepsané změny mazaných uzlů budou zahozeny.</p>}
    </>}
    {error && <p role="alert">{error}</p>}
    <div className="removal-actions">
      <button ref={cancel} disabled={pending} onClick={onClose}>Zrušit</button>
      <button className="danger" disabled={pending} onClick={confirm}>
        {pending ? "Provádím…" : isProject ? "Potvrdit odebrání" : "Potvrdit smazání"}
      </button>
    </div>
  </dialog>;
}
