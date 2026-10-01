// Čistý model bloků Akce / Pravidla / Podklady u karty: identita bloku na plátně, mutace stavu uzlu a rozmístění.
// Bloky nejsou uzly grafu; žijí ve stavu Desktop v3 pod nodes[nodeId].actions / .rules / .materials.
import type { Node, Edge } from "@xyflow/react";
import type { BlockOffset, CanvasNode, Graph } from "@/shared/types/logic/types";
import type { DesktopState, MaterialKind, NodeAction, NodeMaterial, NodeRule, NodeWorkflowFull, PipelineTemplate, RuleKind } from "@/shared/desktop-state/logic/types";
import { nodeWorkflowOf } from "@/shared/desktop-state/logic/types";

export type BlockPort = "action" | "rule" | "material";
export const BLOCK_PORTS: BlockPort[] = ["action", "rule", "material"];
export const BLOCK_LABEL: Record<BlockPort, string> = { action: "Akce", rule: "Pravidla", material: "Podklady" };
export const BLOCK_COLOR: Record<BlockPort, string> = { action: "#c98a1e", rule: "#c4524a", material: "#5f947f" };
/** Pravoúhlé vedení šipky od karty k bloku: stejné zaoblení a odstup jako vazby grafu (viz board-model). */
const BLOCK_EDGE_PATH = { type: "smoothstep" as const, pathOptions: { borderRadius: 12, offset: 24 } };

/** Výchozí místo bloku: vpravo od karty (272 + mezera 55); akce nad středem, pravidla pod ním, podklady pod
 *  pravidly (nebo na jejich místě, když blok pravidel není vidět). Odtud blok vyjde, než si ho uživatel
 *  odtáhne jinam — pak platí `blockOffsets` uzlu. */
export const BLOCK_OFFSET_X = 327;
export const BLOCK_OFFSET_Y: Record<BlockPort, number> = { action: -21, rule: 189, material: 399 };
export const MATERIAL_OFFSET_WITHOUT_RULES = 189;

export function blockNodeId(nodeId: string, port: BlockPort): string {
  return `block:${port}:${nodeId}`;
}
export function isBlockId(id: string): boolean {
  return id.startsWith("block:");
}
/** Zpátky z id bloku na uzel a port; id karty, komentáře nebo neznámý port vrátí null. */
export function parseBlockId(id: string): { nodeId: string; port: BlockPort } | null {
  const parts = id.split(":");
  if (parts.length < 3 || parts[0] !== "block") return null;
  const port = parts[1] as BlockPort;
  if (!BLOCK_PORTS.includes(port)) return null;
  const nodeId = parts.slice(2).join(":");
  return nodeId ? { nodeId, port } : null;
}

/** Výchozí místo bloku u karty; podklady si stoupnou na řádek pravidel, dokud pravidla nejsou vidět. */
export function defaultBlockOffset(port: BlockPort, rulesShown: boolean): BlockOffset {
  return {
    dx: BLOCK_OFFSET_X,
    dy: port === "material" && !rulesShown ? MATERIAL_OFFSET_WITHOUT_RULES : BLOCK_OFFSET_Y[port],
  };
}

/** Kde blok stojí: odtažené místo uložené na kartě, jinak výchozí. Vždy relativně ke kartě, takže ji následuje. */
export function blockOffsetOf(card: Pick<CanvasNode, "blockOffsets">, port: BlockPort, rulesShown: boolean): BlockOffset {
  return card.blockOffsets?.[port] ?? defaultBlockOffset(port, rulesShown);
}

