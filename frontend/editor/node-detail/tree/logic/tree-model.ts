// Čistý model stromu obsahu uzlu: číslování bloků podle rodiče a pořadí, přesuny, větve, mutace stavu.
// Bez Reactu; testuje se samostatně. Komponenty stromu jen volají tyto funkce a bublají události.
import type { Block, BlockPortDef, Branch, BranchKind, DesktopState, ImageRef, NodeDone, NodeWorkflowFull, Todo } from "@/shared/desktop-state/logic/types";
import { blockPorts, emptyBranch, MAX_BLOCK_PORT_LABEL, MAX_BLOCK_PORTS, nodeWorkflowOf } from "@/shared/desktop-state/logic/types";

export function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `id-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function emptyBlock(parentBlockId = ""): Block {
  return {
    id: newId(), number: "", title: "Nový blok", text: "", tags: [], todos: [], images: [], parentBlockId, ports: [],
    state: { status: "open", condition: "", onMet: emptyBranch(), onUnmet: emptyBranch() },
  };
}

/** Bloky přečíslované do tvaru 1, 1.1, 1.2, 2 podle rodiče a pořadí v poli; pořadí sourozenců = pořadí v poli. */
export function renumber(blocks: Block[]): Block[] {
  const byParent = new Map<string, Block[]>();
  for (const block of blocks) {
    const list = byParent.get(block.parentBlockId) ?? [];
    list.push(block);
    byParent.set(block.parentBlockId, list);
  }
  const numbered = new Map<string, string>();
  const walk = (parent: string, prefix: string) => {
    (byParent.get(parent) ?? []).forEach((block, index) => {
      const number = prefix ? `${prefix}.${index + 1}` : String(index + 1);
      numbered.set(block.id, number);
      walk(block.id, number);
    });
  };
  walk("", "");
  // Bloky s neexistujícím rodičem (osiřelé) se připojí na kořen, aby nezmizely.
  const known = new Set(blocks.map((b) => b.id));
  return blocks.map((block) => {
    const orphan = block.parentBlockId && !known.has(block.parentBlockId);
    const number = numbered.get(block.id) ?? String(numbered.size + 1);
    return { ...block, number, parentBlockId: orphan ? "" : block.parentBlockId };
  });
}

export function numberKey(number: string): number[] {
  return number.split(".").map((part) => Number(part));
}

export function compareNumbers(a: string, b: string): number {
  const x = numberKey(a);
  const y = numberKey(b);
  for (let i = 0; i < Math.max(x.length, y.length); i += 1) {
    const d = (x[i] ?? -1) - (y[i] ?? -1);
    if (d !== 0) return d;
  }
  return 0;
}

/** Bloky ve stromovém pořadí (podle čísla) s hloubkou pro odsazení. */
export function ordered(blocks: Block[]): { block: Block; depth: number }[] {
  return blocks
    .slice()
    .sort((a, b) => compareNumbers(a.number, b.number))
    .map((block) => ({ block, depth: block.number.split(".").length - 1 }));
}

export function childrenOf(blocks: Block[], parentId: string): Block[] {
  return blocks.filter((b) => b.parentBlockId === parentId);
}

function withBlocks(state: DesktopState, nodeId: string, fn: (blocks: Block[], node: NodeWorkflowFull) => Block[]): DesktopState {
  const node = nodeWorkflowOf(state, nodeId);
  return { ...state, nodes: { ...state.nodes, [nodeId]: { ...node, blocks: renumber(fn(node.blocks, node)) } } };
}

export const addBlock = (nodeId: string, parentBlockId = "") => (state: DesktopState) =>
  withBlocks(state, nodeId, (blocks) => blocks.concat([emptyBlock(parentBlockId)]));

export const updateBlock = (nodeId: string, blockId: string, patch: Partial<Omit<Block, "id" | "number" | "parentBlockId">>) => (state: DesktopState) =>
  withBlocks(state, nodeId, (blocks) => blocks.map((b) => (b.id === blockId ? { ...b, ...patch } : b)));

/** Přesun mezi sourozenci: prohodí pořadí v poli, číslo se přepočítá. */
export const moveBlock = (nodeId: string, blockId: string, delta: -1 | 1) => (state: DesktopState) =>
  withBlocks(state, nodeId, (blocks) => {
    const index = blocks.findIndex((b) => b.id === blockId);
    if (index < 0) return blocks;
    const parent = blocks[index].parentBlockId;
    const siblings = blocks.map((b, i) => ({ b, i })).filter(({ b }) => b.parentBlockId === parent);
    const at = siblings.findIndex(({ b }) => b.id === blockId);
    const swap = siblings[at + delta];
    if (!swap) return blocks;
    const copy = blocks.slice();
    [copy[index], copy[swap.i]] = [copy[swap.i], copy[index]];
    return copy;
  });

/** Odebrání bloku i celého podstromu; větve mířící na odebrané bloky se vyprázdní, aby stav zůstal platný. */
export const removeBlock = (nodeId: string, blockId: string) => (state: DesktopState) =>
  withBlocks(state, nodeId, (blocks) => {
    const removed = new Set<string>([blockId]);
    let grew = true;
    while (grew) {
      grew = false;
      for (const b of blocks) if (!removed.has(b.id) && removed.has(b.parentBlockId)) { removed.add(b.id); grew = true; }
    }
    const clean = (branch: Branch): Branch => (branch.kind === "block" && removed.has(branch.targetId) ? emptyBranch() : branch);
    return blocks
      .filter((b) => !removed.has(b.id))
      .map((b) => ({ ...b, state: { ...b.state, onMet: clean(b.state.onMet), onUnmet: clean(b.state.onUnmet) } }));
  });

export const addTodo = (nodeId: string, blockId: string, text: string, assignee = "") =>
  updateBlockWith(nodeId, blockId, (b) => ({ todos: b.todos.concat([{ id: newId(), text, done: false, assignee }]) }));

export const toggleTodo = (nodeId: string, blockId: string, todoId: string) =>
  updateBlockWith(nodeId, blockId, (b) => ({ todos: b.todos.map((t) => (t.id === todoId ? { ...t, done: !t.done } : t)) }));

export const removeTodo = (nodeId: string, blockId: string, todoId: string) =>
  updateBlockWith(nodeId, blockId, (b) => ({ todos: b.todos.filter((t) => t.id !== todoId) }));

export const addTag = (nodeId: string, blockId: string, tag: string) =>
  updateBlockWith(nodeId, blockId, (b) => ({ tags: b.tags.includes(tag) ? b.tags : b.tags.concat([tag]) }));

export const removeTag = (nodeId: string, blockId: string, tag: string) =>
  updateBlockWith(nodeId, blockId, (b) => ({ tags: b.tags.filter((t) => t !== tag) }));

export const addImage = (nodeId: string, blockId: string, path: string, caption = "") =>
  updateBlockWith(nodeId, blockId, (b) => ({ images: b.images.concat([{ id: newId(), path, caption }]) }));

export const removeImage = (nodeId: string, blockId: string, imageId: string) =>
  updateBlockWith(nodeId, blockId, (b) => ({ images: b.images.filter((i) => i.id !== imageId) }));

export const setBranch = (nodeId: string, blockId: string, via: "onMet" | "onUnmet", branch: Branch) =>
  updateBlockWith(nodeId, blockId, (b) => ({ state: { ...b.state, [via]: branch } }));

/** Popisek portu: oříznutý na 80 znaků; prázdný dostane pořadové „Port N“, aby tlačítko nikdy nebylo bezejmenné. */
function portLabel(label: string, index: number): string {
  const value = label.trim().slice(0, MAX_BLOCK_PORT_LABEL);
  return value || `Port ${index}`;
}

/** Nový port bloku na konec řady. Nad osmý port se nepřidává; id je unikátní přes newId(). */
export const addBlockPort = (nodeId: string, blockId: string, label = "") =>
  updateBlockWith(nodeId, blockId, (b) => {
    const ports = blockPorts(b);
    if (ports.length >= MAX_BLOCK_PORTS) return {};
    return { ports: ports.concat([{ id: newId(), label: portLabel(label, ports.length + 1) }]) };
  });

export const renameBlockPort = (nodeId: string, blockId: string, portId: string, label: string) =>
  updateBlockWith(nodeId, blockId, (b) => ({
    ports: blockPorts(b).map((p, index) => (p.id === portId ? { ...p, label: portLabel(label, index + 1) } : p)),
  }));

/** Odebrání portu. Vazbu, která z portu vedla, uklízí graf; stav uzlu o ní neví. */
export const removeBlockPort = (nodeId: string, blockId: string, portId: string) =>
  updateBlockWith(nodeId, blockId, (b) => ({ ports: blockPorts(b).filter((p) => p.id !== portId) }));

/**
 * Uzavření karty: člověk potvrzuje (`by: "human"`), agent smí jen navrhnout (`by: "agent", confirmed: false`).
 * Čas se razítkuje teď, pokud ho volající nedodá; ostatní pole zůstávají z předchozího stavu.
 */
export const setDone = (nodeId: string, patch: Partial<NodeDone>) => (state: DesktopState): DesktopState => {
  const node = nodeWorkflowOf(state, nodeId);
  const done: NodeDone = { ...node.done, ...patch, at: patch.at ?? new Date().toISOString() };
  return { ...state, nodes: { ...state.nodes, [nodeId]: { ...node, done } } };
};

function updateBlockWith(nodeId: string, blockId: string, fn: (b: Block) => Partial<Block>) {
  return (state: DesktopState) => withBlocks(state, nodeId, (blocks) => blocks.map((b) => (b.id === blockId ? { ...b, ...fn(b) } : b)));
}

export type BranchTarget = { kind: Exclude<BranchKind, "none">; id: string; label: string };

/** Nabídka cílů větve: jiné bloky uzlu, uzly grafu, akce uzlu. Blok sám sobě cílem není. */
export function branchTargets(node: NodeWorkflowFull, blockId: string, graphNodes: { id: string; name: string }[]): BranchTarget[] {
  return [
    ...ordered(node.blocks).filter(({ block }) => block.id !== blockId).map(({ block }) => ({ kind: "block" as const, id: block.id, label: `${block.number} ${block.title}` })),
    ...graphNodes.map((n) => ({ kind: "node" as const, id: n.id, label: n.name })),
    ...node.actions.map((a) => ({ kind: "action" as const, id: a.id, label: a.label })),
  ];
}

export function branchLabel(branch: Branch, targets: BranchTarget[]): string {
  if (branch.kind === "none") return "nic dalšího";
  const target = targets.find((t) => t.kind === branch.kind && t.id === branch.targetId);
  return target ? `${branch.kind === "block" ? "blok" : branch.kind === "node" ? "uzel" : "akce"}: ${target.label}` : `${branch.kind}: ${branch.targetId}`;
}

export type { Block, BlockPortDef, Todo, ImageRef, Branch, NodeDone };
