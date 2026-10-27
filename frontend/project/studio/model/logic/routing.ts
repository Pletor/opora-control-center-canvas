// Trasa jedné vazby (prototyp `routing.mjs`): Bézierova křivka vedená po normále portu; když by přímá křivka prošla
// kartou, zaoblená objížďka kolem obálky překážek (nejméně křížení, pak nejkratší).
import type { Point, PortSide } from "./model-types";

export type Anchor = Point & { side: PortSide };
export type Rect = { x: number; y: number; w: number; h: number };
export type Route =
  | { kind: "bezier"; d: string; points: Point[] }
  | { kind: "rounded"; d: string; points: Point[]; obstacleCrossings: number };

const NORMALS: Record<PortSide, Point> = { left: { x: -1, y: 0 }, right: { x: 1, y: 0 }, top: { x: 0, y: -1 }, bottom: { x: 0, y: 1 } };
const inside = (p: Point, r: Rect) => p.x > r.x + 2 && p.x < r.x + r.w - 2 && p.y > r.y + 2 && p.y < r.y + r.h - 2;
const distance = (a: Point, b: Point) => Math.hypot(b.x - a.x, b.y - a.y);
function lineHit(a: Point, b: Point, r: Rect): boolean {
  if (a.x === b.x) return a.x > r.x + 2 && a.x < r.x + r.w - 2 && Math.max(a.y, b.y) > r.y + 2 && Math.min(a.y, b.y) < r.y + r.h - 2;
  if (a.y === b.y) return a.y > r.y + 2 && a.y < r.y + r.h - 2 && Math.max(a.x, b.x) > r.x + 2 && Math.min(a.x, b.x) < r.x + r.w - 2;
  return false;
}

export function cubicPoint(p: Point, a: Point, b: Point, q: Point, t: number): Point {
  const u = 1 - t;
  return { x: u * u * u * p.x + 3 * u * u * t * a.x + 3 * u * t * t * b.x + t * t * t * q.x, y: u * u * u * p.y + 3 * u * u * t * a.y + 3 * u * t * t * b.y + t * t * t * q.y };
}

export function routeConnection(start: Anchor, end: Anchor, rectangles: readonly Rect[] = []): Route {
  const sn = NORMALS[start.side], tn = NORMALS[end.side], bend = Math.max(20, Math.min(140, distance(start, end) * 0.35));
  const a = { x: start.x + sn.x * bend, y: start.y + sn.y * bend }, b = { x: end.x + tn.x * bend, y: end.y + tn.y * bend };
  let hit = false;
  for (let i = 1; i < 40 && !hit; i++) { const p = cubicPoint(start, a, b, end, i / 40); hit = rectangles.some((r) => inside(p, r)); }
  if (!hit) return { kind: "bezier", d: `M ${start.x} ${start.y} C ${a.x} ${a.y} ${b.x} ${b.y} ${end.x} ${end.y}`, points: [start, a, b, end] };
  const p = { x: start.x + sn.x * 25, y: start.y + sn.y * 25 }, q = { x: end.x + tn.x * 25, y: end.y + tn.y * 25 };
  const minX = Math.min(start.x, end.x, ...rectangles.map((r) => r.x)) - 40, maxX = Math.max(start.x, end.x, ...rectangles.map((r) => r.x + r.w)) + 40;
  const minY = Math.min(start.y, end.y, ...rectangles.map((r) => r.y)) - 40, maxY = Math.max(start.y, end.y, ...rectangles.map((r) => r.y + r.h)) + 40;
  const candidates: Point[][] = [minY, maxY].map((y) => [start, p, { x: p.x, y }, { x: q.x, y }, q, end])
    .concat([minX, maxX].map((x) => [start, p, { x, y: p.y }, { x, y: q.y }, q, end]));
  const ranked = candidates.map((raw) => {
    const points = raw.filter((pt, i) => i === 0 || distance(pt, raw[i - 1]) > 0.01);
    let hits = 0, length = 0;
    for (let i = 1; i < points.length; i++) { length += distance(points[i - 1], points[i]); hits += rectangles.filter((r) => lineHit(points[i - 1], points[i], r)).length; }
    return { points, hits, length };
  }).sort((x, y) => x.hits - y.hits || x.length - y.length);
  const points = ranked[0].points;
  let d = `M ${points[0].x} ${points[0].y}`;
  for (let i = 1; i < points.length - 1; i++) {
    const prev = points[i - 1], corner = points[i], next = points[i + 1], before = distance(prev, corner), after = distance(corner, next), radius = Math.min(12, before / 2, after / 2);
    if (!before || !after) continue;
    const u = { x: corner.x + (prev.x - corner.x) * radius / before, y: corner.y + (prev.y - corner.y) * radius / before };
    const v = { x: corner.x + (next.x - corner.x) * radius / after, y: corner.y + (next.y - corner.y) * radius / after };
    d += ` L ${u.x} ${u.y} Q ${corner.x} ${corner.y} ${v.x} ${v.y}`;
  }
  d += ` L ${end.x} ${end.y}`;
  return { kind: "rounded", d, points, obstacleCrossings: ranked[0].hits };
}