export function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `id-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function withNode(state: DesktopState, nodeId: string, fn: (n: NodeWorkflowFull) => NodeWorkflowFull): DesktopState {
  return { ...state, nodes: { ...state.nodes, [nodeId]: fn(nodeWorkflowOf(state, nodeId)) } };
}

export function move<T>(items: T[], index: number, delta: number): T[] {
  const target = index + delta;
  if (target < 0 || target >= items.length) return items;
  const copy = items.slice();
  [copy[index], copy[target]] = [copy[target], copy[index]];
  return copy;
}

export const addAction = (nodeId: string, pipeline: PipelineTemplate) => (state: DesktopState) =>
  withNode(state, nodeId, (n) => ({
    ...n,
    actions: n.actions.concat([{ id: newId(), pipelineId: pipeline.id, label: pipeline.label, params: {} }]),
  }));

export const moveAction = (nodeId: string, index: number, delta: number) => (state: DesktopState) =>
  withNode(state, nodeId, (n) => ({ ...n, actions: move(n.actions, index, delta) }));

export const removeAction = (nodeId: string, id: string) => (state: DesktopState) =>
  withNode(state, nodeId, (n) => ({ ...n, actions: n.actions.filter((a) => a.id !== id) }));

export const addRule = (nodeId: string, text: string, kind: RuleKind) => (state: DesktopState) =>
  withNode(state, nodeId, (n) => ({ ...n, rules: n.rules.concat([{ id: newId(), text, kind }]) }));

export const moveRule = (nodeId: string, index: number, delta: number) => (state: DesktopState) =>
  withNode(state, nodeId, (n) => ({ ...n, rules: move(n.rules, index, delta) }));

export const removeRule = (nodeId: string, id: string) => (state: DesktopState) =>
  withNode(state, nodeId, (n) => ({ ...n, rules: n.rules.filter((r) => r.id !== id) }));

export const addMaterial = (nodeId: string, kind: MaterialKind, path: string, caption: string) => (state: DesktopState) =>
  withNode(state, nodeId, (n) => ({ ...n, materials: n.materials.concat([{ id: newId(), kind, path, caption }]) }));

export const moveMaterial = (nodeId: string, index: number, delta: number) => (state: DesktopState) =>
  withNode(state, nodeId, (n) => ({ ...n, materials: move(n.materials, index, delta) }));

export const removeMaterial = (nodeId: string, id: string) => (state: DesktopState) =>
  withNode(state, nodeId, (n) => ({ ...n, materials: n.materials.filter((m) => m.id !== id) }));

export const captionMaterial = (nodeId: string, id: string, caption: string) => (state: DesktopState) =>
  withNode(state, nodeId, (n) => ({ ...n, materials: n.materials.map((m) => (m.id === id ? { ...m, caption } : m)) }));

/** Kam se ukládá odkaz z paty bloku: pro http(s) URL vznikne link, jinak cesta ve zdroji projektu. */
export function materialKindOf(path: string): Exclude<MaterialKind, "upload"> {
  return /^https?:\/\//i.test(path.trim()) ? "link" : "source";
}

/** Náhled podkladu: nahraný soubor ze složky projektu, obrázek ze zdroje projektu; jinak bez náhledu. */
export function materialPreviewUrl(project: string, workspace: string, nodeId: string, material: NodeMaterial): string | null {
  const q = (params: Record<string, string>) =>
    Object.entries(params).map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join("&");
  if (material.kind === "upload") return `/api/node-materials/file?${q({ project, nodeId, file: material.path })}`;
  if (material.kind === "source" && /\.(png|jpe?g|gif|webp|svg)$/i.test(material.path))
    return `/api/workspace/image?${q({ project, workspace, path: material.path })}`;
  return null;
}

/** Operace nad bloky; App je předá jako stabilní ref, aby se uzly plátna nepřepočítávaly každý render. */
export type BlockApi = {
  mutate: (fn: (current: DesktopState) => DesktopState) => Promise<boolean>;
  close: (nodeId: string, port: BlockPort) => void;
  pickPipeline: (nodeId: string) => void;
  /** Nahraje obrázek (data URL) do složky projektu a vrátí jméno souboru; null = neuloženo. */
  uploadMaterial: (nodeId: string, dataUrl: string) => Promise<string | null>;
  /** Smaže nahraný soubor poté, co byl odebrán ze stavu uzlu. */
  discardUpload: (nodeId: string, file: string) => void;
  previewUrl: (nodeId: string, material: NodeMaterial) => string | null;
};

export type BlockData = {
  nodeId: string;
  nodeName: string;
  port: BlockPort;
  actions: NodeAction[];
  rules: NodeRule[];
  materials: NodeMaterial[];
  readOnly: boolean;
  api: { current: BlockApi };
};

export type OpenBlocks = Record<string, BlockPort[]>;

export function toggleOpen(open: OpenBlocks, nodeId: string, port: BlockPort): OpenBlocks {
  const current = open[nodeId] ?? [];
  return { ...open, [nodeId]: current.includes(port) ? current.filter((p) => p !== port) : current.concat([port]) };
}

export function closeOpen(open: OpenBlocks, nodeId: string, port: BlockPort): OpenBlocks {
  return { ...open, [nodeId]: (open[nodeId] ?? []).filter((p) => p !== port) };
}

/** Blok je vidět, když ho uživatel otevřel portem nebo když už má uložené položky. */
export function buildBlockNodes(
  graph: Graph,
  parent: string | null,
  state: DesktopState,
  open: OpenBlocks,
  readOnly: boolean,
  api: { current: BlockApi },
): { nodes: Node<BlockData>[]; edges: Edge[] } {
  const nodes: Node<BlockData>[] = [];
  const edges: Edge[] = [];
  for (const card of graph.nodes) {
    if (card.parentId !== parent) continue;
    const workflow = nodeWorkflowOf(state, card.id);
    const opened = open[card.id] ?? [];
    const itemsOf = { action: workflow.actions, rule: workflow.rules, material: workflow.materials };
    const shown = (port: BlockPort) => opened.includes(port) || itemsOf[port].length > 0;
    for (const port of BLOCK_PORTS) {
      if (!shown(port)) continue;
      const id = blockNodeId(card.id, port);
      const offset = blockOffsetOf(card, port, shown("rule"));
      nodes.push({
        id,
        type: "block",
        // Blok se táhne sám za sebe (kartou nehne); nové místo se ukládá jako posun proti kartě.
        // Vlastní `draggable` přebíjí `nodesDraggable` plátna, proto se o zámek stará samo.
        position: { x: card.x + offset.dx, y: card.y + offset.dy },
        draggable: !readOnly,
        selectable: false,
        connectable: false,
        data: { nodeId: card.id, nodeName: card.name, port, actions: workflow.actions, rules: workflow.rules, materials: workflow.materials, readOnly, api },
      });
      edges.push({
        id: `block-edge:${port}:${card.id}`,
        source: card.id,
        sourceHandle: port,
        target: id,
        targetHandle: port,
        selectable: false,
        deletable: false,
        style: { stroke: BLOCK_COLOR[port], strokeDasharray: port === "rule" ? "4 3" : undefined },
        // Pravoúhlé vedení jako u vazeb grafu (edgeAppearance v board-model): stejné zaoblení a odstup.
        ...BLOCK_EDGE_PATH,
      });
    }
  }
  return { nodes, edges };
}
