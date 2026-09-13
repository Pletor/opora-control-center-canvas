import { useEffect, useRef, useState } from "react";
import {
  SLASH_COMMANDS,
  completeLink,
  indentBlock,
  insertSibling,
  linkParts,
  linkQuery,
  outdentBlock,
  parseBlocks,
  removeBlock,
  serializeBlocks,
  type Block,
} from "@/editor/node-detail/content/logic/block-commands";
import "@/editor/node-detail/content/styles/block-outline.css";

export type LinkTarget = { id: string; name: string; kind: string };
type Menu = { kind: "slash" | "link"; blockId: string; query: string } | null;

/** Odkaz míří na existující uzel: hledá se podle ID i podle jména, jinak zůstane nevyřešený. */
export function resolveTarget(name: string, targets: LinkTarget[]) {
  const key = name.trim().toLocaleLowerCase();
  return (
    targets.find((t) => t.id === name.trim()) ??
    targets.find((t) => t.name.trim().toLocaleLowerCase() === key) ??
    null
  );
}

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
  const [menu, setMenu] = useState<Menu>(null);
  const [active, setActive] = useState(0);
  const emitted = useRef(serializeBlocks(parseBlocks(value)));
  const fields = useRef(new Map<string, HTMLTextAreaElement>());

  useEffect(() => {
    // Vnější změna (načtení, konflikt, zahození draftu) přepíše lokální bloky.
    if (value !== emitted.current) {
      setBlocks(parseBlocks(value));
      emitted.current = value;
      setMenu(null);
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
    const text = serializeBlocks(next);
    emitted.current = text;
    onChange(text);
  }

  function change(index: number, text: string, caret: number) {
    const next = blocks.map((b, i) => (i === index ? { ...b, text } : b));
    commit(next);
    const block = next[index];
    const query = linkQuery(text, caret);
    if (query !== null) setMenu({ kind: "link", blockId: block.id, query });
    else if (text.startsWith("/")) setMenu({ kind: "slash", blockId: block.id, query: text.slice(1) });
    else setMenu(null);
    setActive(0);
  }

  const menuItems: { key: string; label: string; hint: string; run: () => void }[] = (() => {
    if (!menu) return [];
    const index = blocks.findIndex((b) => b.id === menu.blockId);
    if (index < 0) return [];
    const block = blocks[index];
    const field = fields.current.get(block.id);
    const caret = field ? field.selectionStart : block.text.length;
    if (menu.kind === "link") {
      const query = menu.query.trim().toLocaleLowerCase();
      return targets
        .filter((t) => !query || t.name.toLocaleLowerCase().includes(query) || t.id.toLocaleLowerCase().includes(query))
        .slice(0, 8)
        .map((t) => ({
          key: t.id,
          label: t.name,
          hint: t.kind === "sector" ? "sektor" : "uzel",
          run: () => {
            const done = completeLink(block.text, caret, t.name);
            commit(
              blocks.map((b, i) => (i === index ? { ...b, text: done.text } : b)),
              { id: block.id, caret: done.caret },
            );
            setMenu(null);
          },
        }));
    }
    const query = menu.query.trim().toLocaleLowerCase();
    return SLASH_COMMANDS.filter((c) => !query || c.label.toLocaleLowerCase().includes(query)).map((command) => ({
      key: command.id,
      label: command.label,
      hint: command.hint,
      run: () => {
        const rest = block.text.startsWith("/") ? "" : block.text;
        setMenu(null);
        if (command.id === "indent" || command.id === "outdent") {
          const moved = (command.id === "indent" ? indentBlock : outdentBlock)(blocks, index);
          if (moved) commit(moved, { id: block.id, caret: rest.length });
          return;
        }
        if (command.id === "agent") {
          onAgentTask?.(rest);
          return;
        }
        if (command.id === "sibling") {
          const created = insertSibling(
            blocks.map((b, i) => (i === index ? { ...b, text: rest } : b)),
            index,
            rest.length,
          );
          commit(created.blocks, { id: created.focus, caret: 0 });
          return;
        }
        const applied = command.apply(rest);
        if (applied === null) return;
        commit(
          blocks.map((b, i) => (i === index ? { ...b, text: applied } : b)),
          { id: block.id, caret: applied.length },
        );
        if (command.id === "link") setMenu({ kind: "link", blockId: block.id, query: "" });
      },
    }));
  })();

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

  return (
    <div className="block-outline" data-testid={testId} aria-label={label} role="group">
      {blocks.map((block, index) => {
        const parts = linkParts(block.text).filter((p) => p.link);
        return (
          <div
            key={block.id}
            className="block-row"
            data-testid="block-row"
            data-depth={block.depth}
            style={{ marginInlineStart: block.depth * 22 }}
          >
            <span className="block-bullet" aria-hidden="true">
              •
            </span>
            <textarea
              ref={(el) => {
                if (el) fields.current.set(block.id, el);
                else fields.current.delete(block.id);
              }}
              className="block-input"
              aria-label={label + " · blok " + (index + 1)}
              rows={1}
              readOnly={readOnly}
              value={block.text}
              placeholder={index === 0 ? "Pište. Enter = další blok, Tab = zanořit, / = příkazy" : ""}
              onChange={(e) => !readOnly && change(index, e.target.value.replace(/\n/g, " "), e.target.selectionStart)}
              onKeyDown={(e) => keyDown(e, index)}
              onPaste={(e) => paste(e, index)}
              onBlur={() => window.setTimeout(() => setMenu((m) => (m && m.blockId === block.id ? null : m)), 150)}
            />
            {parts.length > 0 && (
              <span className="block-links">
                {parts.map((part, i) => {
                  const target = resolveTarget(part.text, targets);
                  return target ? (
                    <button
                      key={i}
                      type="button"
                      className="block-link"
                      data-testid="block-link"
                      onClick={() => onOpenNode?.(target.id)}
                      title={"Otevřít uzel " + target.name}
                    >
                      ↗ {target.name}
                    </button>
                  ) : (
                    <span key={i} className="block-link unresolved" data-testid="block-link-unresolved">
                      ? {part.text}
                    </span>
                  );
                })}
              </span>
            )}
            {menu && menu.blockId === block.id && (
              <ul
                className="block-menu"
                role="listbox"
                aria-label={menu.kind === "slash" ? "Paleta příkazů" : "Odkaz na uzel"}
                data-testid="block-menu"
              >
                <li className="block-menu-head" role="presentation">
                  {menu.kind === "slash" ? "Příkazy · Esc zavře" : "Existující uzly · Esc zavře"}
                </li>
                {menuItems.map((item, i) => (
                  <li key={item.key} role="presentation">
                    <button
                      type="button"
                      role="option"
                      aria-selected={i === Math.min(active, menuItems.length - 1)}
                      className={i === Math.min(active, menuItems.length - 1) ? "active" : ""}
                      onMouseDown={(e) => {
                        e.preventDefault();
                        item.run();
                      }}
                    >
                      <span>{item.label}</span>
                      <kbd>{item.hint}</kbd>
                    </button>
                  </li>
                ))}
                {!menuItems.length && <li className="block-menu-empty" role="presentation">Nic neodpovídá. Esc zavře.</li>}
              </ul>
            )}
          </div>
        );
      })}
    </div>
  );
}
