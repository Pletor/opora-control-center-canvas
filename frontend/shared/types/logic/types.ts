import { ACCESS_REQUIRED_EVENT } from "@/app/access-gate/logic/access-gate";
import { createEtagCache, notModifiedValue } from "@/shared/types/logic/etag-cache";
export type RemovalPreview = { project: string; workspace: string; kind: "node" | "edge" | "selection" | "project"; target: string; label: string; nodeIds: string[]; nodeCount: number; edgeCount: number; workspaceCount?: number; confirmedNodeIds?: string[]; digest: string };
export type SpecFields = { goal: string; non_goals: string; acceptance: string };
export type NodeSpec = { fields: SpecFields; revision: number; saved_at: string | null; readOnly: boolean; available: boolean; source: string };
/** Vazba na skutečný nebo teprve navržený zdroj; chybí u starších (legacy) uzlů. */
export type SourceRef = { origin: "existing" | "planned"; path: string; kind: "directory" | "file" };
/** Posun bočního bloku proti kartě: blok stojí na `card.x + dx`, `card.y + dy`, takže karta ho při tažení bere s sebou. */
export type BlockOffset = { dx: number; dy: number };
/** Odtažené boční bloky karty podle portu; chybějící port stojí na výchozím místě u karty (viz block-model). */
export type BlockOffsets = Partial<Record<"action" | "rule" | "material" | "pipeline", BlockOffset>>;
/** Barva rámečku oblasti, aby šly skupiny na plátně rozeznat od sebe; chybí = dnešní vzhled (indigo). */
export type AreaColor = "indigo" | "teal" | "amber" | "rose" | "violet" | "slate";
/** Typ workflow karty; neukládá se, čte se jen z předpony názvu `[task] ` atd. (docs/kontext-karet-a-index.md §1). */
export type CardType = "research" | "prototype" | "grilling" | "task" | "gate";
/** Vrstva karty podle otázky frontend / backend / database / library z docs/pravidla-struktury.md. */
export type CardLayer = "frontend" | "backend" | "database" | "library";
/** Ruční stav karty; `done` se nikdy neukládá, odvozuje se z uzavření karty. */
export type CardStatus = "draft" | "ready";
export type CardModel = "fable" | "opus" | "sonnet" | "haiku";
export type CardEffort = "low" | "medium" | "high" | "xhigh" | "max";
/** Nepovinná karta uzlu (jen `kind: "node"`); každý klíč je nepovinný a prázdná karta se neukládá. */
export type NodeCardFields = { layer?: CardLayer; status?: CardStatus; due?: string; model?: CardModel; effort?: CardEffort };
/** Product structure shares the same graph identities across deployment environments. */
export type NodeSite = { kind: "application"; environments: { name: string; host: string }[] } | { kind: "page"; path: string };
export type CanvasNode = {
  gateNodeId?: string;
  design?: DesignArtifact;
  checks?: { id: string; command: string }[];
  factRefs?: string[];
  scenario?: { command: string };
  realization?: { commit: string; prUrl: string; verifiedAt: string };
  goal_mode?: "manual" | "until_checks_pass";
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
  /** Jen s `kind: "node"`: typ, ruční stav, termín, model a effort karty; chybí u starších uzlů. */
  card?: NodeCardFields;
  site?: NodeSite;
};
export type DesignArtifact = { artifactUrl: string; version: string; previewUrl?: string };
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
  /** Architektura (domény a stránky) je nadřazená worktree a jde upravit i tam, kde je obsah jen pro čtení (docs/domeny-a-worktree.md §4). */
  architectureEditable?: boolean;
  architectureRevision?: number;
  /** Uzly obsahu tohoto prostoru, které se liší od architektury projektu nebo z ní byly odstraněny. */
  conflicts?: { id: string; name: string; reason: string }[];
};
export type Project = { id: string; name: string; url: string | null; branch: string | null; sourceKind?: string; sourcePath?: string | null };
/** Cílová platforma projektu (`backend/project_setup/project_hub.py`, PLATFORMS). */
export type Platform = "web" | "app" | "component";
/** Architektura z profilu projektu (docs/suplik-a-profil.md); "" v nastavení = nenastaveno. */
export type Architecture = "monolith" | "modular" | "microservices" | "serverless";
/** Kolik zákazníků aplikace obsluhuje; "" v nastavení = nenastaveno. */
export type Tenancy = "single" | "multi";
/** Nastavení projektu tak, jak ho vrací a přijímá `/api/project-settings`. Zápis nese vždy všechny klíče. */
export type ProjectSettings = { goal: string; platform: Platform; architecture: Architecture | ""; tenancy: Tenancy | "" };
export type SettingsSnapshot = { project: Project; revision: number; settings: ProjectSettings };
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
let humanSession: Promise<void> | null = null;
/**
 * Doklad člověka (upgrade-opora #29): server bere zápis za lidský jen s HttpOnly cookie `opora_ui`,
 * kterou vydá výhradně fetchi z prohlížeče. Vyzvedne se jednou před prvním zápisem; po restartu
 * serveru (428) se obnoví a zápis se jednou zopakuje.
 */
