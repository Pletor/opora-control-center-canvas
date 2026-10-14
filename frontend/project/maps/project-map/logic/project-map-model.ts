/** Lehká mapa kódu: typy odpovědi /api/graphify/overview a čisté výpočty rozmístění bez knihovny. */

export type CommunityId = number | string;
export type TopNode = { id: string; label: string; source_file: string | null; degree: number };
export type Community = {
  id: CommunityId; name: string; rawName?: string | null; size: number; files: number;
  kinds: Record<string, number>; top: TopNode[]; paths: string[];
};
export type CommunityEdge = { source: CommunityId; target: CommunityId; weight: number; count: number };
export type Overview = {
  project: string; generatedAt: string | null; version: string | null;
  counts: { nodes: number; edges: number; communities: number };
  communities: Community[]; edges: CommunityEdge[]; truncated: boolean;
};
export type Bubble = { id: CommunityId; x: number; y: number; r: number };
export type Line = { source: CommunityId; target: CommunityId; x1: number; y1: number; x2: number; y2: number; width: number; weight: number };
export type View = { x: number; y: number; w: number; h: number };
export type Neighbor = { id: CommunityId; name: string; weight: number; count: number };

const GAP = 4;
const MIN_R = 9;

export function isOverview(value: unknown, project: string): value is Overview {
  const v = value as Overview | null;
  return !!v && v.project === project && Array.isArray(v.communities) && Array.isArray(v.edges) && !!v.counts;
}

/** Bubliny od největší ve spirále od středu; každá se posouvá po spirále, dokud nekoliduje. Bez náhody. */
export function layoutCommunities(communities: Community[], _edges: CommunityEdge[], width: number, height: number): Bubble[] {
  const sorted = [...communities].sort((a, b) => b.size - a.size || String(a.id).localeCompare(String(b.id)));
  const total = sorted.reduce((sum, item) => sum + Math.max(1, item.size), 0) || 1;
  const k = Math.sqrt((0.32 * width * height) / (Math.PI * total));
  const maxR = Math.min(width, height) / 5;
  const cx = width / 2, cy = height / 2;
  const placed: Bubble[] = [];
  for (const item of sorted) {
    const r = Math.min(maxR, Math.max(MIN_R, Math.sqrt(Math.max(1, item.size)) * k));
    let angle = 0, x = cx, y = cy;
    for (let step = 0; step < 20000 && collides(placed, x, y, r); step++) {
      const distance = 3 * angle;
      angle += Math.min(0.5, (r * 0.5) / Math.max(distance, 1));
      x = cx + Math.cos(angle) * 3 * angle * (width / height);
      y = cy + Math.sin(angle) * 3 * angle;
    }
    placed.push({ id: item.id, x: round(x), y: round(y), r: round(r) });
  }
  return placed;
}

function collides(placed: Bubble[], x: number, y: number, r: number): boolean {
  return placed.some(b => Math.hypot(b.x - x, b.y - y) < b.r + r + GAP);
}

function round(value: number): number {
  return Math.round(value * 100) / 100;
}

/** Čáry mezi středy nejsilnějších vazeb; tloušťka roste logaritmicky s vahou (1–6 px). */
export function edgeLines(layout: Bubble[], edges: CommunityEdge[], maxEdges = 120): Line[] {
  const at = new Map(layout.map(b => [String(b.id), b]));
  const chosen = [...edges]
    .filter(e => at.has(String(e.source)) && at.has(String(e.target)))
    .sort((a, b) => b.weight - a.weight)
    .slice(0, maxEdges);
  const top = Math.log1p(Math.max(0, ...chosen.map(e => e.weight)));
  return chosen.map(e => {
    const a = at.get(String(e.source))!, b = at.get(String(e.target))!;
    const width = 1 + (top > 0 ? (Math.log1p(Math.max(0, e.weight)) / top) * 5 : 0);
    return { source: e.source, target: e.target, x1: a.x, y1: a.y, x2: b.x, y2: b.y, width: round(width), weight: e.weight };
  });
}

/** Hledá ve jméně, cestách a popiscích nejpropojenějších uzlů; každé slovo dotazu musí sedět. */
export function filterCommunities(list: Community[], query: string): Community[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) return list;
  return list.filter(item => {
    const text = [item.name, ...item.paths, ...item.top.flatMap(t => [t.label, t.source_file ?? ''])].join(' ').toLowerCase();
    return words.every(word => text.includes(word));
  });
}

export const TONES = [
  '--cat-fe-components', '--cat-fe-logic', '--cat-fe-css', '--cat-backend', '--cat-database',
  '--cat-cache', '--cat-security', '--cat-cloud', '--cat-tests',
] as const;

/** Index tónu pro třídu `--tone-N`; stejný index dává stejnou barvu v plátně i v seznamu. */
export function communityTone(index: number): number {
  return ((index % TONES.length) + TONES.length) % TONES.length;
}

export function communityColor(index: number): string {
  return TONES[communityTone(index)];
}

export function neighbors(id: CommunityId, edges: CommunityEdge[], communities: Community[]): Neighbor[] {
  const names = new Map(communities.map(c => [String(c.id), c.name]));
  const key = String(id);
  return edges
    .filter(e => String(e.source) === key || String(e.target) === key)
    .map(e => {
      const other = String(e.source) === key ? e.target : e.source;
      return { id: other, name: names.get(String(other)) ?? String(other), weight: e.weight, count: e.count };
    })
    .filter(n => names.has(String(n.id)))
    .sort((a, b) => b.weight - a.weight);
}

export function fitView(layout: Bubble[], pad = 30): View {
  if (!layout.length) return { x: 0, y: 0, w: 1000, h: 700 };
  const minX = Math.min(...layout.map(b => b.x - b.r)) - pad, maxX = Math.max(...layout.map(b => b.x + b.r)) + pad;
  const minY = Math.min(...layout.map(b => b.y - b.r)) - pad, maxY = Math.max(...layout.map(b => b.y + b.r)) + pad;
  return { x: minX, y: minY, w: maxX - minX, h: maxY - minY };
}

/** Přiblížení kolem bodu (px, py) v souřadnicích mapy; factor < 1 přibližuje. Šířka zůstává v mezích. */
export function zoomAt(view: View, factor: number, px: number, py: number, base: View): View {
  const w = Math.min(base.w * 3, Math.max(base.w / 20, view.w * factor));
  const scale = w / view.w;
  return { x: px - (px - view.x) * scale, y: py - (py - view.y) * scale, w, h: view.h * scale };
}

export function panBy(view: View, dx: number, dy: number): View {
  return { ...view, x: view.x - dx, y: view.y - dy };
}

/** Kolik znaků jména se vejde pod bublinu při daném měřítku; jinak se jméno zkrátí výpustkou. */
export function shortLabel(name: string, max: number): string {
  if (name.length <= max) return name;
  return name.slice(0, Math.max(1, max - 1)) + '…';
}
