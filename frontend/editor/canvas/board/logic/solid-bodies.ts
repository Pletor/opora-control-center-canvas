// Pevná tělesa plátna: karta i oblast mají pevnou hranu. Nezasunou se do sebe, nic se neschová pod ničím
// a karta nikdy nestojí půlkou v oblasti a půlkou venku — je buď celá uvnitř, nebo celá venku. Čisté funkce
// bez Reactu a bez React Flow: Board je volá při puštění tahu, App při změně velikosti oblasti. Kdo do které
// oblasti patří, rozhoduje `areaOf` z modelu oblasti — totéž geometrické pravidlo, jaké zná i backend.
import type { CanvasNode } from "@/shared/types/logic/types";
import { areaOf, AREA_SIZE_MAX, AREA_SIZE_MIN } from "@/editor/canvas/area/logic/area-model";
import { resolveOverlap, type Footprint } from "@/editor/canvas/board/logic/layout-model";

/** Obdélník, kterým těleso na plátně zabírá místo: otisk karty, nebo rámeček oblasti. */
export type Body = { id: string; x: number; y: number; w: number; h: number };
/** Mezera mezi tělesy, odsazení obsahu uvnitř oblasti a mřížka, na kterou výsledek dosedne. */
export type SolidOptions = { gap?: number; pad?: number; grid?: number };

/** Volná mezera, kterou kolem sebe drží každé těleso — tolik je „na dosah, ale ne na sobě“. */
export const SOLID_GAP = 24;
/** Odsazení karty od vnitřní hrany oblasti: uvnitř znamená uvnitř i s dechem kolem. */
export const SOLID_AREA_PAD = 16;
const SOLID_GRID = 8;
/** Kolikrát se nejvýš zkusí ustálit (oblast × karta × ostatní karty) — přeplněné plátno se nesmí zacyklit. */
const SETTLE_ROUNDS = 6;
const PUSH_STEPS = 20;

const snap = (value: number, grid: number) => Math.round(value / grid) * grid;
const snapUp = (value: number, grid: number) => Math.ceil(value / grid) * grid;
const snapDown = (value: number, grid: number) => Math.floor(value / grid) * grid;
/** Hodnota v rozsahu; když je dolní mez nad horní, vyhrává dolní (raději větší, než rozbité těleso). */
const between = (value: number, low: number, high: number) => Math.min(Math.max(value, low), Math.max(low, high));

/** Dotýkají se tělesa blíž, než dovoluje `gap`? Stejné pravidlo jako v magnetismu karet. */
function tooClose(a: Body, b: Body, gap: number): boolean {
  return a.x < b.x + b.w + gap && b.x < a.x + a.w + gap && a.y < b.y + b.h + gap && b.y < a.y + a.h + gap;
}

/** Nejkratší cesta ven z rámečku: doleva, doprava, nahoru nebo dolů — podle toho, kam je to blíž. */
function nearestWayOut(body: Body, frame: Body, gap: number): { dx: number; dy: number } {
  const ways = [
    { dx: frame.x - gap - (body.x + body.w), dy: 0 },
    { dx: frame.x + frame.w + gap - body.x, dy: 0 },
    { dx: 0, dy: frame.y - gap - (body.y + body.h) },
    { dx: 0, dy: frame.y + frame.h + gap - body.y },
  ];
  return ways.reduce((best, way) => (Math.abs(way.dx + way.dy) < Math.abs(best.dx + best.dy) ? way : best));
}

/** Celé těleso ven ze všech rámečků: v každém kroku nejkratší cestou z prvního, do kterého zasahuje. */
function pushOutside(body: Body, frames: Body[], gap: number): { x: number; y: number } {
  let x = body.x;
  let y = body.y;
  for (let step = 0; step < PUSH_STEPS; step++) {
    const current = { ...body, x, y };
    const hit = frames.find((frame) => tooClose(current, frame, gap));
    if (!hit) break;
    const way = nearestWayOut(current, hit, gap);
    x += way.dx;
    y += way.dy;
  }
  return { x, y };
}

/** Celé těleso dovnitř rámečku, s odsazením `pad`; co se dovnitř nevejde, sedne aspoň do levého horního rohu. */
function clampInside(body: Body, frame: Body, pad: number): { x: number; y: number } {
  const left = frame.x + pad;
  const top = frame.y + pad;
  return {
    x: between(body.x, left, frame.x + frame.w - pad - body.w),
    y: between(body.y, top, frame.y + frame.h - pad - body.h),
  };
}

/**
 * Kam karta doopravdy dosedne. Střed karty rozhodne, kam patří: leží-li v oblasti, karta se celá vejde
 * dovnitř (s odsazením `pad`); jinak ji každá oblast, do které zasahuje, vystrčí nejkratší cestou ven.
 * Teprve pak se řeší karta proti kartám (`resolveOverlap`) a obojí se zopakuje, dokud se plocha neustálí.
 * `card` je uzel na místě, kde ho uživatel pustil; `footprint` je jeho otisk (karta i s viditelnými bloky)
 * na témže místě. Vrací novou polohu karty — beze změny a beze snapu, když se nic nestalo.
 */
