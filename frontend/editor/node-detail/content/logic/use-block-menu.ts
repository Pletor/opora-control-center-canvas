/** Paleta osnovy: co se nabízí po `/` a po `[[` a co se stane po potvrzení.
 *  Drží jen svůj stav (co je otevřené, co je zvýrazněné); bloky ukládá dál rodič přes `commit`. */
import { useState } from "react";
import {
  SLASH_COMMANDS,
  completeLink,
  indentBlock,
  insertSibling,
  linkQuery,
  outdentBlock,
  type Block,
} from "@/editor/node-detail/content/logic/block-commands";
import type { LinkTarget } from "@/editor/node-detail/content/logic/block-view";

/** Položka palety: co se v seznamu ukáže a co se stane po potvrzení. */
export type BlockMenuItem = { key: string; label: string; hint: string; run: () => void };
export type BlockMenuState = { kind: "slash" | "link"; blockId: string; query: string } | null;

export function useBlockMenu({
  blocks,
  targets,
  caretOf,
  commit,
  onAgentTask,
}: {
  blocks: Block[];
  targets: LinkTarget[];
  /** Kde je kurzor v poli daného bloku; paleta z něj doplňuje odkaz na správné místo. */
  caretOf: (block: Block) => number;
  commit: (next: Block[], focused?: { id: string; caret: number }) => void;
  onAgentTask?: (blockText: string) => void;
}) {
  const [menu, setMenu] = useState<BlockMenuState>(null);
  const [active, setActive] = useState(0);

  /** Psaní otevírá a zavírá paletu samo: `[[` hledá uzel, `/` na začátku řádku hledá příkaz. */
  function syncMenu(blockId: string, text: string, caret: number) {
    const query = linkQuery(text, caret);
    if (query !== null) setMenu({ kind: "link", blockId, query });
    else if (text.startsWith("/")) setMenu({ kind: "slash", blockId, query: text.slice(1) });
    else setMenu(null);
    setActive(0);
  }

  const items: BlockMenuItem[] = (() => {
    if (!menu) return [];
    const index = blocks.findIndex((b) => b.id === menu.blockId);
    if (index < 0) return [];
    const block = blocks[index];
    const caret = caretOf(block);
    const query = menu.query.trim().toLocaleLowerCase();
    if (menu.kind === "link") {
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

  return { menu, setMenu, active, setActive, syncMenu, items };
}