function ensureHumanSession(refresh = false): Promise<void> {
  if (refresh || !humanSession)
    humanSession = fetch("/api/access/ui-session").then(
      (response) => {
        if (!response.ok) humanSession = null;
      },
      () => {
        humanSession = null;
      },
    );
  return humanSession;
}
/** Poslední ETag a tělo čtení podle URL (karta P3): GET posílá If-None-Match, 304 se vezme z paměti. */
const etags = createEtagCache();
function send(url: string, body?: object, conditional = true, method: WriteMethod = "POST"): Promise<Response> {
  return fetch(
    url,
    body
      ? {
          method,
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : { headers: conditional ? etags.headers(url) : {}, cache: "no-store" },
  );
}
/** Zápis jde jako POST; `PATCH` jen tam, kde ho backend výslovně nabízí (přiřazení worktree k doméně). */
export type WriteMethod = "POST" | "PATCH";
export async function api<T>(url: string, body?: object, method: WriteMethod = "POST"): Promise<T> {
  if (body) await ensureHumanSession();
  let response = await send(url, body, true, method);
  if (response.status === 428 && body) {
    await ensureHumanSession(true);
    response = await send(url, body, true, method);
  }
  // 304 = obsah se od posledního čtení nezměnil; bez uloženého těla se dotaz zopakuje bez podmínky.
  if (!body && response.status === 304) {
    const cached = etags.cached(url);
    if (cached !== null) return notModifiedValue(cached) as T;
    response = await send(url, undefined, false);
  }
  // Chybějící endpoint (statický 404) nesmí vypadat jako JSON chyba parseru: říká se HTTP stav.
  const raw = await response.text();
  if (!body) etags.remember(url, response.ok ? response.headers?.get?.("ETag") ?? null : null, raw);
  let value: { error?: string } & Record<string, unknown>;
  try {
    value = JSON.parse(raw);
  } catch {
    throw new Error(`${url.split("?")[0]} není dostupné (HTTP ${response.status}).`);
  }
  // 401 přichází jen zvenčí přes tunel: token chybí nebo vypršel. Brána se musí vrátit.
  if (response.status === 401 && typeof window !== "undefined")
    window.dispatchEvent(new Event(ACCESS_REQUIRED_EVENT));
  if (!response.ok) throw new ApiError(value.error ?? `Požadavek se nezdařil (HTTP ${response.status}).`, response.status, value);
  return value as T;
}
/** Odmítnutý požadavek: text chyby jako dřív a k tomu HTTP stav a celé tělo odpovědi (strukturované podrobnosti,
 *  např. `fragments` u odmítnutého plánu Schránky). */
export class ApiError extends Error {
  readonly status: number;
  readonly body: Record<string, unknown>;
  constructor(message: string, status: number, body: Record<string, unknown>) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}
