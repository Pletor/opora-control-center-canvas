// Editor jednoho bloku v levé zásuvce: název, popis, porty, stav a větvení, štítky, checklist, obrázky
// a podbloky. Dílek nic neukládá; každá změna bublá nahoru přes `events`, ukládá rodič (App / NodeTree).
import { useEffect, useState } from "react";
import { blockPorts, type Block } from "@/shared/desktop-state/logic/types";
import type { BranchTarget } from "@/editor/node-detail/tree/logic/tree-model";
import type { BlockEditorEvents } from "@/editor/block-editor/logic/block-events";
import BlockPortsEditor from "@/editor/block-editor/components/BlockPortsEditor";
import BlockState from "@/editor/node-detail/tree/components/BlockState";
import BlockTags from "@/editor/node-detail/tree/components/BlockTags";
import BlockTodos from "@/editor/node-detail/tree/components/BlockTodos";
import BlockImages from "@/editor/node-detail/tree/components/BlockImages";
import "@/editor/block-editor/styles/block-editor.css";

export default function BlockEditor({
  node,
  block,
  children,
  targets,
  disabled,
  previewUrl,
  events,
}: {
  node: { id: string; name: string };
  block: Block;
  /** Přímé podbloky tohoto bloku; klik na řádek přepne Editor na ně. */
  children: Block[];
  targets: BranchTarget[];
  disabled: boolean;
  previewUrl: (path: string) => string | null;
  events: BlockEditorEvents;
}) {
  const [title, setTitle] = useState(block.title);
  const [text, setText] = useState(block.text);
  useEffect(() => setTitle(block.title), [block.title]);
  useEffect(() => setText(block.text), [block.text]);
  return (
    <div className="block-editor" aria-label={`Editor bloku ${block.number} v uzlu ${node.name}`}>
      <div className="block-editor__eyebrow">
        <span className="block-editor__kicker">BLOK {block.number}</span>
        <code className="block-editor__id" title="ID bloku (dohledatelné přes /api/desktop-v3/trace)">{block.id}</code>
      </div>
      <label className="block-editor__field">
        Název bloku
        <input
          className="block-editor__title"
          aria-label="Název bloku"
          value={title}
          disabled={disabled}
          onChange={(e) => setTitle(e.target.value)}
          onBlur={() => { if (title.trim() && title !== block.title) events.onTitle(title.trim()); }}
          onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.blur(); }}
        />
      </label>
      <label className="block-editor__field">
        Popis
        <textarea
          className="block-editor__text"
          aria-label="Popis bloku"
          rows={8}
          value={text}
          disabled={disabled}
          placeholder="Popis kroku: co se má stát, jak to má vypadat."
          onChange={(e) => setText(e.target.value)}
          onBlur={() => { if (text !== block.text) events.onText(text); }}
        />
      </label>
      <BlockPortsEditor ports={blockPorts(block)} disabled={disabled} onAdd={events.onAddPort} onRename={events.onRenamePort} onRemove={events.onRemovePort} />
      <section className="block-editor__section" aria-label="Stav a větvení bloku">
        <h5>Stav a větvení</h5>
        <BlockState state={block.state} targets={targets} disabled={disabled} onStatus={events.onStatus} onCondition={events.onCondition} onBranch={events.onBranch} />
      </section>
      <section className="block-editor__section" aria-label="Štítky bloku">
        <h5>Štítky</h5>
        <BlockTags tags={block.tags} disabled={disabled} onAdd={events.onAddTag} onRemove={events.onRemoveTag} onPick={events.onPickTag} />
      </section>
      <section className="block-editor__section" aria-label="Checklist bloku">
        <BlockTodos todos={block.todos} disabled={disabled} onToggle={events.onToggleTodo} onRemove={events.onRemoveTodo} onAdd={events.onAddTodo} />
      </section>
      <section className="block-editor__section" aria-label="Obrázky bloku">
        <BlockImages images={block.images} disabled={disabled} previewUrl={previewUrl} onAdd={events.onAddImage} onRemove={events.onRemoveImage} />
      </section>
      <section className="block-editor__section" aria-label="Podbloky">
        <h5>Podbloky</h5>
        {children.length === 0 && <p className="block-editor__empty">Zatím žádný podblok.</p>}
        <ul className="block-editor__children">
          {children.map((child) => (
            <li key={child.id}>
              <button type="button" className="block-editor__child" onClick={() => events.onSelectChild(child.id)}>
                <span className="block-editor__child-number">{child.number}</span>
                <span className="block-editor__child-title">{child.title}</span>
              </button>
            </li>
          ))}
        </ul>
        <button type="button" className="block-editor__add" disabled={disabled} onClick={events.onAddChild}>+ Podblok</button>
      </section>
      <footer className="block-editor__foot">
        <span className="block-editor__move">
          <button type="button" aria-label="Posunout výš" disabled={disabled} onClick={() => events.onMove(-1)}>▲</button>
          <button type="button" aria-label="Posunout níž" disabled={disabled} onClick={() => events.onMove(1)}>▼</button>
        </span>
        <button type="button" className="danger" disabled={disabled} onClick={events.onRemove}>Odebrat blok</button>
      </footer>
    </div>
  );
}
