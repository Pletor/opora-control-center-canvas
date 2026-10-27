// Rozložení vazeb Studia (prototyp `studio-routing.mjs`, `studio-routes/1`): strany portů se otočí k protějšku,
// port sdílený víc vazbami míří ke středu svých protějšků a drží jednu kotvu, a z kandidátních dvojic stran se vybere
// první, jejíž Bézierova křivka vzorkováním neprotne cizí kartu. Jen geometrie: model se nemění, objížďka není zaručená.
import { cubicPoint } from "./routing";
import type { Point, PortDirection, PortRef, PortSide } from "./model-types";

export const STUDIO_ROUTING_VERSION = "studio-routes/1";

export type LayoutPort = { id: string; direction: PortDirection; side?: PortSide };
export type LayoutNode = { id: string; x: number; y: number; width: number; height: number; ports: readonly LayoutPort[] };
export type LayoutEdge = { id: string; from: PortRef; to: PortRef; enabled?: boolean };
export type PortAnchor = Point & { side: PortSide; fraction: number };
export type StudioRoute = { kind: "bezier"; start: Point & { side: PortSide }; end: Point & { side: PortSide }; points: Point[]; d: string; routingVersion: string;
  sourceSide?: PortSide; targetSide?: PortSide; candidateIndex?: number; probeClear?: boolean; inactive?: boolean };

const NORMALS: Record<PortSide, Point> = { left: { x: -1, y: 0 }, right: { x: 1, y: 0 }, top: { x: 0, y: -1 }, bottom: { x: 0, y: 1 } };
const center = (n: LayoutNode) => ({ x: n.x + n.width / 2, y: n.y + n.height / 2 });
const key = (e: PortRef) => JSON.stringify([e.nodeId, e.portId]);

function anchor(node: LayoutNode, port: LayoutPort, side: PortSide): PortAnchor {
  const fraction = (node.ports.findIndex((p) => p.id === port.id) + 1) / (node.ports.length + 1);
  return { side, fraction, x: side === "left" ? 0 : side === "right" ? node.width : node.width * fraction, y: side === "top" ? 0 : side === "bottom" ? node.height : node.height * fraction };
}
function world(node: LayoutNode, port: LayoutPort, side: PortSide) {
  const a = anchor(node, port, side);
  return { x: node.x + a.x, y: node.y + a.y, side };
}
function curve(start: Point & { side: PortSide }, end: Point & { side: PortSide }): StudioRoute {
  const distance = Math.max(20, Math.min(140, Math.hypot(end.x - start.x, end.y - start.y) * 0.36));
  const a = { x: start.x + NORMALS[start.side].x * distance, y: start.y + NORMALS[start.side].y * distance };
  const b = { x: end.x + NORMALS[end.side].x * distance, y: end.y + NORMALS[end.side].y * distance };
  return { kind: "bezier", start, end, points: [start, a, b, end], d: `M ${start.x} ${start.y} C ${a.x} ${a.y} ${b.x} ${b.y} ${end.x} ${end.y}`, routingVersion: STUDIO_ROUTING_VERSION };
}
function clearProbe(route: StudioRoute, nodes: readonly LayoutNode[], sourceId: string, targetId: string): boolean {
  const [p, a, b, q] = route.points;
  for (let j = 2; j <= 38; j++) {
    const t = j / 40, pt = cubicPoint(p, a, b, q, t);
    for (const n of nodes) {
      if ((n.id === sourceId && t < 0.12) || (n.id === targetId && t > 0.88)) continue;
      if (pt.x > n.x - 4 && pt.x < n.x + n.width + 4 && pt.y > n.y - 4 && pt.y < n.y + n.height + 4) return false;
    }
  }
  return true;
}

