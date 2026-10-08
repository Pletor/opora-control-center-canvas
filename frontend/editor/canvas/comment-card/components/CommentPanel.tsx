// Inspektor komentáře: titulek, text lístku a smazání. Dílek nic neukládá — rozepsané pole drží
// u sebe a po opuštění (blur) hotovou hodnotu ohlásí nahoru přes onSave(node), stejně jako NodePanel.
import { useState } from "react";
import { useScopedSaveParticipant } from "@/shared/hooks/logic/save-scope-context";
import type { CanvasNode } from "@/shared/types/logic/types";
import "@/editor/canvas/comment-card/styles/comment-card.css";

export default function CommentPanel({
  node,
  readOnly,
  busy,
  onSave,
  onDelete,
}: {
  node: CanvasNode;
  readOnly: boolean;
  busy: boolean;
  onSave: (n: CanvasNode) => void;
  onDelete: () => void;
}) {
  const [title, setTitle] = useState(node.name);
  const [text, setText] = useState(node.purpose);
  useScopedSaveParticipant({ id: `comment-fields:${node.id}`, label: `Komentář: ${node.name}`,
    dirty: title.trim() !== node.name || text !== node.purpose,
    blocked: "Dokončete úpravu komentáře a vyčkejte na její uložení." });
  return (
    <div className="comment-panel" data-testid="comment-panel">
      <div className="eyebrow">KOMENTÁŘ</div>
      <label className="field">
        Titulek
        <input
          aria-label="Titulek komentáře"
          value={title}
          maxLength={160}
          readOnly={readOnly}
          onChange={(e) => setTitle(e.target.value)}
          onBlur={() => {
            const next = title.trim();
            if (!next) { setTitle(node.name); return; }
            if (next !== node.name) onSave({ ...node, name: next });
          }}
        />
      </label>
      <label className="field">
        Text
        <textarea
          aria-label="Text komentáře"
          rows={10}
          maxLength={12000}
          value={text}
          readOnly={readOnly}
          onChange={(e) => setText(e.target.value)}
          onBlur={() => { if (text !== node.purpose) onSave({ ...node, purpose: text }); }}
        />
      </label>
      <p className="muted comment-panel__note">
        Komentář vidí model v node-brief jako orientaci, ne jako příkaz.
      </p>
      <footer className="panel-foot">
        <button
          type="button"
          className="danger"
          disabled={readOnly || busy}
          title={readOnly ? "Main je pouze pro čtení." : "Zobrazí dopad před smazáním"}
          onClick={onDelete}
        >
          Smazat komentář
        </button>
      </footer>
    </div>
  );
}
