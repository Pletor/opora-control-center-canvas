// Čistý model Velínu: celá pyramida projektu (oblast → sektor → karta) se stavem procesu a jedinou
// frontou „Čeká na tebe“. Nic neukládá a nic nemění; jen čte graf, stav plátna a přehled práce
// (`/api/desktop-v3/work-overview`) a skládá z nich data pro dílky Velínu.
// Hierarchie je obecná: vnitřní vrstvu může mít sektor i karta (dvojklik = do hloubky). Karta s dětmi je
// v pyramidě **kontejner** a kreslí se jako dlaždice; na každé vrstvě se sektory a karty seskupí podle
// oblastí té vrstvy (`areaOf`). Nic z grafu se neztratí: každý sektor a karta je v pyramidě přesně jednou.
// Dvě fáze: `towerStructure(graph)` je čistá geometrie a hierarchie (mění se jen s grafem, memoizuje se
// zvlášť), `towerFrom(structure, …)` nad ní doplní stav karet, součty a frontu.
import type { AreaColor, CanvasNode, Graph } from "@/shared/types/logic/types";
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import { areaColorOf, areaLabel, areaOf } from "@/editor/canvas/area/logic/area-model";
import { processView, type CardProcessView } from "@/editor/canvas/node-card/logic/card-process";
import { sectorViews } from "@/editor/canvas/node-card/logic/sector-status";
import { buildBoardIndex } from "@/editor/canvas/board/logic/board-index";
import type { WorkOverview, WorkStatus } from "@/editor/canvas/node-card/logic/use-work-overview";
import { KIND_LABEL } from "@/editor/workflow/card-pipeline/logic/pipeline-model";
import { openIdeas } from "@/editor/node-detail/ideas/logic/ideas-model";

/**
 * Součty karet. `closed`, `proposed`, `failed`, `waitingHuman` a `running` se nepřekrývají: každá karta
 * spadne do prvního sedícího koše v tomhle pořadí, takže z nich jde nakreslit pruh stavů beze zbytku.
 * `unrouted` je navíc (otevřená karta bez schváleného procesu) a do pruhu nepatří.
 */
export type Counts = { cards: number; closed: number; running: number; waitingHuman: number; proposed: number; failed: number; unrouted: number };
/** Jak je na tom přehled práce: ještě se načítá, nepřišel (chyba), nebo je k dispozici. */
export type WorkState = "loading" | "unavailable" | "loaded";
export type TowerCard = {
  id: string; name: string; purpose: string; status: WorkStatus | "idle"; closed: boolean; proposed: boolean;
  /** `false`, když přehled práce chybí a stav otevřené karty proto nejde říct. */
  statusKnown: boolean;
  process?: CardProcessView; waiting: string[]; ideas: number; layer?: string;
};
/** Obsah jedné vrstvy: pásma oblastí, pak sektory, karty a kontejnerové karty mimo oblast. */
export type TowerLayer = { areas: TowerArea[]; sectors: TowerSector[]; cards: TowerCard[]; containers: TowerSector[] };
/**
 * Dlaždice: sektor (`kind: "sector"`), nebo karta s vlastní vrstvou (`kind: "card"`, stav karty v `card`).
 * Obsah je vnitřní vrstva; `counts` jdou celou hloubkou (u kontejneru včetně karty samotné).
 */
