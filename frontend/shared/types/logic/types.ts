import { ACCESS_REQUIRED_EVENT } from "@/app/access-gate/logic/access-gate";
export type RemovalPreview = { project: string; workspace: string; kind: "node" | "edge" | "project"; target: string; label: string; nodeIds: string[]; nodeCount: number; edgeCount: number; workspaceCount?: number; digest: string };
export type SpecFields = { goal: string; non_goals: string; acceptance: string };
export type NodeSpec = { fields: SpecFields; revision: number; saved_at: string | null; readOnly: boolean; available: boolean; source: string };
/** Vazba na skutečný nebo teprve navržený zdroj; chybí u starších (legacy) uzlů. */
export type SourceRef = { origin: "existing" | "planned"; path: string; kind: "directory" | "file" };
/** Posun bočního bloku proti kartě: blok stojí na `card.x + dx`, `card.y + dy`, takže karta ho při tažení bere s sebou. */
export type BlockOffset = { dx: number; dy: number };
/** Odtažené boční bloky karty podle portu; chybějící port stojí na výchozím místě u karty (viz block-model). */
export type BlockOffsets = Partial<Record<"action" | "rule" | "material", BlockOffset>>;
/** Barva rámečku oblasti, aby šly skupiny na plátně rozeznat od sebe; chybí = dnešní vzhled (indigo). */
export type AreaColor = "indigo" | "teal" | "amber" | "rose" | "violet" | "slate";
export type CanvasNode = {
  id: string;
  parentId: string | null;
  kind: "sector" | "node" | "comment" | "area";
  name: string;
  purpose: string;
  x: number;
  y: number;
  sourceRef?: SourceRef | null;
  /** Jen s `kind: "area"`: rozměr dashovaného rámečku (120..20000 v obou osách). */
  size?: { w: number; h: number };
  /** Kam si uživatel odtáhl boční bloky karty; chybí, dokud s nimi nikdo nehnul. */
  blockOffsets?: BlockOffsets;
  /** Jen s `kind: "area"`: barva rámečku; chybí = indigová (viz `areaColorOf`). */
  color?: AreaColor;
};
/** Port karty, ze kterého vazba vede. Starší vazba bez portu znamená `next`. `flow` spojuje jen dvě oblasti. */
export type EdgePort = "next" | "action" | "rule" | "flow";
export const EDGE_PORTS: EdgePort[] = ["next", "action", "rule", "flow"];
/** Port vazby včetně `block`: vazba nevede z hrany karty, ale z tlačítka bloku v kartě. */
export type GraphEdgePort = EdgePort | "block";
export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  port?: GraphEdgePort;
  /** Jen s `port: "block"`: blok zdrojové karty a jeho port. Úchyt v React Flow je `block:<blockId>:<portId>`. */
  sourceBlockId?: string;
  sourcePortId?: string;
};
/** Vazba z tlačítka bloku: musí mít `port: "block"` i obě identity, jinak ji nelze zakreslit. */
export const isBlockEdge = (edge: GraphEdge): edge is GraphEdge & { sourceBlockId: string; sourcePortId: string } =>
  edge.port === "block" && !!edge.sourceBlockId && !!edge.sourcePortId;
/** Úchyt portu bloku v React Flow; stejný tvar čte i `parseBlockHandle` v board-model. */
export const blockHandleId = (blockId: string, portId: string): string => `block:${blockId}:${portId}`;
export type Graph = {
  nodes: CanvasNode[];
  edges: GraphEdge[];
};
export type Workspace = {
  id: string;
  directory: string;
  branch: string;
  node_id: string;
  actor: string;
  base_sha: string;
};
export type View = {
  graph: Graph;
  digest: string;
  readOnly: boolean;
  source: string;
  sha: string | null;
  branch: string | null;
  dirty: boolean;
  graphStatus: string;
  workspaces: Workspace[];
  observedAt: string;
};
export type Project = { id: string; name: string; url: string | null; branch: string | null; sourceKind?: string; sourcePath?: string | null };
export type Job = {
  id: string;
  kind: string;
  status: string;
  message: string;
  project_id: string;
  updated_at: string;
};
/**
 * Paměť agenta podle role v bootstrapu klienta: jen poloha přepínače aplikace. Zapnutá paměť tu má
 * `status: "unknown"`, protože bootstrap záměrně nevolá síť — skutečnou dostupnost říká teprve
 * `GET /api/memory/status` (docs/pamet-agentu.md).
 */
export type MemoryBootstrap = { enabled: boolean; status: string };
/** První odpověď klienta (`GET /api/bootstrap`): projekty, úlohy, rozpracovaný projekt a paměť rolí. */
export type Bootstrap = { projects: Project[]; jobs: Job[]; draft?: Project; memory?: MemoryBootstrap };
export async function api<T>(url: string, body?: object): Promise<T> {
  const response = await fetch(
    url,
    body
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : undefined,
  );
  // Chybějící endpoint (statický 404) nesmí vypadat jako JSON chyba parseru: říká se HTTP stav.
  const raw = await response.text();
  let value: { error?: string } & Record<string, unknown>;
  try {
    value = JSON.parse(raw);
  } catch {
    throw new Error(`${url.split("?")[0]} není dostupné (HTTP ${response.status}).`);
  }
  // 401 přichází jen zvenčí přes tunel: token chybí nebo vypršel. Brána se musí vrátit.
  if (response.status === 401 && typeof window !== "undefined")
    window.dispatchEvent(new Event(ACCESS_REQUIRED_EVENT));
  if (!response.ok) throw new Error(value.error ?? `Požadavek se nezdařil (HTTP ${response.status}).`);
  return value as T;
}
