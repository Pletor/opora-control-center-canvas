// Bézierova vazba podle normály portu, převzatá z prototypu Architektura projektu (`prototype/routing.mjs`,
// `routeConnection` bez objížďky překážek): ohyb = vzdálenost × 0,35, sevřený do 20–140 px, kontrolní body leží
// ve směru, kterým port míří ven z karty. Štítek souhrnné vazby stojí v polovině křivky (t = 0,5).

export type PortSide = "left" | "right" | "top" | "bottom";
export type PortPoint = { x: number; y: number; side: PortSide };
type Point = { x: number; y: number };

const NORMAL: Record<PortSide, Point> = { left: { x: -1, y: 0 }, right: { x: 1, y: 0 }, top: { x: 0, y: -1 }, bottom: { x: 0, y: 1 } };

export function bendOf(start: Point, end: Point): number {
  return Math.max(20, Math.min(140, Math.hypot(end.x - start.x, end.y - start.y) * 0.35));
}

export function cubicPoint(p: Point, a: Point, b: Point, q: Point, t: number): Point {
  const u = 1 - t;
  return { x: u * u * u * p.x + 3 * u * u * t * a.x + 3 * u * t * t * b.x + t * t * t * q.x, y: u * u * u * p.y + 3 * u * u * t * a.y + 3 * u * t * t * b.y + t * t * t * q.y };
}

/** Cesta SVG `M … C …` a bod pro štítek. */
export function studioBezier(start: PortPoint, end: PortPoint): { d: string; label: Point } {
  const bend = bendOf(start, end);
  const sn = NORMAL[start.side]; const tn = NORMAL[end.side];
  const a = { x: start.x + sn.x * bend, y: start.y + sn.y * bend };
  const b = { x: end.x + tn.x * bend, y: end.y + tn.y * bend };
  const round = (value: number) => Math.round(value * 100) / 100;
  return { d: `M ${round(start.x)} ${round(start.y)} C ${round(a.x)} ${round(a.y)} ${round(b.x)} ${round(b.y)} ${round(end.x)} ${round(end.y)}`, label: cubicPoint(start, a, b, end, 0.5) };
}
