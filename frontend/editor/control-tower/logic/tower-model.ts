// Čistý model Velínu: celá pyramida projektu (oblast → sektor → karta) se stavem procesu a jedinou
// frontou „Čeká na tebe“. Nic neukládá a nic nemění; jen čte graf, stav plátna a přehled práce
// (`/api/desktop-v3/work-overview`) a skládá z nich data pro dílky Velínu.
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
export type TowerSector = {
  id: string; name: string; purpose: string; cards: TowerCard[]; subsectors: TowerSector[]; counts: Counts;
  verified: boolean; gateName: string;
};
export type TowerArea = { id: string; name: string; purpose: string; color: AreaColor; sectors: TowerSector[]; cards: TowerCard[]; counts: Counts };
export type InboxKind = "proposed" | "waiting" | "stuck";
export type InboxItem = {
  kind: InboxKind; nodeId: string; nodeName: string; sectorId: string; sectorName: string; areaId: string; areaName: string; text: string;
};
export type Tower = {
  areas: TowerArea[];
  /** Sektory mimo oblast: na kořeni mimo rámeček i osiřelé (rodič neexistuje nebo cyklus). */
  loose: TowerSector[];
  /** Karty mimo sektor i oblast, včetně osiřelých. */
  looseCards: TowerCard[];
  totals: Counts;
  /** Celá fronta seřazená podle naléhavosti; stránkuje ji `inboxPage`. */
  inbox: InboxItem[];
  workState: WorkState;
};

/** Kolik položek fronty se ukáže najednou (a o kolik přidá „Zobrazit dalších“). */
export const INBOX_LIMIT = 50;
/** Kolik úrovní sektorů se kreslí; součty jdou vždy přes celou hierarchii. */
export const MAX_SECTOR_DEPTH = 4;
export const LOOSE_AREA_ID = "__loose";
const UNNAMED_SECTOR = "Nepojmenovaný sektor";
const UNNAMED_CARD = "Nepojmenovaná karta";
const INBOX_ORDER: Record<InboxKind, number> = { proposed: 0, stuck: 1, waiting: 2 };

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
  closed: "hotovo", proposed: "ke schválení", failed: "selhalo", waitingHuman: "čeká na tebe", running: "pracuje", idle: "čeká",
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

export type StructureSector = { node: CanvasNode; cards: CanvasNode[]; subsectors: StructureSector[] };
export type StructureArea = { node: CanvasNode; sectors: StructureSector[]; cards: CanvasNode[] };
export type TowerStructure = { graph: Graph; areas: StructureArea[]; loose: StructureSector[]; looseCards: CanvasNode[] };

const byPosition = (a: CanvasNode, b: CanvasNode) => a.y - b.y || a.x - b.x;
const nameOr = (name: string, fallback: string) => name.trim() || fallback;

