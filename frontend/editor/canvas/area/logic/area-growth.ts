// Rostoucí oblast (docs/architektura-pro-agenty.md §3.5, §8): když člověk táhne kartu přes hranu její
// domovské oblasti, rámeček se natáhne za ní, místo aby ji při puštění vrátil dovnitř. Roste jen tam, kde
// je volno — o cizí kartu ani o jinou oblast se nikdy neopře; kde by musel, platí dnešní `settleCard`.
// Členství zůstává geometrické: růst vždy pojme i bod členství karty, takže `areaOf` po puštění vrátí
// domovskou oblast. Čisté funkce bez Reactu; Board i mapa architektury je volají při tahu a puštění.
import type { CanvasNode } from "@/shared/types/logic/types";
import { areaOf, AREA_SIZE_MAX, membershipPoint } from "@/editor/canvas/area/logic/area-model";
import { settleCard, SOLID_AREA_PAD, SOLID_GAP, type Body } from "@/editor/canvas/board/logic/solid-bodies";

export type Rect = { x: number; y: number; w: number; h: number };
export type Point = { x: number; y: number };
/** Překážky růstu: obdélníky cizích karet a oblastí (drží se od nich `gap`) a body členství cizích karet. */
export type Obstacles = { rects: Rect[]; points: Point[] };
export type GrowthOptions = { pad?: number; gap?: number; grid?: number };

const GRID = 8;
const snapDown = (value: number) => Math.floor(value / GRID) * GRID;
const snapUp = (value: number) => Math.ceil(value / GRID) * GRID;

function overlaps(a: Rect, b: Rect, gap = 0): boolean {
  return a.x < b.x + b.w + gap && b.x < a.x + a.w + gap && a.y < b.y + b.h + gap && b.y < a.y + a.h + gap;
}

function contains(rect: Rect, point: Point): boolean {
  return rect.x <= point.x && point.x <= rect.x + rect.w && rect.y <= point.y && point.y <= rect.y + rect.h;
}

/**
 * Nový obdélník oblasti, který pojme kartu s okrajem `pad` a její bod členství s rezervou `pad`, nebo
 * `null`: karta oblast nepřekrývá, rámeček by přerostl strop, nebo by se dotkl překážky. Roste jen
 * hranami, které musí (posunutá hrana dosedne na mřížku 8 px), nikdy se nezmenší. Překážka, která byla
 * blíž než `gap` už u výchozího rámečku `start`, vadí jen skutečným překryvem.
 */
export function growArea(area: Rect, card: Rect, point: Point, obstacles: Obstacles, opts: GrowthOptions & { start?: Rect } = {}): Rect | null {
  const pad = opts.pad ?? SOLID_AREA_PAD;
  const gap = opts.gap ?? SOLID_GAP;
  const start = opts.start ?? area;
  if (!overlaps(area, card)) return null;
  const left = Math.min(card.x - pad, point.x - pad);
  const top = Math.min(card.y - pad, point.y - pad);
  const right = Math.max(card.x + card.w + pad, point.x + pad);
  const bottom = Math.max(card.y + card.h + pad, point.y + pad);
  const x = left < area.x ? snapDown(left) : area.x;
  const y = top < area.y ? snapDown(top) : area.y;
  const x1 = right > area.x + area.w ? snapUp(right) : area.x + area.w;
  const y1 = bottom > area.y + area.h ? snapUp(bottom) : area.y + area.h;
  const grown = { x, y, w: x1 - x, h: y1 - y };
  if (grown.w > AREA_SIZE_MAX || grown.h > AREA_SIZE_MAX) return null;
  const blocked = obstacles.rects.some((other) => overlaps(grown, other) || (overlaps(grown, other, gap) && !overlaps(start, other, gap)))
    || obstacles.points.some((p) => contains(grown, p) && !contains(start, p));
  return blocked ? null : grown;
}

/** Jeden tah karty: domovská oblast z místa, kde tah začal, poslední platný rámeček a překážky vrstvy. */
export type GrowthSession = { cardId: string; homeId: string; start: Rect; current: Rect; obstacles: Obstacles };

