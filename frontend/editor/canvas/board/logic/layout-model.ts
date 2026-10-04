// Magnetismus a srovnání plátna: karta (a její viditelné boční bloky) nesmí skončit přes jinou kartu. Čisté
// funkce bez Reactu a bez React Flow — Board volá resolveOverlap při puštění tahu, App volá arrangeLayer
// z tlačítka „Srovnat“. Otisk (Footprint) je obdélník, kterým uzel na plátně skutečně zabírá místo.
import type { BlockOffsets, CanvasNode, Graph, GraphEdge } from "@/shared/types/logic/types";
import type { DesktopState } from "@/shared/desktop-state/logic/types";
import { nodeWorkflowOf } from "@/shared/desktop-state/logic/types";
import { areaOf, AREA_SIZE_MAX, AREA_SIZE_MIN } from "@/editor/canvas/area/logic/area-model";
import {
  BLOCK_PORTS,
  blockOffsetOf,
  type BlockPort,
  type OpenBlocks,
} from "@/editor/workflow/blocks/logic/block-model";

export type Footprint = { id: string; x: number; y: number; w: number; h: number };

const CARD_W = 360;
const CARD_H_DEFAULT = 240;
const COMMENT_W = 240;
const COMMENT_H_DEFAULT = 140;
const SIDE_BLOCK_W = 260;
const SIDE_BLOCK_H = 200;

/**
 * Otisk uzlu na plátně: karta (nebo lístek komentáře) sloučená s viditelnými bočními bloky Akce / Pravidla /
 * Podklady — přesně tou plochou uzel na plátně skutečně stojí, i když samotná karta je užší. Odtažený blok
 * (`blockOffsets` uzlu) se počítá tam, kam ho uživatel dal, aby otisk neodstrkával karty od prázdného místa.
 * Budoucí oblast (`kind: "area"`) nic nezabírá a do magnetismu nevstupuje vůbec, ani jako překážka pro ostatní.
 */
