// Čistý model oblasti: dashovaný rámeček, který karty seskupuje podle polohy na plátně, ne podle
// odkazu. Členství je geometrické a nikde se neukládá — stejné pravidlo počítá i backend
// (`backend/canvas/areas.py`, `area_of`), tenhle modul jen čte a staví data pro Board a App.
import type { AreaColor, CanvasNode } from "@/shared/types/logic/types";

export const AREA_SIZE_MIN = 120;
export const AREA_SIZE_MAX = 20000;
const DEFAULT_SIZE = { w: 720, h: 480 };
export const UNNAMED_AREA_LABEL = "Nepojmenovaná oblast";

// Nabídka barev v inspektoru, v pořadí, ve kterém se kreslí zleva doprava; hodnota je i název
// CSS proměnné oblasti (`--area-*`), popisek jde do `aria-label`/`title` swatch tlačítka.
export const AREA_COLORS: { value: AreaColor; label: string }[] = [
  { value: "indigo", label: "Indigová" },
  { value: "teal", label: "Tyrkysová" },
  { value: "amber", label: "Jantarová" },
  { value: "rose", label: "Růžová" },
  { value: "violet", label: "Fialová" },
  { value: "slate", label: "Šedá" },
];
const KNOWN_AREA_COLORS = new Set<AreaColor>(AREA_COLORS.map((c) => c.value));

/** Barva oblasti pro kartu i inspektor; chybějící nebo neznámá (starší/cizí data) hodnota je vždy indigová. */
export function areaColorOf(node: Pick<CanvasNode, "color">): AreaColor {
  return node.color && KNOWN_AREA_COLORS.has(node.color) ? node.color : "indigo";
}

/** Nastaví barvu oblasti; nová kopie uzlu, jak to čeká `onSave` v inspektoru. */
export function setAreaColor(node: CanvasNode, color: AreaColor): CanvasNode {
  return { ...node, color };
}

/** Rozpozná oblast mezi uzly grafu; použij všude, kde seznam uzlů nesmí oblast nabídnout jako cíl. */
export function isArea(node: Pick<CanvasNode, "kind">): boolean {
  return node.kind === "area";
}

/** Nová oblast na daném místě vrstvy: bez jména (= nepojmenovaná), bez podstaty, výchozí velikost 720×480. */
export function newArea(parentId: string | null, x: number, y: number): CanvasNode {
  return {
    id: crypto.randomUUID(),
    parentId,
    kind: "area",
    name: "",
    purpose: "",
    x,
    y,
    size: { ...DEFAULT_SIZE },
  };
}

/** Uzel, v jehož vrstvě oblast leží: `null` na kořenové vrstvě (oblast = téma, rozpadá se na sektory),
 *  `kind: "sector"` = oblast je **fáze** sektoru (rozpadá se na karty), `kind: "node"` = vnitřní plátno
 *  karty (rozklad se nenabízí). Rodič, který v grafu chybí, se hlásí jako `kind: "missing"`.
 *  Stejné pravidlo čte `AreaDecompose` (`docs/pyramida.md` §1 bod 3). */
export function areaHost(area: Pick<CanvasNode, "parentId">, nodes: { id: string; kind: string; name: string }[]): AreaHost | null {
  if (!area.parentId) return null;
  const host = nodes.find((n) => n.id === area.parentId);
  if (!host) return { id: area.parentId, name: "", kind: "missing" };
  return { id: host.id, name: host.name, kind: host.kind === "sector" ? "sector" : "node" };
}

/** Rodič vrstvy oblasti pro rozklad: sektor (fáze), karta, nebo chybějící uzel. */
export type AreaHost = { id: string; name: string; kind: "sector" | "node" | "missing" };

/** Popisek oblasti pro štítek na plátně i inspektor: jméno, nebo „Nepojmenovaná oblast“, když chybí. */
export function areaLabel(area: Pick<CanvasNode, "name">): string {
  return area.name.trim() || UNNAMED_AREA_LABEL;
}

// Odsazení středu karty od jejího levého horního rohu, podle druhu uzlu — stejné hodnoty jako
// backendový `_CENTRE_OFFSET`, aby členství vypočtené na plátně souhlasilo s tím v node-brief.
const CENTRE_OFFSET: Record<string, { dx: number; dy: number }> = {
  node: { dx: 180, dy: 120 },
  sector: { dx: 180, dy: 120 },
  comment: { dx: 120, dy: 80 },
};