const rectOf = (area: CanvasNode): Rect => ({ x: area.x, y: area.y, w: area.size!.w, h: area.size!.h });

/**
 * Začátek tahu: domovská oblast je `areaOf(karta)` teď. Překážky jsou ostatní oblasti vrstvy a karty,
 * které do domovské oblasti nepatří (obdélník z `bodies` i jejich bod členství). Karta bez oblasti → `null`.
 */
export function startGrowth(card: CanvasNode, nodes: CanvasNode[], bodies: Body[]): GrowthSession | null {
  const home = areaOf(card, nodes);
  if (!home?.size) return null;
  const layer = nodes.filter((n) => n.parentId === card.parentId && n.id !== card.id && n.id !== home.id);
  const foreign = layer.filter((n) => n.kind !== "area" && areaOf(n, nodes)?.id !== home.id);
  const foreignIds = new Set(foreign.map((n) => n.id));
  const rects: Rect[] = [
    ...layer.filter((n) => n.kind === "area" && !!n.size).map(rectOf),
    ...bodies.filter((b) => foreignIds.has(b.id)),
  ];
  const start = rectOf(home);
  return { cardId: card.id, homeId: home.id, start, current: start, obstacles: { rects, points: foreign.map(membershipPoint) } };
}

/** Oblasti vrstvy s domovskou oblastí nataženou na `rect`. */
export function withGrownArea(nodes: CanvasNode[], homeId: string, rect: Rect): CanvasNode[] {
  return nodes.map((n) => (n.id === homeId ? { ...n, x: rect.x, y: rect.y, size: { w: rect.w, h: rect.h } } : n));
}

/**
 * Krok tahu: karta (`card` už na nové poloze, `body` její obdélník tamtéž) natáhne poslední platný
 * rámeček. Vrací nový rámeček, nebo `null`, když růst neprojde — pak náhled zůstává na `session.current`.
 * Pojistka: po růstu musí `areaOf` karty vracet domovskou oblast, jinak se neroste.
 */
export function stepGrowth(session: GrowthSession, card: CanvasNode, body: Rect, nodes: CanvasNode[], opts: GrowthOptions = {}): Rect | null {
  const grown = growArea(session.current, body, membershipPoint(card), session.obstacles, { ...opts, start: session.start });
  if (!grown) return null;
  return areaOf(card, withGrownArea(nodes, session.homeId, grown))?.id === session.homeId ? grown : null;
}

/** Výsledek puštění karty: kam dosedne a případně nový rámeček domovské oblasti (uloží se jednou změnou). */
export type CardDrop = { x: number; y: number; area?: Rect & { id: string } };

/**
 * Puštění karty. Projde-li růst, karta dosedne do natažené oblasti (`settleCard` proti ostatním kartám)
 * a vrátí se nový rámeček. Neprojde-li, nebo karta oblast už nepřekrývá, platí dnešní `settleCard`
 * proti původním oblastem. `card` je uzel na místě puštění, `body` jeho obdélník tamtéž, `others`
 * obdélníky ostatních karet vrstvy a `areas` oblasti vrstvy (uložené rozměry).
 */
export function dropCard(session: GrowthSession | null, card: CanvasNode, body: Body, others: Body[], areas: CanvasNode[]): CardDrop {
  const grown = session ? stepGrowth(session, card, body, areas.concat(card)) : null;
  if (session && grown && !sameRect(grown, session.start)) {
    const grownAreas = withGrownArea(areas, session.homeId, grown);
    const settled = settleCard(card, body, others, grownAreas);
    if (areaOf({ ...card, ...settled }, grownAreas)?.id === session.homeId) return { ...settled, area: { id: session.homeId, ...grown } };
  }
  return settleCard(card, body, others, areas);
}

function sameRect(a: Rect, b: Rect): boolean {
  return a.x === b.x && a.y === b.y && a.w === b.w && a.h === b.h;
}
