import { useEffect, useRef, useState } from "react";
import {
  indentBlock,
  insertSibling,
  outdentBlock,
  parseBlocks,
  removeBlock,
  serializeBlocks,
  type Block,
} from "@/editor/node-detail/content/logic/block-commands";
import { hasChildren, prunedCollapsed, visibleIndexes } from "@/editor/node-detail/content/logic/block-tree";
import { type LinkTarget } from "@/editor/node-detail/content/logic/block-view";
import { useBlockMenu } from "@/editor/node-detail/content/logic/use-block-menu";
import BlockRow from "@/editor/node-detail/content/components/BlockRow";
import BlockMenu from "@/editor/node-detail/content/components/BlockMenu";
import "@/editor/node-detail/content/styles/block-outline.css";

export type { LinkTarget };

/**
 * Osnova uzlu: plochý seznam bloků s hloubkou, vykreslený jako odrážkový dokument.
 * Rodič drží bloky, kurzor, paletu i sbalení a každou změnu posílá ven jedním `onChange`
 * se serializovaným textem; řádek (`BlockRow`) a paleta (`BlockMenu`) jen kreslí.
 */
export default function BlockOutline({
  value,
  readOnly,
  targets,
  label,
  testId,
  onChange,
  onOpenNode,
  onAgentTask,
}: {
  value: string;
  readOnly: boolean;
  targets: LinkTarget[];
  label: string;
  testId: string;
  onChange: (text: string) => void;
  onOpenNode?: (nodeId: string) => void;
  onAgentTask?: (blockText: string) => void;
}) {
  const [blocks, setBlocks] = useState<Block[]>(() => parseBlocks(value));
  const [focus, setFocus] = useState<{ id: string; caret: number } | null>(null);
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(() => new Set<string>());
  const emitted = useRef(serializeBlocks(parseBlocks(value)));
  const fields = useRef(new Map<string, HTMLTextAreaElement>());
  const { menu, setMenu, active, setActive, syncMenu, items: menuItems } = useBlockMenu({
    blocks,
    targets,
    caretOf: (block) => {
      const field = fields.current.get(block.id);
      return field ? field.selectionStart : block.text.length;
    },
    commit: (next, focused) => commit(next, focused),
    onAgentTask,
  });

  useEffect(() => {
    // Vnější změna (načtení, konflikt, zahození draftu) přepíše lokální bloky.
    if (value !== emitted.current) {
      setBlocks(parseBlocks(value));
      emitted.current = value;
      setMenu(null);
      setCollapsed(new Set<string>());
    }
  }, [value]);

  useEffect(() => {
    // Jen vyžádaný přesun kurzoru: běžné psaní si pozici řídí samo.
    if (!focus) return;
    const field = fields.current.get(focus.id);
    if (!field) return;
    field.focus();
    const caret = Math.min(focus.caret, field.value.length);
    field.setSelectionRange(caret, caret);
  }, [focus]);

  function commit(next: Block[], focused?: { id: string; caret: number }) {
    setBlocks(next);
    if (focused) setFocus(focused);
    // Sbalený blok, který přišel o děti, se rozbalí sám, aby text nikde nezůstal schovaný.
    setCollapsed((prev) => {
      if (!prev.size) return prev;
      const kept = prunedCollapsed(next, prev);
      return kept.size === prev.size ? prev : kept;
    });
    const text = serializeBlocks(next);
    emitted.current = text;
    onChange(text);
  }

  function change(index: number, text: string, caret: number) {
    const next = blocks.map((b, i) => (i === index ? { ...b, text } : b));
    commit(next);
    syncMenu(next[index].id, text, caret);
  }

  function keyDown(event: React.KeyboardEvent<HTMLTextAreaElement>, index: number) {
    const field = event.currentTarget;
    const caret = field.selectionStart;
    const block = blocks[index];
    if (event.key === "Escape") {
      event.preventDefault();
      if (menu) setMenu(null);
      else field.blur();
      return;
    }
    if (menu && menuItems.length && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
      event.preventDefault();
      setActive((a) => (a + (event.key === "ArrowDown" ? 1 : menuItems.length - 1)) % menuItems.length);
      return;
    }
    if (event.nativeEvent.isComposing) return; // Rozepsané IME slovo není příkaz.
    if (menu && menuItems.length && (event.key === "Enter" || event.key === "Tab")) {
      event.preventDefault();
      menuItems[Math.min(active, menuItems.length - 1)].run();
      return;
    }
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      onAgentTask?.(block.text);
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      if (readOnly) return;
      const created = insertSibling(blocks, index, caret);
      commit(created.blocks, { id: created.focus, caret: created.caret });
      return;
    }
    if (event.key === "Tab") {
      event.preventDefault();
      if (readOnly) return;
      const moved = event.shiftKey ? outdentBlock(blocks, index) : indentBlock(blocks, index);
      if (moved) commit(moved, { id: block.id, caret });
      return;
    }
    if (event.key === "Backspace" && caret === 0 && !block.text && !readOnly) {
      const removed = removeBlock(blocks, index);
      if (removed) {
        event.preventDefault();
        commit(removed.blocks, { id: removed.focus, caret: removed.caret });
      }
    }
  }

  function paste(event: React.ClipboardEvent<HTMLTextAreaElement>, index: number) {
    const pasted = event.clipboardData.getData("text/plain");
    if (!pasted.includes("\n") || readOnly) return;
    event.preventDefault();
    const base = blocks[index];
    const added = parseBlocks(pasted).map((b) => ({ ...b, depth: Math.min(base.depth + b.depth, 8) }));
    const next = [...blocks];
    next.splice(index, 1, { ...base, text: base.text + added[0].text }, ...added.slice(1));
    commit(next, { id: added.length > 1 ? added[added.length - 1].id : base.id, caret: 0 });
  }

  function toggle(id: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (!next.delete(id)) next.add(id);
      return next;
    });
  }

  return (
    <div className="block-outline" data-testid={testId} aria-label={label} role="group">
      {visibleIndexes(blocks, collapsed).map((index) => {
        const block = blocks[index];
        return (
          <BlockRow
            key={block.id}
            block={block}
            index={index}
            label={label}
            readOnly={readOnly}
            targets={targets}
            collapsible={hasChildren(blocks, index)}
            collapsed={collapsed.has(block.id)}
            registerField={(el) => {
              if (el) fields.current.set(block.id, el);
              else fields.current.delete(block.id);
            }}
            onToggle={() => toggle(block.id)}
            onChange={(text, caret) => change(index, text, caret)}
            onKeyDown={(e) => keyDown(e, index)}
            onPaste={(e) => paste(e, index)}
            onBlur={() => window.setTimeout(() => setMenu((m) => (m && m.blockId === block.id ? null : m)), 150)}
            onOpenNode={onOpenNode}
          >
            {menu && menu.blockId === block.id && (
              <BlockMenu kind={menu.kind} items={menuItems} active={active} />
            )}
          </BlockRow>
        );
      })}
    </div>
  );
}