// Půdorys karty pro hledání volného místa (dvojnásobek CENTRE_OFFSET výš — stejný střed, celý obdélník).
const NODE_FOOTPRINT = { w: 360, h: 240 }; // node / sector
const COMMENT_FOOTPRINT = { w: 240, h: 160 };

function centreOf(node: Pick<CanvasNode, "kind" | "x" | "y">): { cx: number; cy: number } {
  const offset = CENTRE_OFFSET[node.kind] ?? CENTRE_OFFSET.node;
  return { cx: node.x + offset.dx, cy: node.y + offset.dy };
}

/** Bod členství karty (střed podle `CENTRE_OFFSET`): ten rozhoduje v `areaOf`, kam karta patří. */
export function membershipPoint(node: Pick<CanvasNode, "kind" | "x" | "y">): { x: number; y: number } {
  const { cx, cy } = centreOf(node);
  return { x: cx, y: cy };
}

type Rect = { x: number; y: number; w: number; h: number };

/** Mezera, kterou musí nová oblast dodržet od všeho ostatního na vrstvě. */
const AREA_SEARCH_MARGIN = 40;
const AREA_SEARCH_STEP = 40;
const AREA_SEARCH_MAX_COLS = 60;
const AREA_SEARCH_MAX_ROWS = 200;

function inflate(rect: Rect, margin: number): Rect {
  return { x: rect.x - margin, y: rect.y - margin, w: rect.w + margin * 2, h: rect.h + margin * 2 };
}

function rectsIntersect(a: Rect, b: Rect): boolean {
  return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
}

/** Obdélník, který `node` na plátně zabírá: u oblasti její vlastní velikost, u karty/komentáře pevný půdorys. */
function footprintRect(node: CanvasNode): Rect | null {
  if (isArea(node)) {
    if (!node.size) return null;
    return { x: node.x, y: node.y, w: node.size.w, h: node.size.h };
  }
  const footprint = node.kind === "comment" ? COMMENT_FOOTPRINT : NODE_FOOTPRINT;
  return { x: node.x, y: node.y, w: footprint.w, h: footprint.h };
}

/**
 * Je `rect` volný v dané vrstvě (`parentId`)? Porovná ho — s 40px rezervou kolem — proti obdélníku
 * každé oblasti i karty/komentáře na téže vrstvě. Čistá funkce, žádné React ani DOM.
 */
export function isFreeSpot(rect: Rect, nodes: CanvasNode[], parentId: string | null): boolean {
  return !nodes.some((other) => {
    if (other.parentId !== parentId) return false;
    const otherRect = footprintRect(other);
    if (!otherRect) return false;
    return rectsIntersect(rect, inflate(otherRect, AREA_SEARCH_MARGIN));
  });
}

/**
 * Místo pro novou oblast v dané vrstvě: mřížka po 40px od (80, 80), řádek po řádku (nejdřív x, pak
 * y), první volné místo pro obdélník výchozí velikosti (720×480), které nepřekrývá žádnou oblast ani
 * kartu/komentář vrstvy (s 40px rezervou). Prázdná vrstva vrátí rovnou (80, 80). Když se nic volného
 * v prohledané mřížce nenajde, spadne na místo pod nejnižší obsazenou hranou (+ rezerva) na x = 80.
 */
export function nextAreaSpot(nodes: CanvasNode[], parentId: string | null): { x: number; y: number } {
  for (let row = 0; row < AREA_SEARCH_MAX_ROWS; row++) {
    const y = 80 + row * AREA_SEARCH_STEP;
    for (let col = 0; col < AREA_SEARCH_MAX_COLS; col++) {
      const x = 80 + col * AREA_SEARCH_STEP;
      const rect = { x, y, w: DEFAULT_SIZE.w, h: DEFAULT_SIZE.h };
      if (isFreeSpot(rect, nodes, parentId)) return { x, y };
    }
  }
  // Nic volného v prohledané mřížce: pod nejnižší obsazenou hranu vrstvy, zarovnané doleva.
  const bottoms = nodes
    .filter((n) => n.parentId === parentId)
    .map((n) => footprintRect(n))
    .filter((r): r is Rect => r !== null)
    .map((r) => r.y + r.h);
  const maxBottom = bottoms.length ? Math.max(...bottoms) : 80 - AREA_SEARCH_MARGIN;
  return { x: 80, y: maxBottom + AREA_SEARCH_MARGIN };
}

