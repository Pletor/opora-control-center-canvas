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
/**
 * Komponenta (docs/architektura-pro-agenty.md §3.3): technologie realizace (1–80 znaků) a 1–8 krátkých stavů
 * píše agent dávkou plánu, člověk je jen vidí. `section` je id sekce nejbližší stránky, kterou komponenta
 * realizuje; píše ji agent i člověk v Detailu prvku. Chybějící klíč = neurčeno, nikdy se nedoplňuje.
 */
export type CardComponentFields = { tech?: string; states?: string[]; section?: string };
/**
 * Kontext pro agenta z knihovny (docs/zive-zobrazeni-a-knihovna.md §5): `fetch` = co si stáhnout do kontextu
 * (relativní cesty v repozitáři, u `docs` i `https://`), `fill` = pole karty, která agent vyplní. Skládá je vložení
 * z knihovny; node-brief je nese v `node` mimo zadání. Prázdný seznam se neukládá.
 */
export type CardAgentFields = { fetch?: { files?: string[]; docs?: string[] }; fill?: string[] };
/** Product structure shares the same graph identities across deployment environments. */
export type NodeSite = ApplicationSite | PageSite;
/** Akce zákazníka, kterou se dostane do kroku: `open` otevře stránku přímo (jen první krok), `click` / `submit` na stránce předchozího kroku. */
export type JourneyAction = "open" | "click" | "submit";
/** Signál přechodu do kroku: akce, sekce stránky předchozího kroku (`site.sections[].id`) a viditelný text prvku (1–60). */
export type JourneyVia = { do: JourneyAction; section?: string; text?: string };
/** Krok trychtýře (`docs/architektura-pro-agenty.md` §3.2): stránka (`page`, u prvního kroku smí být `"nav"`), role (`label`), jaký posun
 * na stránce nastane (`shift`, 1–160), co ho brzdí (`objection`, 1–120), jak sem zákazník přijde (`via`) a odbočka (`after` = id
 * dřívějšího kroku; bez něj navazuje na předchozí). */
export type JourneyStep = { id: string; page: string; label?: string; shift?: string; objection?: string; via?: JourneyVia; after?: string };
/** Cesta zákazníka jako trychtýř stránek a proměna zákazníka: kdo (`actor`, 1–80), kde je na začátku (`pointA`, 1–200) a kým se stane
 * (`pointB`, 1–200). Zadává člověk, 2–30 kroků; vazby mezi kroky po mapě odvodí stroj (§6). Prázdné texty se neukládají. */
export type CustomerJourney = { id: string; name: string; purpose?: string; actor?: string; pointA?: string; pointB?: string; steps: JourneyStep[] };
/** Platforma aplikace: web (výchozí, bez pole) nebo mobilní aplikace Android / iOS. */
export type SitePlatform = "web" | "android" | "ios";
/** Prostředí aplikace: web má `host`, mobilní aplikace místo něj `bundleId` (reverzní doménová notace, unikátní v grafu). */
export type SiteEnvironment = { name: string; host?: string; bundleId?: string };
/** Aplikace (doména): platforma, prostředí, volitelná cesta zdraví (jen web) a cesty zákazníka; prázdné cesty se neukládají. */
export type ApplicationSite = { kind: "application"; platform?: SitePlatform; environments: SiteEnvironment[]; healthPath?: string; journeys?: CustomerJourney[] };
/** Role sekce stránky (`docs/architektura-pro-agenty.md` §3.1). */
export type PageSectionRole = "hero" | "cta" | "form" | "content" | "gallery" | "proof" | "faq" | "footer" | "custom" | "header" | "nav" | "aside" | "article" | "main";
/** Box layoutu sekce na plátně 2: celá čísla na mřížce 12 sloupců uvnitř rodiče (`docs/navrhy/2026-11-10-platno-2.md`). */
export type SectionBox = { x: number; y: number; w: number; h: number };
/** Sekce stránky: navrhuje ji agent v dávce, skládá a upravuje člověk. `intent` smí být prázdný; `moves` (1–120) říká,
 * čím sekce posouvá zákazníka v kroku cesty, prázdné se neukládá. */
export type PageSection = { id: string; role: PageSectionRole; name: string; intent: string; moves?: string;
  /** Poloha boxu v layoutu; bez ní se sekce skládá pod ostatní na celou šířku. */ box?: SectionBox;
  /** Id rodičovské sekce téže stránky (box v boxu, hloubka nejvýš 3). */ parent?: string;
  /** Stav boxu; chybí = `draft` (Rozpracováno). `proposed` zapisuje agent nebo sken, `approved` jen člověk. */ status?: SectionStatus;
  /** Obrázky (fileId z `/api/drawing-file`, nejvýš 6), odkaz na web a poznámka jako inspirace boxu. */ inspiration?: SectionInspiration;
  /** Kdo box naposledy zapsal; doplňuje server, klient ho jen nese dál. */ source?: "human" | "agent" | "scan";
  /** Krátký popis vzhledu boxu (pozadí, typografie, rozmístění; 1–300 znaků, ze skenu webu); prázdné se neukládá. */ look?: string };