export function footprintOf(
  node: { id: string; kind: string; x: number; y: number; blockOffsets?: BlockOffsets },
  opts: { measuredHeight?: number; openPorts: BlockPort[]; hasActions: boolean; hasRules: boolean; hasMaterials: boolean },
): Footprint | null {
  if (node.kind === "area") return null;
  if (node.kind === "comment") {
    return { id: node.id, x: node.x, y: node.y, w: COMMENT_W, h: opts.measuredHeight ?? COMMENT_H_DEFAULT };
  }
  let x0 = node.x;
  let y0 = node.y;
  let x1 = node.x + CARD_W;
  let y1 = node.y + (opts.measuredHeight ?? CARD_H_DEFAULT);
  const hasItems: Record<BlockPort, boolean> = { action: opts.hasActions, rule: opts.hasRules, material: opts.hasMaterials };
  const shown = (port: BlockPort) => opts.openPorts.includes(port) || hasItems[port];
  for (const port of BLOCK_PORTS) {
    if (!shown(port)) continue;
    const offset = blockOffsetOf(node, port, shown("rule"));
    const bx0 = node.x + offset.dx;
    const by0 = node.y + offset.dy;
    x0 = Math.min(x0, bx0);
    y0 = Math.min(y0, by0);
    x1 = Math.max(x1, bx0 + SIDE_BLOCK_W);
    y1 = Math.max(y1, by0 + SIDE_BLOCK_H);
  }
  return { id: node.id, x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
}

/**
 * Otisky všech viditelných uzlů jedné vrstvy. `heights` je naměřená výška karty z plátna (nepovinná — u
 * ještě nezměřené karty chybí, stejně jako při volání z App, které DOM neyzná a spoléhá na výchozí rozměr).
 */
export function layerFootprints(
  graph: Graph,
  parent: string | null,
  state: DesktopState,
  openBlocks: OpenBlocks,
  heights: Record<string, number>,
): Footprint[] {
  const footprints: Footprint[] = [];
  for (const n of graph.nodes) {
    if (n.parentId !== parent) continue;
    const workflow = nodeWorkflowOf(state, n.id);
    const footprint = footprintOf(n, {
      measuredHeight: heights[n.id],
      openPorts: openBlocks[n.id] ?? [],
      hasActions: workflow.actions.length > 0,
      hasRules: workflow.rules.length > 0,
      hasMaterials: workflow.materials.length > 0,
    });
    if (footprint) footprints.push(footprint);
  }
  return footprints;
}

/** Kolik by bylo třeba uzly rozestrčit na každé ose, aby mezi nimi zůstala `gap`; ≤0 = na té ose se nepřekrývají. */
function overlapAmount(a: Footprint, b: Footprint, gap: number): { ox: number; oy: number } {
  const ox = a.w / 2 + b.w / 2 + gap - Math.abs(a.x + a.w / 2 - (b.x + b.w / 2));
  const oy = a.h / 2 + b.h / 2 + gap - Math.abs(a.y + a.h / 2 - (b.y + b.h / 2));
  return { ox, oy };
}

const snap = (value: number, grid: number) => Math.round(value / grid) * grid;

/**
 * Vytáhne `moved` ze všech překryvů s `others` (mezera `gap`, přichycení na mřížku `grid`) — v každém kroku
 * posune po ose, na které je průnik menší (nejkratší cesta ven), dokud se nepřekrývá s ničím, nejvýš `20`
 * kroků. Deterministické; beze změny (a beze snapu), když se s ničím nepřekrývá.
 */
export function resolveOverlap(moved: Footprint, others: Footprint[], gap = 24, grid = 8): { x: number; y: number } {
  let x = moved.x;
  let y = moved.y;
  let pushed = false;
  for (let step = 0; step < 20; step++) {
    const current: Footprint = { ...moved, x, y };
    let hit: Footprint | undefined;
    let penetration = { ox: 0, oy: 0 };
    for (const other of others) {
      if (other.id === moved.id) continue;
      const amount = overlapAmount(current, other, gap);
      if (amount.ox > 0 && amount.oy > 0) {
        hit = other;
        penetration = amount;
        break;
      }
    }
    if (!hit) break;
    const dirX = current.x + current.w / 2 >= hit.x + hit.w / 2 ? 1 : -1;
    const dirY = current.y + current.h / 2 >= hit.y + hit.h / 2 ? 1 : -1;
    if (penetration.ox < penetration.oy) x += penetration.ox * dirX;
    else y += penetration.oy * dirY;
    pushed = true;
  }
  return pushed ? { x: snap(x, grid), y: snap(y, grid) } : { x: moved.x, y: moved.y };
}

// ——— Srovnání podle toku („Srovnat“) ————————————————————————————————————————————————————————————————
// Příběh rozvržení: co spolu souvisí, má stát vedle sebe ve směru čtení; co spolu nesouvisí, má stát
// zvlášť; a co uživatel zavřel do oblasti, z ní nesmí vypadnout. Vrstva se proto rozpadne na skupiny
// (obsah každé oblasti zvlášť, zbytek jako volné karty), každá skupina se srovná do sloupců podle
// vazeb a skupiny se poskládají pod sebe. Nic se nepřekrývá a žádná karta nezmizí.

/** Mezery rozvržení: vodorovná mezi sloupci, svislá mezi kartami ve sloupci, mřížka pro zaokrouhlení. */
export type ArrangeOptions = { gapX?: number; gapY?: number; grid?: number };
/** Rámeček oblasti po srovnání: poloha zůstává, rozměr může vyrůst, aby se obsah vešel. */
export type ArrangedArea = { id: string; x: number; y: number; w: number; h: number };
export type Arrangement = { nodes: { id: string; x: number; y: number }[]; areas: ArrangedArea[] };

type Link = { source: string; target: string };
type Placed = { id: string; x: number; y: number; w: number; h: number };
type Rect = { x: number; y: number; w: number; h: number };
type FramedArea = CanvasNode & { size: { w: number; h: number } };

/** Odsazení obsahu uvnitř oblasti: po stranách a dole 32, nahoře 56 — tam sedí štítek se jménem oblasti. */
const AREA_PAD = 32;
const AREA_PAD_TOP = 56;
/** Nejvýš čtyři osamělé karty pod sebou; pak začíná další sloupec, aby mřížka zůstala nízká a čitelná. */
const LONELY_COLUMN = 4;

const clampAreaSize = (value: number) => Math.min(AREA_SIZE_MAX, Math.max(AREA_SIZE_MIN, Math.round(value)));

/** Protínají se obdélníky? `margin` je rezerva, kterou kolem sebe druhý z nich navíc drží. */
function rectsTouch(a: Rect, b: Rect, margin = 0): boolean {
  return a.x < b.x + b.w + margin && b.x - margin < a.x + a.w && a.y < b.y + b.h + margin && b.y - margin < a.y + a.h;
}

/** Obálka umístěných otisků — kolik místa skupina nakonec zabrala. */
function boundsOf(placed: Placed[]): Rect {
  if (!placed.length) return { x: 0, y: 0, w: 0, h: 0 };
  const x = Math.min(...placed.map((p) => p.x));
  const y = Math.min(...placed.map((p) => p.y));
  const right = Math.max(...placed.map((p) => p.x + p.w));
  const bottom = Math.max(...placed.map((p) => p.y + p.h));
  return { x, y, w: right - x, h: bottom - y };
}

/** Stabilní pořadí podle původního místa na plátně (odshora, zleva) a nakonec podle id: dvakrát totéž. */
function byOriginalPlace(a: Footprint, b: Footprint): number {
  return a.y - b.y || a.x - b.x || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
}

/**
 * Vazby, které do rozvržení vrstvy patří: obě strany musí být mezi otisky, smyčka do sebe ani dvojí
 * zápis téže vazby se nepočítají. Port `flow` spojuje dvě oblasti, ne karty, takže do toku uzlů nevstupuje;
 * `next`, `action`, `rule` i `block` znamenají pro rozvržení totéž — „odtud se pokračuje tam“.
 */
function linksAmong(footprints: Footprint[], edges: GraphEdge[]): Link[] {
  const inside = new Set(footprints.map((f) => f.id));
  const seen = new Set<string>();
  const links: Link[] = [];
  for (const edge of edges) {
    if (edge.port === "flow" || edge.source === edge.target) continue;
    if (!inside.has(edge.source) || !inside.has(edge.target)) continue;
    const key = `${edge.source}\u0000${edge.target}`;
    if (seen.has(key)) continue;
    seen.add(key);
    links.push({ source: edge.source, target: edge.target });
  }
  return links;
}

/**
 * Tytéž vazby bez cyklů: průchod do hloubky (nejdřív od uzlů, do kterých nic nevede) označí zpětné hrany —
 * ty, které míří na uzel právě otevřený na zásobníku — a ty se do rozvržení nepočítají. Kruh v procesu tak
 * řazení do sloupců nezacyklí a žádná karta kvůli němu nezmizí; jen ta jedna vazba povede zpátky napříč.
 */
function forwardLinks(ids: string[], links: Link[]): Link[] {
  const out = new Map<string, Link[]>(ids.map((id) => [id, []]));
  for (const link of links) out.get(link.source)!.push(link);
  const hasIncoming = new Set(links.map((link) => link.target));
  const open = new Set<string>();
  const done = new Set<string>();
  const back = new Set<Link>();
  const walk = (id: string) => {
    open.add(id);
    for (const link of out.get(id)!) {
      if (open.has(link.target)) back.add(link);
      else if (!done.has(link.target)) walk(link.target);
    }
    open.delete(id);
    done.add(id);
  };
  for (const id of ids) if (!hasIncoming.has(id) && !done.has(id)) walk(id);
  for (const id of ids) if (!done.has(id)) walk(id);
  return links.filter((link) => !back.has(link));
}

/** Sloupec uzlu = nejdelší cesta od uzlu bez vstupu (0 = nic do něj nevede). Vazby jsou už bez cyklů. */
function ranksOf(ids: string[], links: Link[]): Map<string, number> {
  const out = new Map<string, string[]>(ids.map((id) => [id, []]));
  const waiting = new Map<string, number>(ids.map((id) => [id, 0]));
  for (const link of links) {
    out.get(link.source)!.push(link.target);
    waiting.set(link.target, waiting.get(link.target)! + 1);
  }
  const rank = new Map<string, number>(ids.map((id) => [id, 0]));
  const queue = ids.filter((id) => waiting.get(id) === 0);
  for (let i = 0; i < queue.length; i++) {
    for (const target of out.get(queue[i])!) {
      rank.set(target, Math.max(rank.get(target)!, rank.get(queue[i])! + 1));
      const left = waiting.get(target)! - 1;
      waiting.set(target, left);
      if (left === 0) queue.push(target);
    }
  }
  return rank;
}

/** Souvislé celky skupiny (vazby brané jako neorientované), v pořadí prvního výskytu mezi otisky. */
function componentsOf(footprints: Footprint[], links: Link[]): Footprint[][] {
  const home = new Map<string, string>(footprints.map((f) => [f.id, f.id]));
  const root = (id: string): string => {
    let current = id;
    while (home.get(current) !== current) current = home.get(current)!;
    return current;
  };
  for (const link of links) {
    const a = root(link.source);
    const b = root(link.target);
    if (a !== b) home.set(a, b);
  }
  const groups = new Map<string, Footprint[]>();
  for (const f of footprints) {
    const key = root(f.id);
    const group = groups.get(key);
    if (group) group.push(f);
    else groups.set(key, [f]);
  }
  return [...groups.values()];
}

/**
 * Jeden souvislý celek do sloupců: sloupec je pořadí v toku (kdo je dřív, stojí vlevo), šířka sloupce je
 * nejširší karta v něm a další sloupec začíná o gapX dál. Uvnitř sloupce se karty seřadí podle průměrné
 * řady svých předchůdců (těžiště), aby vazby vedly co nejrovněji; při shodě rozhodne původní místo a id.
 * Levý horní roh celku je (0, 0), posunutí na plátno je věcí volajícího.
 */
function placeFlow(members: Footprint[], links: Link[], gapX: number, gapY: number): Placed[] {
  const ids = members.map((f) => f.id);
  const rank = ranksOf(ids, links);
  const before = new Map<string, string[]>(ids.map((id) => [id, []]));
  for (const link of links) before.get(link.target)!.push(link.source);
  const columns = new Map<number, Footprint[]>();
  for (const f of members) {
    const column = columns.get(rank.get(f.id)!);
    if (column) column.push(f);
    else columns.set(rank.get(f.id)!, [f]);
  }
  const row = new Map<string, number>();
  const centre = (f: Footprint) => {
    const rows = before.get(f.id)!.map((id) => row.get(id)).filter((value): value is number => value !== undefined);
    return rows.length ? rows.reduce((sum, value) => sum + value, 0) / rows.length : 0;
  };
  const placed: Placed[] = [];
  let x = 0;
  for (const level of [...columns.keys()].sort((a, b) => a - b)) {
    const column = [...columns.get(level)!].sort((a, b) => centre(a) - centre(b) || byOriginalPlace(a, b));
    let y = 0;
    column.forEach((f, index) => {
      row.set(f.id, index);
      placed.push({ id: f.id, x, y, w: f.w, h: f.h });
      y += f.h + gapY;
    });
    x += Math.max(...column.map((f) => f.w)) + gapX;
  }
  return placed;
}

/**
 * Osamělé uzly (nevede z nich ani do nich žádná vazba) do úsporné mřížky: sloupce po nejvýš čtyřech
 * kartách, šířka sloupce podle nejširší karty v něm, výška řady podle nejvyšší karty v řadě.
 */
function placeGrid(members: Footprint[], gapX: number, gapY: number): Placed[] {
  const order = [...members].sort(byOriginalPlace);
  const columnOf = (index: number) => Math.floor(index / LONELY_COLUMN);
  const rowOf = (index: number) => index % LONELY_COLUMN;
  const columnWidth: number[] = [];
  const rowHeight: number[] = [];
  order.forEach((f, index) => {
    columnWidth[columnOf(index)] = Math.max(columnWidth[columnOf(index)] ?? 0, f.w);
    rowHeight[rowOf(index)] = Math.max(rowHeight[rowOf(index)] ?? 0, f.h);
  });
  const columnX: number[] = [];
  const rowY: number[] = [];
  let x = 0;
  for (let column = 0; column < columnWidth.length; column++) {
    columnX[column] = x;
    x += columnWidth[column] + gapX;
  }
  let y = 0;
  for (let line = 0; line < rowHeight.length; line++) {
    rowY[line] = y;
    y += rowHeight[line] + gapY;
  }
  return order.map((f, index) => ({ id: f.id, x: columnX[columnOf(index)], y: rowY[rowOf(index)], w: f.w, h: f.h }));
}

/**
 * Celá skupina (obsah jedné oblasti, nebo všechny volné karty) s levým horním rohem v (0, 0): nejdřív
 * souvislé celky pod sebou, širší nahoře (aby se rozvržení četlo jako stránka), mezi nimi dvojitá mezera,
 * a úplně dole mřížka osamělých uzlů — ty nikomu nepřekážejí v toku.
 */
function placeGroup(members: Footprint[], links: Link[], gapX: number, gapY: number): Placed[] {
  if (!members.length) return [];
  const inside = new Set(members.map((f) => f.id));
  const own = links.filter((link) => inside.has(link.source) && inside.has(link.target));
  const forward = forwardLinks(
    members.map((f) => f.id),
    own,
  );
  const parts = componentsOf(members, own);
  const lonely = parts.filter((part) => part.length === 1).map((part) => part[0]);
  const flows = parts
    .filter((part) => part.length > 1)
    .map((part) => {
      const here = new Set(part.map((f) => f.id));
      return placeFlow(part, forward.filter((link) => here.has(link.source) && here.has(link.target)), gapX, gapY);
    })
    .sort((a, b) => boundsOf(b).w - boundsOf(a).w || b.length - a.length || (a[0].id < b[0].id ? -1 : 1));
  const placed: Placed[] = [];
  let top = 0;
  for (const block of [...flows, ...(lonely.length ? [placeGrid(lonely, gapX, gapY)] : [])]) {
    const bounds = boundsOf(block);
    for (const item of block) placed.push({ ...item, x: item.x - bounds.x, y: item.y - bounds.y + top });
    top += bounds.h + gapY * 2;
  }
  return placed;
}

/**
 * Do které oblasti otisk patří. Rozhoduje `areaOf` z modelu oblasti — totéž geometrické pravidlo, které
 * plátno i backend používají pro členství (střed karty leží v rámečku, při shodě vyhrává menší oblast).
 * Otisk se přitom tváří jako karta na svém levém horním rohu: u karty bez odtažených bloků je to přesně
 * ona sama, takže srovnání nikoho z jeho oblasti nevyhodí.
 */
function areaMembership(footprints: Footprint[], areas: FramedArea[]): Map<string, string | null> {
  const parentId = areas[0]?.parentId ?? null;
  const membership = new Map<string, string | null>();
  for (const f of footprints) {
    const card: CanvasNode = { id: f.id, parentId, kind: "node", name: "", purpose: "", x: f.x, y: f.y };
    membership.set(f.id, areaOf(card, areas)?.id ?? null);
  }
  return membership;
}

/**
 * Srovná celou vrstvu (tlačítko „Srovnat“) tak, aby se dala číst: co je spojené vazbou, stojí vedle sebe
 * ve směru toku zleva doprava; co spolu nesouvisí, leží zvlášť; karty uvnitř oblasti zůstanou uvnitř
 * (a oblast se pod nimi podle potřeby zvětší, nikdy nezmenší); volné karty se odstěhují pod oblasti.
 * Výsledek je deterministický — stejný vstup dá vždycky stejné rozvržení — a bez jediného překryvu.
 */
export function arrangeLayer(
  footprints: Footprint[],
  edges: GraphEdge[],
  areas: CanvasNode[],
  opts: ArrangeOptions = {},
): Arrangement {
  const gapX = opts.gapX ?? 96;
  const gapY = opts.gapY ?? 48;
  const grid = opts.grid ?? 8;
  const links = linksAmong(footprints, edges);
  const framed = areas.filter((area): area is FramedArea => area.kind === "area" && !!area.size);
  const home = areaMembership(footprints, framed);
  const placed: Placed[] = [];
  const frames: ArrangedArea[] = [];

  // Oblasti: obsah začíná pod štítkem, rámeček se pod ním roztáhne, ale nikdy neuhne z místa.
  for (const area of framed) {
    const content = placeGroup(
      footprints.filter((f) => home.get(f.id) === area.id),
      links,
      gapX,
      gapY,
    );
    const bounds = boundsOf(content);
    frames.push({
      id: area.id,
      x: area.x,
      y: area.y,
      w: clampAreaSize(Math.max(area.size.w, bounds.w + AREA_PAD * 2)),
      h: clampAreaSize(Math.max(area.size.h, bounds.h + AREA_PAD + AREA_PAD_TOP)),
    });
    for (const item of content) {
      placed.push({ ...item, x: snap(item.x + area.x + AREA_PAD, grid), y: snap(item.y + area.y + AREA_PAD_TOP, grid) });
    }
  }

  // Volné karty: jeden celek pod všemi oblastmi, zarovnaný na jejich levou hranu. Bez oblastí prostě (80, 80).
  const free = placeGroup(
    footprints.filter((f) => !home.get(f.id)),
    links,
    gapX,
    gapY,
  );
  const originX = frames.length ? Math.min(...frames.map((frame) => frame.x)) : 80;
  let originY = frames.length ? Math.max(...frames.map((frame) => frame.y + frame.h)) + gapY * 2 : 80;
  for (let step = 0; step < 200; step++) {
    const at = originY;
    if (!free.some((item) => frames.some((frame) => rectsTouch({ ...item, x: item.x + originX, y: item.y + at }, frame, gapY)))) break;
    originY += gapY;
  }
  for (const item of free) placed.push({ ...item, x: snap(item.x + originX, grid), y: snap(item.y + originY, grid) });

  // Pojistka: při běžném zadání se po srovnání nic nepřekrývá a resolveOverlap nic nezmění. Zasáhne jen
  // u zvrhlého plátna (dvě oblasti přes sebe), aby vrstva nikdy neskončila kartou na kartě.
  const settled: Footprint[] = [];
  for (const item of placed) settled.push({ ...item, ...resolveOverlap(item, settled, 24, grid) });
  return { nodes: settled.map(({ id, x, y }) => ({ id, x, y })), areas: frames };
}
