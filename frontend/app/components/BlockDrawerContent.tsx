// Obsah zásuvky pro vybraný blok: spojuje Editor bloku s uloženým stavem Desktop v3 a výběrem v App.
// Ukládá App (přes `desktop.mutate`), tenhle dílek jen skládá props a hlídá, že blok pořád existuje.
import { useEffect } from "react";
import BlockEditor from "@/editor/block-editor/components/BlockEditor";
import { blockEditorEvents } from "@/editor/block-editor/logic/block-events";
import { branchTargets, childrenOf } from "@/editor/node-detail/tree/logic/tree-model";
import type { DesktopStateHandle } from "@/shared/desktop-state/logic/state-store";
import type { NodeWorkflowFull } from "@/shared/desktop-state/logic/types";
import type { CanvasNode } from "@/shared/types/logic/types";

export default function BlockDrawerContent({
  desktop,
  project,
  workspace,
  node,
  workflow,
  blockId,
  linkTargets,
  disabled,
  onSelectBlock,
  onSelectNode,
  onPickTag,
}: {
  desktop: DesktopStateHandle;
  project: string;
  workspace: string;
  node: CanvasNode;
  workflow: NodeWorkflowFull;
  blockId: string;
  /** Uzly grafu jako cíle větví „uzel“. */
  linkTargets: { id: string; name: string }[];
  disabled: boolean;
  /** Klik na podblok: Editor se přepne na něj. */
  onSelectBlock: (blockId: string) => void;
  /** Blok zmizel (smazán jinde) nebo byl právě odebrán: výběr spadne zpět na uzel. */
  onSelectNode: () => void;
  onPickTag: (tag: string) => void;
}) {
  const block = workflow.blocks.find((b) => b.id === blockId);
  // Externí zásah (smazání bloku odjinud) shodí vybraný blok ze stavu; tady se to jen doloží pojistkou,
  // hlavní přepnutí výběru dělá App v useEffect nad `selection`.
  useEffect(() => { if (!block) onSelectNode(); }, [block, onSelectNode]);
  if (!block) return null;
  const previewUrl = (path: string) =>
    /\.(png|jpe?g|gif|webp|svg)$/i.test(path)
      ? `/api/workspace/image?project=${encodeURIComponent(project)}&workspace=${encodeURIComponent(workspace)}&path=${encodeURIComponent(path)}`
      : null;
  const events = blockEditorEvents(node.id, blockId, (fn) => desktop.mutate(fn), { onSelectChild: onSelectBlock, onPickTag });
  return (
    <BlockEditor
      node={{ id: node.id, name: node.name }}
      block={block}
      children={childrenOf(workflow.blocks, blockId)}
      targets={branchTargets(workflow, blockId, linkTargets)}
      disabled={disabled}
      previewUrl={previewUrl}
      events={{ ...events, onRemove: () => { events.onRemove(); onSelectNode(); } }}
    />
  );
}