export type SectionStatus = "draft" | "proposed" | "approved";
export type SectionInspiration = { files?: string[]; url?: string; note?: string };
/** Stránka: záměr píše člověk (`goal`, `feel`, `navLabel`); vše nepovinné, prázdné pole se neukládá. */
export type PageSite = { kind: "page"; path: string; goal?: string; feel?: string; navLabel?: string; sections?: PageSection[] };
export type ElementKind = "page" | "form" | "overview" | "dialog" | "action" | "service" | "process" | "entity" | "relationship" | "storage" | "condition" | "permission" | "constraint" | "input" | "output" | "event" | "api_contract" | "actor";
export type ElementMetadata = { kind: ElementKind };
export type EdgeRelation = "uses" | "communicates_with" | "requires" | "evidences";
export type CanvasNode = {
  /** Persistent domain role, independent of graphical kind and workflow. */
  element?: ElementMetadata;
  gateNodeId?: string;
  /** Výslovné logické členství v oblasti se stejným rodičem (H01, `docs/kontrakt-identity.md`); ne poloha. */
  memberOf?: string;
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
  card?: NodeCardFields & CardComponentFields & CardAgentFields;
  site?: NodeSite;
};
export type DesignArtifact = { artifactUrl: string; version: string; previewUrl?: string };
/** Port karty, ze kterého vazba vede. Starší vazba bez portu znamená `next`. `flow` spojuje jen dvě oblasti. */
export type EdgePort = "next" | "action" | "rule" | "flow";
export const EDGE_PORTS: EdgePort[] = ["next", "action", "rule", "flow"];
/** Port vazby včetně `block`: vazba nevede z hrany karty, ale z tlačítka bloku v kartě. */
export type GraphEdgePort = EdgePort | "block";
export type RequirementTestCase = { stepId: string; check: string; command: string };
export type InputRequirement = { readiness: "design" | "implemented" | "verified"; revision: number; verification?: { positive: RequirementTestCase; negative: RequirementTestCase } };
export type GraphEdge = {
  requirement?: InputRequirement;
  relation?: EdgeRelation;
  reason?: string;
  id: string;
  source: string;
  target: string;
  port?: GraphEdgePort;
  /** Jen s `port: "block"`: blok zdrojové karty a jeho port. Úchyt v React Flow je `block:<blockId>:<portId>`. */
  sourceBlockId?: string;
  sourcePortId?: string;
  /** Co po vazbě teče (`docs/architektura-pro-agenty.md` §3.4). Jen u vazby `next` nebo bez portu; nikdy se nedoplňuje. */
  carries?: EdgeCarries;
};
/** Druh toku vazby: navigace zákazníka, čtení dat, odeslání/zápis, událost. */
export type EdgeCarries = "navigation" | "data" | "command" | "event";
export const EDGE_CARRIES: EdgeCarries[] = ["navigation", "data", "command", "event"];
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
 * serveru (428) se obnoví a požadavek se jednou zopakuje, i čtení jen pro člověka (otázky srdce).
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
/** Zápis jde jako POST; `PATCH`, `PUT` a `DELETE` jen tam, kde je backend výslovně nabízí (přiřazení worktree k doméně,
 *  technický model Studia `PUT /api/studio/model`, linie velínu `DELETE /api/pletor/linie/...`). */
export type WriteMethod = "POST" | "PATCH" | "PUT" | "DELETE";
export async function api<T>(url: string, body?: object, method: WriteMethod = "POST"): Promise<T> {
  // Research reads are scoped to a human or agent, including a fresh canvas deep link.
  const researchRead = !body && /^\/api\/(?:research|brief-vault\/reviews|library\/reviews|flow\/review|working-reviews|desktop-reviews)(?:[/?]|$)/.test(url);
  if (body || researchRead) await ensureHumanSession();
  let response = await send(url, body, true, method);
  if (response.status === 428 || (researchRead && response.status === 401)) {
    await ensureHumanSession(true);
    response = await send(url, body, Boolean(body), method);
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
  return parsed<T>(url, response, raw);
}
/** Zápis, jehož odpověď čte volající po kouscích (proud NDJSON): doklad člověka, 428 i chyby stejně jako `api`. */
export async function apiStream(url: string, body: object): Promise<ReadableStream<Uint8Array>> {
  await ensureHumanSession();
  let response = await send(url, body);
  if (response.status === 428) {
    await ensureHumanSession(true);
    response = await send(url, body);
  }
  if (response.ok && response.body) return response.body;
  parsed(url, response, await response.text());
  throw new Error(`${url} není dostupné (HTTP ${response.status}).`);
}
function parsed<T>(url: string, response: Response, raw: string): T {
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
