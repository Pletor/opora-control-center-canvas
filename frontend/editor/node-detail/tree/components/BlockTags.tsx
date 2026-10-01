// Štítky bloku: pomáhají filtrovat velký strom. Klik na štítek bublá nahoru (filtr plátna).
import { useState } from "react";

export default function BlockTags({
  tags,
  disabled,
  onAdd,
  onRemove,
  onPick,
}: {
  tags: string[];
  disabled: boolean;
  onAdd: (tag: string) => Promise<boolean>;
  onRemove: (tag: string) => void;
  onPick?: (tag: string) => void;
}) {
  const [draft, setDraft] = useState("");
  function submit() {
    const value = draft.trim();
    if (!value) return;
    onAdd(value).then((ok) => { if (ok) setDraft(""); });
  }
  return (
    <div className="tree-tags" aria-label="Štítky bloku">
      {tags.map((tag) => (
        <span key={tag} className="tree-tag">
          <button type="button" className="tree-tag-name" title="Filtrovat plátno podle štítku" onClick={() => onPick?.(tag)}>{tag}</button>
          <button type="button" aria-label={`Odebrat štítek ${tag}`} disabled={disabled} onClick={() => onRemove(tag)}>✕</button>
        </span>
      ))}
      <input aria-label="Nový štítek" placeholder="+ štítek" value={draft} disabled={disabled} maxLength={40}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
        onBlur={submit} />
    </div>
  );
}
