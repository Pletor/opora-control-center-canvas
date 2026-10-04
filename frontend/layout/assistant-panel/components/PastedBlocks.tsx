import { pastePreview, type PastedBlock } from "../logic/pasted-blocks";

/**
 * Dlaždice vložených textů nad polem pro zprávu. Každá ukazuje začátek textu a délku; tužka ji vrátí
 * do pole k úpravě, křížek ji odebere. Data i změny drží rodič (`Composer` → panel).
 */
export default function PastedBlocks({
  blocks,
  onEdit,
  onRemove,
}: {
  blocks: PastedBlock[];
  onEdit: (block: PastedBlock) => void;
  onRemove: (id: string) => void;
}) {
  if (!blocks.length) return null;
  return (
    <ul className="assistant-panel__pasted" aria-label="Vložené texty">
      {blocks.map((b) => (
        <li key={b.id} className="assistant-panel__pasted-tile">
          <p className="assistant-panel__pasted-preview">{pastePreview(b.text)}</p>
          <span className="assistant-panel__pasted-foot">
            <span className="assistant-panel__pasted-badge">Vloženo</span>
            <span className="assistant-panel__pasted-size">{b.text.length.toLocaleString("cs-CZ")} zn.</span>
            <button type="button" className="assistant-panel__pasted-edit" title="Upravit v poli" aria-label="Upravit vložený text v poli" onClick={() => onEdit(b)}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M12 20h9" />
                <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
              </svg>
            </button>
          </span>
          <button type="button" className="assistant-panel__pasted-remove" title="Odebrat" aria-label="Odebrat vložený text" onClick={() => onRemove(b.id)}>
            ×
          </button>
        </li>
      ))}
    </ul>
  );
}
