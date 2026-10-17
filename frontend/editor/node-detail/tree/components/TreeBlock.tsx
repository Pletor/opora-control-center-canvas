// Jeden blok stromu: hlavička (číslo, název, status, nástroje) a po rozbalení text, štítky, TODO, obrázky, stav.
// Dílky nic neukládají; každá změna bublá nahoru jako událost se jménem bloku.
import { useEffect, useState } from "react";
import { useScopedSaveParticipant } from "@/shared/hooks/components/save-scope-context";
import type { Block } from "@/shared/desktop-state/logic/types";
import type { BranchTarget } from "@/editor/node-detail/tree/logic/tree-model";
import type { TreeBlockEvents } from "@/editor/block-editor/logic/block-events";
import BlockTodos from "@/editor/node-detail/tree/components/BlockTodos";
import BlockTags from "@/editor/node-detail/tree/components/BlockTags";
import BlockImages from "@/editor/node-detail/tree/components/BlockImages";
import BlockState from "@/editor/node-detail/tree/components/BlockState";

// Typ událostí bloku se skládá v editor/block-editor/logic/block-events.ts (sdílený se záložkou Strom
// i s Editorem bloku v zásuvce); re-export tady kvůli zpětné kompatibilitě stávajících importů.
export type { TreeBlockEvents } from "@/editor/block-editor/logic/block-events";

export default function TreeBlock({
  block,
  depth,
  targets,
  disabled,
  expanded,
  onToggle,
  onSelectBlock,
  previewUrl,
  events,
}: {
  block: Block;
  depth: number;
  targets: BranchTarget[];
  disabled: boolean;
  expanded: boolean;
  onToggle: () => void;
  /** Klik na číslo bloku otevře jeho Editor v levé zásuvce (App přepne výběr na blok). */
  onSelectBlock?: (blockId: string) => void;
  previewUrl: (path: string) => string | null;
  events: TreeBlockEvents;
}) {
  // Text a název se ukládají až po opuštění pole, aby každý znak nezapisoval revizi.
  const [title, setTitle] = useState(block.title);
  const [text, setText] = useState(block.text);
  useScopedSaveParticipant({ id: `tree-block:${block.id}`, label: `Blok ${block.number}: ${block.title}`,
    dirty: title !== block.title || text !== block.text,
    blocked: "Dokončete název nebo text bloku a vyčkejte na jeho uložení." });
  useEffect(() => setTitle(block.title), [block.title]);
  useEffect(() => setText(block.text), [block.text]);
  const openTodos = block.todos.filter((t) => !t.done).length;
  return (
    <li className={`tree-block tree-status-${block.state.status}`} style={{ "--depth": depth } as React.CSSProperties} data-testid={`tree-block-${block.id}`}>
      <div className="tree-block-head">
        <button type="button" className="tree-toggle" aria-expanded={expanded} aria-label={expanded ? "Sbalit blok" : "Rozbalit blok"} onClick={onToggle}>
          {expanded ? "▾" : "▸"}
        </button>
        <button type="button" className="tree-number" title="Otevřít editor bloku" onClick={() => onSelectBlock?.(block.id)}>{block.number}</button>
        <input className="tree-title" aria-label="Název bloku" value={title} disabled={disabled} onChange={(e) => setTitle(e.target.value)}
          onBlur={() => { if (title.trim() && title !== block.title) events.onTitle(title.trim()); }}
          onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.blur(); }} />
        <span className={`tree-status-chip tree-status-${block.state.status}`}>{block.state.status}</span>
        {block.tags.length > 0 && <span className="tree-head-tags">{block.tags.slice(0, 2).join(" · ")}{block.tags.length > 2 ? ` +${block.tags.length - 2}` : ""}</span>}
        {openTodos > 0 && <span className="tree-head-todos" title="Otevřená TODO">{openTodos} ☐</span>}
        <span className="tree-tools">
          <button type="button" aria-label="Posunout výš" disabled={disabled} onClick={() => events.onMove(-1)}>▲</button>
          <button type="button" aria-label="Posunout níž" disabled={disabled} onClick={() => events.onMove(1)}>▼</button>
          <button type="button" aria-label="Přidat podblok" title="Přidat podblok" disabled={disabled} onClick={events.onAddChild}>+</button>
          <button type="button" aria-label="Odebrat blok" title="Odebrat blok i podbloky" disabled={disabled} onClick={events.onRemove}>✕</button>
        </span>
      </div>
      {expanded && (
        <div className="tree-block-body">
          <code className="tree-id" title="ID bloku (dohledatelné přes /api/desktop-v3/trace)">{block.id}</code>
          <textarea aria-label="Text bloku" rows={4} value={text} disabled={disabled} placeholder="Popis kroku: co se má stát, jak to má vypadat."
            onChange={(e) => setText(e.target.value)}
            onBlur={() => { if (text !== block.text) events.onText(text); }} />
          <BlockTags tags={block.tags} disabled={disabled} onAdd={events.onAddTag} onRemove={events.onRemoveTag} onPick={events.onPickTag} />
          <BlockTodos todos={block.todos} disabled={disabled} onToggle={events.onToggleTodo} onRemove={events.onRemoveTodo} onAdd={events.onAddTodo} />
          <BlockImages images={block.images} disabled={disabled} previewUrl={previewUrl} onAdd={events.onAddImage} onRemove={events.onRemoveImage} />
          <BlockState state={block.state} targets={targets} disabled={disabled} onStatus={events.onStatus} onCondition={events.onCondition} onBranch={events.onBranch} />
        </div>
      )}
    </li>
  );
}