export function layoutStudioConnections(nodes: readonly LayoutNode[], edges: readonly LayoutEdge[]) {
  const byId = new Map(nodes.map((n) => [n.id, n])), ports = new Map<string, Map<string, PortAnchor>>(), peers = new Map<string, LayoutNode[]>();
  const fixed = new Map<string, PortSide>(), routes = new Map<string, StudioRoute>();
  const endpoints = (edge: LayoutEdge) => {
    const a = byId.get(edge.from.nodeId), b = byId.get(edge.to.nodeId), out = a?.ports.find((p) => p.id === edge.from.portId), input = b?.ports.find((p) => p.id === edge.to.portId);
    return a && b && out && input ? { a, b, out, input } : null;
  };
  for (const n of nodes) ports.set(n.id, new Map(n.ports.map((p) => [p.id, anchor(n, p, p.side ?? (p.direction === "input" ? "left" : "right"))])));
  for (const e of edges) {
    if (e.enabled === false) continue;
    const ends = endpoints(e);
    if (!ends) continue;
    for (const [ref, peer] of [[e.from, ends.b], [e.to, ends.a]] as const) { const k = key(ref), list = peers.get(k) ?? []; list.push(peer); peers.set(k, list); }
  }
  for (const n of nodes) for (const p of n.ports) {
    const k = key({ nodeId: n.id, portId: p.id }), list = peers.get(k);
    if (!list || list.length < 2) continue;
    const own = center(n), mean = list.reduce((sum, peer) => { const c = center(peer); return { x: sum.x + c.x / list.length, y: sum.y + c.y / list.length }; }, { x: 0, y: 0 });
    const dx = mean.x - own.x, dy = mean.y - own.y, side: PortSide = Math.abs(dx) >= Math.abs(dy) ? (dx >= 0 ? "right" : "left") : (dy >= 0 ? "bottom" : "top");
    fixed.set(k, side); ports.get(n.id)!.set(p.id, anchor(n, p, side));
  }
  for (const e of edges) {
    if (e.enabled === false) continue;
    const ends = endpoints(e);
    if (!ends) continue;
    const { a, b, out, input } = ends, ac = center(a), bc = center(b), dx = bc.x - ac.x, dy = bc.y - ac.y;
    const h: [PortSide, PortSide] = dx >= 0 ? ["right", "left"] : ["left", "right"], v: [PortSide, PortSide] = dy >= 0 ? ["bottom", "top"] : ["top", "bottom"];
    const candidates: [PortSide, PortSide][] = [Math.abs(dx) >= Math.abs(dy) ? h : v, h, v, [h[0], v[1]], [v[0], h[1]]], seen = new Set<string>(), unique: [PortSide, PortSide][] = [];
    for (const pair of candidates) {
      const sides: [PortSide, PortSide] = [fixed.get(key(e.from)) ?? pair[0], fixed.get(key(e.to)) ?? pair[1]], signature = sides.join("/");
      if (!seen.has(signature)) { seen.add(signature); unique.push(sides); }
    }
    const options = unique.map(([sourceSide, targetSide], candidateIndex) => {
      const route = curve(world(a, out, sourceSide), world(b, input, targetSide));
      return { ...route, sourceSide, targetSide, candidateIndex, probeClear: clearProbe(route, nodes, a.id, b.id) };
    });
    const selected = options.find((r) => r.probeClear) ?? options[0];
    routes.set(e.id, selected);
    ports.get(a.id)!.set(out.id, anchor(a, out, selected.sourceSide));
    ports.get(b.id)!.set(input.id, anchor(b, input, selected.targetSide));
  }
  // Neaktivní vazby sledují viditelné konce a strany aktivních neovlivní (vlastní pravidlo zobrazení).
  for (const e of edges) {
    if (e.enabled !== false) continue;
    const ends = endpoints(e);
    if (!ends) continue;
    const { a, b, out, input } = ends;
    routes.set(e.id, { ...curve(world(a, out, ports.get(a.id)!.get(out.id)!.side), world(b, input, ports.get(b.id)!.get(input.id)!.side)), inactive: true });
  }
  return { version: STUDIO_ROUTING_VERSION, ports, routes };
}
