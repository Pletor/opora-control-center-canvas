// Rodič záložky Strom: drží stav Desktop v3, jeden zámek zápisu a rozbalené bloky. Skládá TreeBlock
// pro každý blok v pořadí čísel a překládá události dílků na mutace z tree-model.
import { useLayoutEffect, useRef, useState } from "react";
import { useDesktopState } from "@/shared/desktop-state/logic/state-store";
import { nodeWorkflowOf, type DesktopState } from "@/shared/desktop-state/logic/types";
import { addBlock, branchTargets, ordered } from "@/editor/node-detail/tree/logic/tree-model";
import { blockEvents } from "@/editor/block-editor/logic/block-events";
import TreeBlock from "@/editor/node-detail/tree/components/TreeBlock";
import "@/editor/node-detail/tree/styles/tree.css";

export default function NodeTree({
  project,
  workspace,
  nodeId,
  graphNodes,
  onPickTag,
  onSelectBlock,
}: {
  project: string;
  workspace: string;
  nodeId: string;
  /** Uzly grafu jako cíle větví „uzel“. */
  graphNodes: { id: string; name: string }[];
  /** Klik na štítek: filtr plátna. */
  onPickTag?: (tag: string) => void;
  /** Klik na číslo bloku: otevře jeho Editor v levé zásuvce. */
  onSelectBlock?: (blockId: string) => void;
}) {
  const { state, readOnly, loading, error, reload, mutate } = useDesktopState(project, workspace);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  // Jeden zápis najednou za celý strom (stejný důvod jako NodeWorkflowPanel: jeden dokument, jedna revize).
  const lock = useRef(false);
  const [busy, setBusy] = useState(false);
  const [settled, setSettled] = useState(0);
  useLayoutEffect(() => { lock.current = false; }, [settled]);

  async function run(fn: (current: DesktopState) => DesktopState): Promise<boolean> {
    if (lock.current) return false;
    lock.current = true;
    setBusy(true);
    try {
      return await mutate(fn);
    } finally {
      setBusy(false);
      setSettled((n) => n + 1);
    }
  }

  const node = nodeWorkflowOf(state, nodeId);
  const rows = ordered(node.blocks);
  const disabled = readOnly || busy;
  const previewUrl = (path: string) =>
    /\.(png|jpe?g|gif|webp|svg)$/i.test(path)
      ? `/api/workspace/image?project=${encodeURIComponent(project)}&workspace=${encodeURIComponent(workspace)}&path=${encodeURIComponent(path)}`
      : null;

  return (
    <section className="node-tree" aria-label="Strom obsahu uzlu">
      {readOnly && <p role="status" className="v3-readonly">Main je pouze pro čtení; změny se neuloží.</p>}
      {loading && <p role="status">Načítám strom…</p>}
      {error && (
        <p role="alert" className="v3-error">
          {error} <button type="button" onClick={reload}>Znovu načíst</button>
        </p>
      )}
      {!loading && (
        <>
          <p className="v3-note">
            Každý blok má číslo a ID. Stav říká, co se stane při splnění a při nesplnění. Agent dostává do podkladů
            celý obraz, ale pracuje jen na prvním otevřeném bloku.
          </p>
          {rows.length === 0 && <p className="v3-empty">Zatím žádný blok. Začněte prvním krokem.</p>}
          <ul className="tree-list">
            {rows.map(({ block, depth }) => (
              <TreeBlock
                key={block.id}
                block={block}
                depth={depth}
                targets={branchTargets(node, block.id, graphNodes)}
                disabled={disabled}
                expanded={!!expanded[block.id]}
                onToggle={() => setExpanded((e) => ({ ...e, [block.id]: !e[block.id] }))}
                onSelectBlock={onSelectBlock}
                previewUrl={previewUrl}
                events={blockEvents(nodeId, block.id, run, { onPickTag, onAddChild: () => setExpanded((e) => ({ ...e, [block.id]: true })) })}
              />
            ))}
          </ul>
          <div className="v3-row">
            <button type="button" disabled={disabled} onClick={() => run(addBlock(nodeId))}>+ Blok</button>
          </div>
        </>
      )}
    </section>
  );
}