/**
 * Oblast, do které `node` geometricky patří: stejná vrstva (`parentId`), obdélník oblasti
 * `[x, x+w] × [y, y+h]` obsahuje střed karty; když jich vyhovuje víc, vyhrává nejmenší podle
 * plochy. Oblast sama do jiné oblasti nikdy nepatří — stejné pravidlo jako v `graph.py` (nikdy
 * rodič) a v backendovém `area_of`.
 */
export function areaOf(node: CanvasNode, nodes: CanvasNode[]): CanvasNode | null {
  if (isArea(node)) return null;
  const { cx, cy } = centreOf(node);
  const candidates = nodes.filter((other) => {
    if (!isArea(other) || other.id === node.id) return false;
    if (other.parentId !== node.parentId) return false;
    if (!other.size) return false;
    const x1 = other.x + other.size.w;
    const y1 = other.y + other.size.h;
    return other.x <= cx && cx <= x1 && other.y <= cy && cy <= y1;
  });
  if (!candidates.length) return null;
  return [...candidates].sort((a, b) => a.size!.w * a.size!.h - b.size!.w * b.size!.h)[0];
}

/** Všechny uzly (i komentáře), které do dané oblasti geometricky patří — pro inspektor a přesun. */
export function membersOf(area: CanvasNode, nodes: CanvasNode[]): CanvasNode[] {
  return nodes.filter((n) => n.id !== area.id && areaOf(n, nodes)?.id === area.id);
}

/**
 * Posune oblast a všechny její aktuální členy o stejný vektor (dx, dy), aby tažení rámečku
 * vzalo karty uvnitř s sebou. Ostatní uzly zůstávají beze změny.
 */
export function moveWithMembers(nodes: CanvasNode[], areaId: string, dx: number, dy: number): CanvasNode[] {
  const area = nodes.find((n) => n.id === areaId);
  if (!area) return nodes;
  const memberIds = new Set(membersOf(area, nodes).map((n) => n.id));
  return nodes.map((n) => (n.id === areaId || memberIds.has(n.id) ? { ...n, x: n.x + dx, y: n.y + dy } : n));
}

/** Nová velikost oblasti, ohraničená na 120..20000 v obou rozměrech (stejný rozsah jako backend). */
export function resizeArea(node: CanvasNode, w: number, h: number): CanvasNode {
  const clamp = (value: number) => Math.min(AREA_SIZE_MAX, Math.max(AREA_SIZE_MIN, Math.round(value)));
  return { ...node, size: { w: clamp(w), h: clamp(h) } };
}

/** Text prázdné oblasti: co má člověk udělat jako první krok pyramidy (záměr → sektory od agenta). */
export const EMPTY_AREA_ROLLUP = "Prázdná oblast: napište záměr a nechte agenta navrhnout sektory";

/** České skloňování počtu: 1 → první tvar, 2–4 → druhý, jinak (0, 5+) třetí. */
export function czechCount(count: number, one: string, few: string, many: string): string {
  return `${count} ${count === 1 ? one : count >= 2 && count <= 4 ? few : many}`;
}

/**
 * Tichý souhrn pod záměrem na rámečku oblasti: „3 sektory · 14 karet · 5 hotovo“. Ukáže jen
 * nenulové části; oblast bez sektorů i karet dostane výzvu k napsání záměru.
 */
export function areaRollup({ sectors, cards, closed }: { sectors: number; cards: number; closed: number }): string {
  const parts: string[] = [];
  if (sectors > 0) parts.push(czechCount(sectors, "sektor", "sektory", "sektorů"));
  if (cards > 0) parts.push(czechCount(cards, "karta", "karty", "karet"));
  if (closed > 0) parts.push(`${closed} hotovo`);
  if (!sectors && !cards) return EMPTY_AREA_ROLLUP;
  return parts.join(" · ");
}