export type TowerSector = TowerLayer & {
  id: string; name: string; purpose: string; kind: "sector" | "card"; card?: TowerCard;
  counts: Counts; verified: boolean; gateName: string;
};
/** Pásmo oblasti na libovolné vrstvě (na kořeni i uvnitř dlaždice); vlastní oblasti nemá. */
export type TowerArea = {
  id: string; name: string; purpose: string; color: AreaColor;
  sectors: TowerSector[]; cards: TowerCard[]; containers: TowerSector[]; counts: Counts;
};
/** `intent` = oblast bez záměru, `goal` = sektor bez podstaty (cíl sektoru `spec.goal` klient nemá, proto `purpose`). */
export type InboxKind = "proposed" | "waiting" | "stuck" | "intent" | "goal";
export type InboxItem = {
  kind: InboxKind; nodeId: string; nodeName: string; sectorId: string; sectorName: string; areaId: string; areaName: string; text: string;
};
export type Tower = {
  areas: TowerArea[];
  /** Sektory na kořeni mimo oblast i osiřelé (rodič neexistuje nebo cyklus). */
  loose: TowerSector[];
  /** Karty bez vrstvy na kořeni mimo oblast, včetně osiřelých. */
  looseCards: TowerCard[];
  /** Kontejnerové karty na kořeni mimo oblast, včetně osiřelých. */
  looseContainers: TowerSector[];
  totals: Counts;
  /** Celá fronta seřazená podle naléhavosti; stránkuje ji `inboxPage`. */
  inbox: InboxItem[];
  workState: WorkState;
};

/** Kolik položek fronty se ukáže najednou (a o kolik přidá „Zobrazit dalších“). */
export const INBOX_LIMIT = 50;
/** Kolik úrovní dlaždic se kreslí; součty jdou vždy přes celou hierarchii. */
export const MAX_SECTOR_DEPTH = 4;
export const LOOSE_AREA_ID = "__loose";
const UNNAMED_SECTOR = "Nepojmenovaný sektor";
const UNNAMED_CARD = "Nepojmenovaná karta";
const INBOX_ORDER: Record<InboxKind, number> = { proposed: 0, stuck: 1, waiting: 2, intent: 3, goal: 3 };

export const emptyCounts = (): Counts => ({ cards: 0, closed: 0, running: 0, waitingHuman: 0, proposed: 0, failed: 0, unrouted: 0 });

export function addCounts(...all: Counts[]): Counts {
  const sum = emptyCounts();
  for (const c of all) for (const key of Object.keys(sum) as (keyof Counts)[]) sum[key] += c[key];
  return sum;
}

type Bucket = "closed" | "proposed" | "failed" | "waitingHuman" | "running" | "idle";

/** Koš karty pro součty a pruh stavů; pořadí rozhoduje, když platí víc věcí najednou. */
export function cardBucket(card: TowerCard): Bucket {
  if (card.closed) return "closed";
  if (card.proposed) return "proposed";
  if (card.status === "blocked" || card.process?.waitingOnHuman) return "failed";
  if (card.waiting.length || card.status === "waiting-human") return "waitingHuman";
  if (card.status === "claimed") return "running";
  return "idle";
}

export function cardCounts(cards: TowerCard[]): Counts {
  const counts = emptyCounts();
  for (const card of cards) {
    counts.cards++;
    const bucket = cardBucket(card);
    if (bucket !== "idle") counts[bucket]++;
    if (!card.closed && !card.process?.routed) counts.unrouted++;
  }
  return counts;
}

export type CountSegment = { key: Bucket; label: string; count: number; share: number };
const SEGMENT_LABEL: Record<Bucket, string> = {
  closed: "hotovo", proposed: "ke schválení", failed: "blokováno / selhalo", waitingHuman: "čeká na tebe", running: "pracuje", idle: "čeká",
};

/** Úseky pruhu stavů (jen nenulové), podíl v procentech; prázdné součty vrátí prázdný pruh. */
export function countSegments(counts: Counts): CountSegment[] {
  if (!counts.cards) return [];
  const idle = counts.cards - counts.closed - counts.proposed - counts.failed - counts.waitingHuman - counts.running;
  const values: [Bucket, number][] = [
    ["closed", counts.closed], ["proposed", counts.proposed], ["failed", counts.failed],
    ["waitingHuman", counts.waitingHuman], ["running", counts.running], ["idle", Math.max(0, idle)],
  ];
  return values.filter(([, count]) => count > 0)
    .map(([key, count]) => ({ key, label: SEGMENT_LABEL[key], count, share: Math.round((1000 * count) / counts.cards) / 10 }));
}

