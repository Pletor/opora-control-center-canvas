// Události jednoho bloku, čisté bez Reactu: skládají mutace z tree-model a posílají je přes `run` (zámek
// zápisu drží volající). Používá je jak záložka Strom (`blockEvents`), tak Editor bloku v zásuvce
// (`blockEditorEvents`, navíc porty a klik na podblok).
import type { BlockStatus, Branch, DesktopState } from "@/shared/desktop-state/logic/types";
import { nodeWorkflowOf } from "@/shared/desktop-state/logic/types";
import {
  addBlock, addBlockPort, addImage, addTag, addTodo, moveBlock, removeBlock, removeBlockPort, removeImage,
  removeTag, removeTodo, renameBlockPort, setBranch, toggleTodo, updateBlock,
} from "@/editor/node-detail/tree/logic/tree-model";

export type TreeBlockEvents = {
  onTitle: (title: string) => void;
  onText: (text: string) => void;
  onStatus: (status: BlockStatus) => void;
  onCondition: (condition: string) => void;
  onBranch: (via: "onMet" | "onUnmet", branch: Branch) => void;
  onAddChild: () => void;
  onMove: (delta: -1 | 1) => void;
  onRemove: () => void;
  onAddTodo: (text: string, assignee: string) => Promise<boolean>;
  onToggleTodo: (todoId: string) => void;
  onRemoveTodo: (todoId: string) => void;
  onAddTag: (tag: string) => Promise<boolean>;
  onRemoveTag: (tag: string) => void;
  onPickTag?: (tag: string) => void;
  onAddImage: (path: string, caption: string) => Promise<boolean>;
  onRemoveImage: (imageId: string) => void;
};

type Run = (fn: (current: DesktopState) => DesktopState) => Promise<boolean>;

/**
 * Události jednoho bloku pro Strom. `extras.onAddChild` se zavolá až po úspěšném přidání podbloku
 * (Strom tím rozbalí rodiče); `extras.onPickTag` bublá klik na štítek do filtru plátna.
 */
export function blockEvents(
  nodeId: string,
  blockId: string,
  run: Run,
  extras?: { onPickTag?: (tag: string) => void; onAddChild?: () => void },
): TreeBlockEvents {
  return {
    onTitle: (title) => run(updateBlock(nodeId, blockId, { title })),
    onText: (text) => run(updateBlock(nodeId, blockId, { text })),
    onStatus: (status) =>
      run((s) => updateBlock(nodeId, blockId, { state: { ...nodeWorkflowOf(s, nodeId).blocks.find((b) => b.id === blockId)!.state, status } })(s)),
    onCondition: (condition) =>
      run((s) => updateBlock(nodeId, blockId, { state: { ...nodeWorkflowOf(s, nodeId).blocks.find((b) => b.id === blockId)!.state, condition } })(s)),
    onBranch: (via, branch) => run(setBranch(nodeId, blockId, via, branch)),
    onAddChild: () => { void run(addBlock(nodeId, blockId)).then((ok) => { if (ok) extras?.onAddChild?.(); }); },
    onMove: (delta) => run(moveBlock(nodeId, blockId, delta)),
    onRemove: () => run(removeBlock(nodeId, blockId)),
    onAddTodo: (text, assignee) => run(addTodo(nodeId, blockId, text, assignee)),
    onToggleTodo: (todoId) => run(toggleTodo(nodeId, blockId, todoId)),
    onRemoveTodo: (todoId) => run(removeTodo(nodeId, blockId, todoId)),
    onAddTag: (tag) => run(addTag(nodeId, blockId, tag)),
    onRemoveTag: (tag) => run(removeTag(nodeId, blockId, tag)),
    onPickTag: extras?.onPickTag,
    onAddImage: (path, caption) => run(addImage(nodeId, blockId, path, caption)),
    onRemoveImage: (imageId) => run(removeImage(nodeId, blockId, imageId)),
  };
}

export type BlockEditorEvents = TreeBlockEvents & {
  onAddPort: () => void;
  onRenamePort: (portId: string, label: string) => void;
  onRemovePort: (portId: string) => void;
  /** Klik na řádek podbloku v sekci „Podbloky“: Editor se přepne na ten podblok. */
  onSelectChild: (blockId: string) => void;
};

/** Události bloku pro Editor v levé zásuvce: totéž jako Strom, plus porty a klik na podblok. */
export function blockEditorEvents(
  nodeId: string,
  blockId: string,
  run: Run,
  extras: { onSelectChild: (blockId: string) => void; onPickTag?: (tag: string) => void },
): BlockEditorEvents {
  return {
    ...blockEvents(nodeId, blockId, run, { onPickTag: extras.onPickTag }),
    onAddPort: () => run(addBlockPort(nodeId, blockId)),
    onRenamePort: (portId, label) => run(renameBlockPort(nodeId, blockId, portId, label)),
    onRemovePort: (portId) => run(removeBlockPort(nodeId, blockId, portId)),
    onSelectChild: extras.onSelectChild,
  };
}
