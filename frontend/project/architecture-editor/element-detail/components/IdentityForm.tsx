import { useRef, useState } from "react";
import { confirmSavedChange, useScopedSaveParticipant } from "@/shared/hooks/logic/save-scope-context";
import type { CanvasNode } from "@/shared/types/logic/types";

type Props = {
  node: CanvasNode;
  disabled: boolean;
  onIdentity: (original: CanvasNode, name: string, purpose: string) => Promise<void>;
};

/**
 * Název a účel jako koncept: píše se lokálně, uloží se až tlačítkem přes `onIdentity`. Rodič dá
 * formuláři `key` podle id prvku, takže přepnutí prvku začne čistým konceptem.
 */
export default function IdentityForm({ node, disabled, onIdentity }: Props) {
  const [name, setName] = useState(node.name);
  const [purpose, setPurpose] = useState(node.purpose);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const dirty = name !== node.name || purpose !== node.purpose;
  const locked = disabled || saving;
  const changed = useRef(dirty); changed.current = dirty;
  useScopedSaveParticipant({ id: `architecture-identity:${node.id}`, label: `Název a účel: ${node.name}`,
    dirty, pending: saving, isDirty: () => changed.current,
    blocked: disabled ? "Prvek nyní nelze upravovat." : undefined,
    flush: () => confirmSavedChange(() => onIdentity(node, name, purpose), () => changed.current) });

  async function save() {
    if (!dirty || locked) return;
    setSaving(true);
    setError("");
    try {
      await onIdentity(node, name, purpose);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      className="element-detail__form"
      onSubmit={(event) => {
        event.preventDefault();
        void save();
      }}
    >
      <label className="element-detail__field">
        <span className="element-detail__field-label">Název</span>
        <input className="element-detail__input" value={name} disabled={locked} onChange={(e) => setName(e.target.value)} />
      </label>
      <label className="element-detail__field">
        <span className="element-detail__field-label">Účel</span>
        <textarea className="element-detail__input" rows={3} value={purpose} disabled={locked} onChange={(e) => setPurpose(e.target.value)} />
      </label>
      {error ? <p className="element-detail__error" role="alert">{error}</p> : null}
      <div className="element-detail__actions">
        {dirty ? <span className="element-detail__hint">Neuložený koncept</span> : null}
        <button type="button" className="element-detail__button" disabled={!dirty || locked} onClick={() => { setName(node.name); setPurpose(node.purpose); setError(""); }}>
          Zahodit
        </button>
        <button type="submit" className="element-detail__button element-detail__button--primary" disabled={!dirty || locked}>
          {saving ? "Ukládám…" : "Uložit"}
        </button>
      </div>
    </form>
  );
}