// ---------- Fáze 1: struktura (jen z grafu) ----------

export type StructureBlock = { node: CanvasNode; layer: StructureLayer };
export type StructureArea = { node: CanvasNode; sectors: StructureBlock[]; cards: CanvasNode[]; containers: StructureBlock[] };
export type StructureLayer = { areas: StructureArea[]; sectors: StructureBlock[]; cards: CanvasNode[]; containers: StructureBlock[] };
export type TowerStructure = { graph: Graph; root: StructureLayer };

const byPosition = (a: CanvasNode, b: CanvasNode) => a.y - b.y || a.x - b.x;
const nameOr = (name: string, fallback: string) => name.trim() || fallback;
const isMember = (n: CanvasNode) => n.kind === "sector" || n.kind === "node";

/** Geometrie a hierarchie plátna: vrstvy rekurzivně (každý sektor i karta s dětmi), oblasti na každé vrstvě. */
export function towerStructure(graph: Graph): TowerStructure {
  const nodes = graph.nodes;
  const children = new Map<string | null, CanvasNode[]>();
  for (const node of nodes) {
    const list = children.get(node.parentId);
    if (list) list.push(node); else children.set(node.parentId, [node]);
  }
  for (const list of children.values()) list.sort(byPosition);
  const hasLayer = (id: string) => (children.get(id) ?? []).some(isMember);

  // Dosažitelné z kořene přes jakékoli rodiče; zbytek je osiřelý (rodič chybí nebo cyklus).
  const reachable = new Set<string>();
  const queue: (string | null)[] = [null];
  while (queue.length) {
    for (const child of children.get(queue.shift()!) ?? []) {
      if (reachable.has(child.id)) continue;
      reachable.add(child.id);
      queue.push(child.id);
    }
  }

  const seen = new Set<string>();
  const emptyGroup = () => ({ sectors: [] as StructureBlock[], cards: [] as CanvasNode[], containers: [] as StructureBlock[] });
  /** Zařadí uzel do skupiny: sektor, kontejnerová karta (má vlastní vrstvu), nebo prostá karta. */
  function place(node: CanvasNode, group: ReturnType<typeof emptyGroup>) {
    seen.add(node.id);
    if (node.kind === "sector") group.sectors.push(blockOf(node));
    else if (hasLayer(node.id)) group.containers.push(blockOf(node));
    else group.cards.push(node);
  }
  function blockOf(node: CanvasNode): StructureBlock {
    return { node, layer: layerOf(node.id) };
  }
  function layerOf(ownerId: string | null): StructureLayer {
    const own = children.get(ownerId) ?? [];
    const layerAreas = own.filter((n) => n.kind === "area");
    // Členství v oblasti jednou pro každý uzel vrstvy, jen proti oblastem téže vrstvy.
    const byArea = new Map<string, CanvasNode[]>();
    const outside: CanvasNode[] = [];
    for (const node of own) {
      if (!isMember(node) || seen.has(node.id)) continue;
      seen.add(node.id);
      const area = layerAreas.length ? areaOf(node, layerAreas) : null;
      if (area) {
        const list = byArea.get(area.id);
        if (list) list.push(node); else byArea.set(area.id, [node]);
      } else outside.push(node);
    }
    const areas = layerAreas.map((area): StructureArea => {
      const group = emptyGroup();
      for (const node of byArea.get(area.id) ?? []) place(node, group);
      return { node: area, ...group };
    });
    const rest = emptyGroup();
    for (const node of outside) place(node, rest);
    return { areas, ...rest };
  }

  const root = layerOf(null);
  // Osiřelé uzly: nejdřív vrcholy (rodič chybí nebo není osiřelý sektor/karta), pak zbytky čistých cyklů.
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const orphans = nodes.filter((n) => isMember(n) && !reachable.has(n.id)).sort(byPosition);
  const orphanParent = (n: CanvasNode) => {
    const parent = n.parentId ? byId.get(n.parentId) : undefined;
    return !!parent && isMember(parent) && !reachable.has(parent.id);
  };
  for (const n of orphans) if (!seen.has(n.id) && !orphanParent(n)) place(n, root);
  // Ve zbytku cyklu nejdřív dlaždice (sektor, kontejner), ať prostá karta cyklu skončí uvnitř, ne vedle.
  const leaf = (n: CanvasNode) => (n.kind === "node" && !hasLayer(n.id) ? 1 : 0);
  for (const n of [...orphans].sort((a, b) => leaf(a) - leaf(b))) if (!seen.has(n.id)) place(n, root);
  return { graph, root };
}