export function settleCard(
  card: CanvasNode,
  footprint: Body,
  others: Body[],
  areas: CanvasNode[],
  opts: SolidOptions = {},
): { x: number; y: number } {
  const gap = opts.gap ?? SOLID_GAP;
  const pad = opts.pad ?? SOLID_AREA_PAD;
  const grid = opts.grid ?? SOLID_GRID;
  const frames: Body[] = areas
    .filter((area) => area.kind === "area" && !!area.size && area.id !== card.id && area.parentId === card.parentId)
    .map((area) => ({ id: area.id, x: area.x, y: area.y, w: area.size!.w, h: area.size!.h }));
  // Domovská oblast se určí jednou, z místa puštění: co uživatel pustil dovnitř, tam zůstane.
  const home = areaOf(card, areas);
  const homeFrame = home ? (frames.find((frame) => frame.id === home.id) ?? null) : null;
  let x = footprint.x;
  let y = footprint.y;
  for (let round = 0; round < SETTLE_ROUNDS; round++) {
    const fromX = x;
    const fromY = y;
    const placed = homeFrame
      ? clampInside({ ...footprint, x, y }, homeFrame, pad)
      : pushOutside({ ...footprint, x, y }, frames, gap);
    const settled = resolveOverlap({ ...footprint, x: placed.x, y: placed.y }, others as Footprint[], gap, grid);
    x = settled.x;
    y = settled.y;
    if (x === fromX && y === fromY) break;
  }
  if (x === footprint.x && y === footprint.y) return { x: card.x, y: card.y };
  return { x: snap(card.x + (x - footprint.x), grid), y: snap(card.y + (y - footprint.y), grid) };
}

/**
 * Kam dosedne puštěný rámeček oblasti: pryč od každé jiné oblasti i od každé cizí karty (ta, co v něm
 * před tahem nebyla), nejkratší cestou ven a s mezerou `gap`. Členové jedou s ním, takže do překážek
 * nepatří. Vrací novou polohu rámečku — beze změny, když nikomu nepřekáží.
 */
export function settleArea(
  moved: Body,
  otherAreas: Body[],
  nonMemberCards: Body[],
  opts: SolidOptions = {},
): { x: number; y: number } {
  const gap = opts.gap ?? SOLID_GAP;
  const grid = opts.grid ?? SOLID_GRID;
  return resolveOverlap(moved as Footprint, [...otherAreas, ...nonMemberCards] as Footprint[], gap, grid);
}

/** Dokud roste doprava (osa x) nebo dolů (osa y): kolik místa je k první překážce v daném pruhu. */
function roomToGrow(area: Body, obstacles: Body[], span: number, axis: "x" | "y", gap: number): number {
  let room = AREA_SIZE_MAX;
  for (const other of obstacles) {
    const across = axis === "x"
      ? area.y < other.y + other.h + gap && other.y < area.y + span + gap
      : area.x < other.x + other.w + gap && other.x < area.x + span + gap;
    if (!across) continue;
    const free = axis === "x" ? other.x - gap - area.x : other.y - gap - area.y;
    // Překážka, která začíná vlevo (nahoře) od naší hrany, se šířkou (výškou) obejít nedá — tu neřešíme.
    if (free < 0) continue;
    room = Math.min(room, free);
  }
  return room;
}

/**
 * Největší rozměr, na který oblast smí vyrůst, a nejmenší, na který smí splasknout. Dolní mez drží obsah:
 * rámeček musí své členy pojmout celé i s odsazením `pad`, jinak by z něj karty vypadly. Horní mez drží
 * sousedy: roste se jen k první překážce (jiná oblast nebo cizí karta) a tam se zastaví. Nejdřív se ustálí
 * šířka, pak se podle ní měří výška. Zmenšit se smí vždy až na dolní mez; při sporu vyhrává obsah.
 */
export function clampAreaResize(
  area: Body,
  members: Body[],
  otherAreas: Body[],
  nonMemberCards: Body[],
  w: number,
  h: number,
  opts: SolidOptions = {},
): { w: number; h: number } {
  const gap = opts.gap ?? SOLID_GAP;
  const pad = opts.pad ?? SOLID_AREA_PAD;
  const grid = opts.grid ?? SOLID_GRID;
  const obstacles = [...otherAreas, ...nonMemberCards].filter((other) => other.id !== area.id);
  const lowW = Math.min(AREA_SIZE_MAX, snapUp(Math.max(AREA_SIZE_MIN, ...members.map((m) => m.x + m.w + pad - area.x)), grid));
  const lowH = Math.min(AREA_SIZE_MAX, snapUp(Math.max(AREA_SIZE_MIN, ...members.map((m) => m.y + m.h + pad - area.y)), grid));
  const wantW = between(snap(w, grid), lowW, AREA_SIZE_MAX);
  const wantH = between(snap(h, grid), lowH, AREA_SIZE_MAX);
  const highW = Math.max(lowW, area.w, snapDown(roomToGrow(area, obstacles, wantH, "x", gap), grid));
  const fitW = Math.min(wantW, highW);
  const highH = Math.max(lowH, area.h, snapDown(roomToGrow(area, obstacles, fitW, "y", gap), grid));
  return { w: fitW, h: Math.min(wantH, highH) };
}