/** Geometrie a hierarchie plátna: oblasti, jejich sektory (celý strom) a karty; osiřelé uzly mimo oblast. */
export function towerStructure(graph: Graph): TowerStructure {
  const nodes = graph.nodes;
  const children = new Map<string | null, CanvasNode[]>();
  for (const node of nodes) {
    const list = children.get(node.parentId);
    if (list) list.push(node); else children.set(node.parentId, [node]);
  }
  for (const list of children.values()) list.sort(byPosition);
  const ofKind = (id: string | null, kind: CanvasNode["kind"]) => (children.get(id) ?? []).filter((n) => n.kind === kind);

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
  function sectorOf(node: CanvasNode): StructureSector {
    seen.add(node.id);
    return {
      node,
      cards: ofKind(node.id, "node"),
      subsectors: ofKind(node.id, "sector").filter((s) => !seen.has(s.id)).map(sectorOf),
    };
  }

  // Členství v oblasti jednou pro každý kořenový sektor a kartu.
  const members = new Map<string | null, { sectors: CanvasNode[]; cards: CanvasNode[] }>();
  const bucketOf = (id: string | null) => {
    let bucket = members.get(id);
    if (!bucket) { bucket = { sectors: [], cards: [] }; members.set(id, bucket); }
    return bucket;
  };
  for (const node of children.get(null) ?? []) {
    if (node.kind !== "sector" && node.kind !== "node") continue;
    const bucket = bucketOf(areaOf(node, nodes)?.id ?? null);
    (node.kind === "sector" ? bucket.sectors : bucket.cards).push(node);
  }

  const areas = ofKind(null, "area").map((area): StructureArea => {
    const bucket = members.get(area.id);
    return { node: area, sectors: (bucket?.sectors ?? []).map(sectorOf), cards: bucket?.cards ?? [] };
  });
  const rootLoose = members.get(null);
  const loose = (rootLoose?.sectors ?? []).map(sectorOf);
  const looseCards = [...(rootLoose?.cards ?? [])];

  // Osiřelé sektory: nejdřív vrcholy (rodič není osiřelý sektor), pak zbytky čistých cyklů.
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const orphanSectors = nodes.filter((n) => n.kind === "sector" && !reachable.has(n.id)).sort(byPosition);
  const isOrphanSector = (id: string | null) => {
    const parent = id ? byId.get(id) : undefined;
    return !!parent && parent.kind === "sector" && !reachable.has(parent.id);
  };
  for (const s of orphanSectors) if (!seen.has(s.id) && !isOrphanSector(s.parentId)) loose.push(sectorOf(s));
  for (const s of orphanSectors) if (!seen.has(s.id)) loose.push(sectorOf(s));
  // Osiřelé karty, které nespadly pod žádný zobrazený sektor.
  for (const card of nodes.filter((n) => n.kind === "node" && !reachable.has(n.id)).sort(byPosition)) {
    if (!(card.parentId && seen.has(card.parentId))) looseCards.push(card);
  }
  return { graph, areas, loose, looseCards };
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

export function towerFrom(structure: TowerStructure, state: DesktopState, work?: WorkOverview, workState: WorkState = work ? "loaded" : "unavailable"): Tower {
  const gates = sectorViews(structure.graph, state, buildBoardIndex(structure.graph, state));
  const inbox: InboxItem[] = [];
  const cardsOf = (list: CanvasNode[], where: Where) => list.map((node) => {
    const card = towerCard(node, state, work, workState);
    inbox.push(...inboxOf(card, where));
    return card;
  });
  function sectorOf(s: StructureSector, areaId: string, areaName: string): TowerSector {
    const name = nameOr(s.node.name, UNNAMED_SECTOR);
    const cards = cardsOf(s.cards, { sectorId: s.node.id, sectorName: name, areaId, areaName });
    const subsectors = s.subsectors.map((sub) => sectorOf(sub, areaId, areaName));
    const gate = gates[s.node.id];
    return {
      id: s.node.id, name, purpose: s.node.purpose, cards, subsectors,
      counts: addCounts(cardCounts(cards), ...subsectors.map((sub) => sub.counts)),
      verified: !!gate?.verified, gateName: gate?.gateName ?? "Nenastavena",
    };
  }
  const areas = structure.areas.map((a): TowerArea => {
    const name = areaLabel(a.node);
    const sectors = a.sectors.map((s) => sectorOf(s, a.node.id, name));
    const cards = cardsOf(a.cards, { sectorId: "", sectorName: "", areaId: a.node.id, areaName: name });
    return {
      id: a.node.id, name, purpose: a.node.purpose, color: areaColorOf(a.node), sectors, cards,
      counts: addCounts(cardCounts(cards), ...sectors.map((s) => s.counts)),
    };
  });
  const loose = structure.loose.map((s) => sectorOf(s, "", ""));
  const looseCards = cardsOf(structure.looseCards, { sectorId: "", sectorName: "", areaId: "", areaName: "" });
  const totals = addCounts(...areas.map((a) => a.counts), ...loose.map((s) => s.counts), cardCounts(looseCards));
  const ordered = inbox.map((item, index) => ({ item, index }))
    .sort((a, b) => INBOX_ORDER[a.item.kind] - INBOX_ORDER[b.item.kind] || a.index - b.index)
    .map(({ item }) => item);
  return { areas, loose, looseCards, totals, inbox: ordered, workState };
}

/** Obě fáze najednou (pro testy a jednorázové použití). */
export function buildTower({ graph, state, work, workState }: { graph: Graph; state: DesktopState; work?: WorkOverview; workState?: WorkState }): Tower {
  return towerFrom(towerStructure(graph), state, work, workState);
}

/** Sektory a karty mimo oblast jako jedno pásmo „Mimo oblast“; `null`, když tam nic není. */
export function looseArea(tower: Tower): TowerArea | null {
  if (!tower.loose.length && !tower.looseCards.length) return null;
  return {
    id: LOOSE_AREA_ID, name: "Mimo oblast", purpose: "Sektory a karty, které neleží v žádné oblasti, včetně osiřelých.",
    color: "slate", sectors: tower.loose, cards: tower.looseCards,
    counts: addCounts(cardCounts(tower.looseCards), ...tower.loose.map((s) => s.counts)),
  };
}

// ---------- Fronta ----------

export type InboxFilter = "all" | InboxKind;

/** Kolik položek fronty je kterého druhu (pro čipy filtru). */
export function inboxKinds(items: InboxItem[]): Record<InboxFilter, number> {
  const counts: Record<InboxFilter, number> = { all: items.length, proposed: 0, stuck: 0, waiting: 0 };
  for (const item of items) counts[item.kind]++;
  return counts;
}

/** Počet různých karet, kterých se fronta týká. */
export function inboxCardCount(items: InboxItem[]): number {
  return new Set(items.map((i) => i.nodeId)).size;
}

/** Viditelná část fronty: filtr druhu a prvních `limit` položek; `more` = kolik jich zbývá. */
export function inboxPage(items: InboxItem[], filter: InboxFilter, limit: number): { items: InboxItem[]; total: number; more: number } {
  const matching = filter === "all" ? items : items.filter((i) => i.kind === filter);
  const shown = matching.slice(0, Math.max(0, limit));
  return { items: shown, total: matching.length, more: matching.length - shown.length };
}

export type InboxGroup = { key: string; sectorId: string; title: string; items: InboxItem[] };

/** Fronta seskupená podle sektoru, mimo sektor podle oblasti (podle id, ne názvu); pořadí skupin = první výskyt. */
export function groupInbox(items: InboxItem[]): InboxGroup[] {
  const groups = new Map<string, InboxGroup>();
  for (const item of items) {
    const key = item.sectorId ? "sector:" + item.sectorId : "area:" + item.areaId;
    let group = groups.get(key);
    if (!group) {
      const title = item.sectorName
        ? (item.areaName ? item.areaName + " › " : "") + item.sectorName
        : item.areaName || "Mimo oblast";
      group = { key, sectorId: item.sectorId, title, items: [] };
      groups.set(key, group);
    }
    group.items.push(item);
  }
  return [...groups.values()];
}

const plural = (n: number, one: string, few: string, many: string) => n + " " + (n === 1 ? one : n >= 2 && n <= 4 ? few : many);

/** Popisek tlačítka rozbalení sektoru: „Obsah: 3 karty · 1 podsektor“ (jen nenulové části). */
export function contentLabel(cards: number, subsectors: number): string {
  const parts = [
    cards ? plural(cards, "karta", "karty", "karet") : "",
    subsectors ? plural(subsectors, "podsektor", "podsektory", "podsektorů") : "",
  ].filter(Boolean);
  return "Obsah: " + (parts.join(" · ") || "prázdný");
}