// ---------- Fáze 2: stav, součty, fronta ----------

function towerCard(node: CanvasNode, state: DesktopState, work: WorkOverview | undefined, workState: WorkState): TowerCard {
  const flow = state.nodes[node.id];
  const row = work?.nodes[node.id];
  const closed = !!flow?.done?.confirmed;
  return {
    id: node.id,
    name: nameOr(node.name, UNNAMED_CARD),
    purpose: node.purpose,
    status: closed ? "done" : row?.status ?? "idle",
    closed,
    proposed: !closed && flow?.done?.by === "agent",
    statusKnown: closed || workState === "loaded",
    process: processView(flow?.stages),
    waiting: (row?.waitingOnHuman ?? []).map((w) => w.ask).filter((ask) => ask.trim()),
    ideas: openIdeas(flow?.ideas),
    ...(node.card?.layer ? { layer: node.card.layer } : {}),
  };
}

type Where = { sectorId: string; sectorName: string; areaId: string; areaName: string };

/** Co karta chce od člověka: návrh uzavření, uvízlý proces, otázky agenta (v tomhle pořadí). */
function inboxOf(card: TowerCard, where: Where): InboxItem[] {
  if (card.closed) return [];
  const base = { nodeId: card.id, nodeName: card.name, ...where };
  const items: InboxItem[] = [];
  if (card.proposed) items.push({ ...base, kind: "proposed", text: "Agent navrhuje kartu uzavřít." });
  if (card.process?.waitingOnHuman) {
    const stuck = card.process.dots.filter((d) => d.stuck)
      .map((d) => (d.title || KIND_LABEL[d.kind]) + (d.note ? " — " + d.note : ""));
    items.push({ ...base, kind: "stuck", text: "Proces uvízl: " + stuck.join("; ") });
  }
  for (const ask of card.waiting) items.push({ ...base, kind: "waiting", text: ask });
  if (!card.waiting.length && card.status === "waiting-human") items.push({ ...base, kind: "waiting", text: "Agent čeká na člověka." });
  return items;
}

const groupCounts = (g: { sectors: TowerSector[]; cards: TowerCard[]; containers: TowerSector[] }) =>
  addCounts(...g.sectors.map((s) => s.counts), cardCounts(g.cards), ...g.containers.map((c) => c.counts));

export function towerFrom(structure: TowerStructure, state: DesktopState, work?: WorkOverview, workState: WorkState = work ? "loaded" : "unavailable"): Tower {
  const gates = sectorViews(structure.graph, state, buildBoardIndex(structure.graph, state));
  const inbox: InboxItem[] = [];
  const cardOf = (node: CanvasNode, where: Where) => {
    const card = towerCard(node, state, work, workState);
    inbox.push(...inboxOf(card, where));
    return card;
  };
  function groupOf(g: { sectors: StructureBlock[]; cards: CanvasNode[]; containers: StructureBlock[] }, where: Where) {
    return {
      sectors: g.sectors.map((b) => blockOf(b, where)),
      cards: g.cards.map((n) => cardOf(n, where)),
      containers: g.containers.map((b) => blockOf(b, where)),
    };
  }
  function areaOfLayer(a: StructureArea, where: Where): TowerArea {
    const name = areaLabel(a.node);
    const inArea = { ...where, areaId: a.node.id, areaName: name };
    // Vrchol pyramidy: oblast bez záměru je úkol pro člověka, ne pro agenta.
    if (!a.node.purpose.trim()) inbox.push({ ...inArea, kind: "intent", nodeId: a.node.id, nodeName: name, text: "Oblast „" + name + "“ nemá záměr." });
    const group = groupOf(a, inArea);
    return { id: a.node.id, name, purpose: a.node.purpose, color: areaColorOf(a.node), ...group, counts: groupCounts(group) };
  }
  function layerOf(layer: StructureLayer, where: Where): TowerLayer {
    return { areas: layer.areas.map((a) => areaOfLayer(a, where)), ...groupOf(layer, where) };
  }
  function blockOf(b: StructureBlock, where: Where): TowerSector {
    const isSector = b.node.kind === "sector";
    const card = isSector ? undefined : cardOf(b.node, where);
    const name = card?.name ?? nameOr(b.node.name, UNNAMED_SECTOR);
    if (isSector && !b.node.purpose.trim()) inbox.push({ ...where, kind: "goal", nodeId: b.node.id, nodeName: name, text: "Sektor „" + name + "“ je bez podstaty." });
    // Uvnitř dlaždice začíná nový kontext: skupina fronty = tahle dlaždice, oblast = oblast její vrstvy.
    const inner = layerOf(b.layer, { sectorId: b.node.id, sectorName: name, areaId: "", areaName: "" });
    const gate = isSector ? gates[b.node.id] : undefined;
    return {
      id: b.node.id, name, purpose: b.node.purpose, kind: isSector ? "sector" : "card", ...(card ? { card } : {}), ...inner,
      counts: addCounts(...inner.areas.map((a) => a.counts), groupCounts(inner), ...(card ? [cardCounts([card])] : [])),
      verified: isSector ? !!gate?.verified : !!card?.closed,
      gateName: isSector ? gate?.gateName ?? "Nenastavena" : "",
    };
  }
  const root = layerOf(structure.root, { sectorId: "", sectorName: "", areaId: "", areaName: "" });
  const totals = addCounts(...root.areas.map((a) => a.counts), groupCounts(root));
  const ordered = inbox.map((item, index) => ({ item, index }))
    .sort((a, b) => INBOX_ORDER[a.item.kind] - INBOX_ORDER[b.item.kind] || a.index - b.index)
    .map(({ item }) => item);
  return { areas: root.areas, loose: root.sectors, looseCards: root.cards, looseContainers: root.containers, totals, inbox: ordered, workState };
}

/** Obě fáze najednou (pro testy a jednorázové použití). */
export function buildTower({ graph, state, work, workState }: { graph: Graph; state: DesktopState; work?: WorkOverview; workState?: WorkState }): Tower {
  return towerFrom(towerStructure(graph), state, work, workState);
}

/** Kořenové sektory a karty mimo oblast jako jedno pásmo; `null`, když tam nic není. Bez oblastí na kořeni je to „Kořen plátna“. */
export function looseArea(tower: Tower): TowerArea | null {
  if (!tower.loose.length && !tower.looseCards.length && !tower.looseContainers.length) return null;
  const group = { sectors: tower.loose, cards: tower.looseCards, containers: tower.looseContainers };
  return {
    id: LOOSE_AREA_ID,
    name: tower.areas.length ? "Mimo oblast" : "Kořen plátna",
    purpose: tower.areas.length ? "Sektory a karty, které neleží v žádné oblasti, včetně osiřelých." : "Sektory a karty na nejvyšší vrstvě plátna.",
    color: "slate", ...group, counts: groupCounts(group),
  };
}

/** Kolik přímých členů má vnitřní vrstva dlaždice (karty včetně kontejnerových, sektory, oblasti). */
export function layerSize(layer: TowerLayer): { cards: number; sectors: number; areas: number } {
  const all = [layer, ...layer.areas];
  return {
    cards: all.reduce((n, g) => n + g.cards.length + g.containers.length, 0),
    sectors: all.reduce((n, g) => n + g.sectors.length, 0),
    areas: layer.areas.length,
  };
}

/** Každé id sektoru a karty v pyramidě (i kontejnerů), v pořadí kreslení — pro kontrolu, že se nic neztratilo. */
export function towerIds(tower: Tower): string[] {
  const ids: string[] = [];
  const group = (g: { sectors: TowerSector[]; cards: TowerCard[]; containers: TowerSector[] }) => {
    g.sectors.forEach(block); g.cards.forEach((c) => ids.push(c.id)); g.containers.forEach(block);
  };
  const block = (b: TowerSector) => { ids.push(b.id); b.areas.forEach(group); group(b); };
  tower.areas.forEach(group);
  group({ sectors: tower.loose, cards: tower.looseCards, containers: tower.looseContainers });
  return ids;
}

// ---------- Fronta ----------

/** Filtr fronty; „intent“ (čip Záměr) bere oblasti bez záměru i sektory bez podstaty. */
export type InboxFilter = "all" | "proposed" | "stuck" | "waiting" | "intent";
const filterOf = (kind: InboxKind): Exclude<InboxFilter, "all"> => (kind === "goal" ? "intent" : kind);

/** Kolik položek fronty je kterého druhu (pro čipy filtru). */
export function inboxKinds(items: InboxItem[]): Record<InboxFilter, number> {
  const counts: Record<InboxFilter, number> = { all: items.length, proposed: 0, stuck: 0, waiting: 0, intent: 0 };
  for (const item of items) counts[filterOf(item.kind)]++;
  return counts;
}

/** Počet různých karet, kterých se fronta týká. */
export function inboxCardCount(items: InboxItem[]): number {
  return new Set(items.map((i) => i.nodeId)).size;
}

/** Viditelná část fronty: filtr druhu a prvních `limit` položek; `more` = kolik jich zbývá. */
export function inboxPage(items: InboxItem[], filter: InboxFilter, limit: number): { items: InboxItem[]; total: number; more: number } {
  const matching = filter === "all" ? items : items.filter((i) => filterOf(i.kind) === filter);
  const shown = matching.slice(0, Math.max(0, limit));
  return { items: shown, total: matching.length, more: matching.length - shown.length };
}

export type InboxGroup = { key: string; sectorId: string; title: string; items: InboxItem[] };

/** Fronta seskupená podle sektoru (či kontejneru), mimo něj podle oblasti — podle id, ne názvu; pořadí skupin = první výskyt. */
export function groupInbox(items: InboxItem[]): InboxGroup[] {
  const groups = new Map<string, InboxGroup>();
  for (const item of items) {
    const key = item.sectorId ? "sector:" + item.sectorId + ":" + item.areaId : "area:" + item.areaId;
    let group = groups.get(key);
    if (!group) {
      const title = item.sectorName
        ? item.sectorName + (item.areaName ? " › " + item.areaName : "")
        : item.areaName || "Mimo oblast";
      group = { key, sectorId: item.sectorId, title, items: [] };
      groups.set(key, group);
    }
    group.items.push(item);
  }
  return [...groups.values()];
}

const plural = (n: number, one: string, few: string, many: string) => n + " " + (n === 1 ? one : n >= 2 && n <= 4 ? few : many);

/** Popisek tlačítka rozbalení: „Obsah: 3 karty · 1 podsektor · 2 oblasti“ (jen nenulové části). */
export function contentLabel(cards: number, subsectors: number, areas = 0): string {
  const parts = [
    cards ? plural(cards, "karta", "karty", "karet") : "",
    subsectors ? plural(subsectors, "podsektor", "podsektory", "podsektorů") : "",
    areas ? plural(areas, "oblast", "oblasti", "oblastí") : "",
  ].filter(Boolean);
  return "Obsah: " + (parts.join(" · ") || "prázdný");
}
