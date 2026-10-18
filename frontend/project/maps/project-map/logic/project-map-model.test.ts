import { describe, expect, it } from 'vitest';
import {
  communityColor, communityTone, edgeLines, filterCommunities, fitView, isOverview, layoutCommunities,
  neighbors, panBy, shortLabel, zoomAt, type Community, type CommunityEdge,
} from './project-map-model';

function community(id: number, size: number, name = 'area/' + id, extra: Partial<Community> = {}): Community {
  return { id, name, size, files: 1, kinds: { code: size }, top: [], paths: [], ...extra };
}

const fifty = Array.from({ length: 50 }, (_, i) => community(i, ((i * 37) % 120) + 1));

describe('layoutCommunities', () => {
  it('places 50 bubbles without overlap', () => {
    const layout = layoutCommunities(fifty, [], 1000, 700);
    expect(layout).toHaveLength(50);
    for (let i = 0; i < layout.length; i++)
      for (let j = i + 1; j < layout.length; j++) {
        const a = layout[i], b = layout[j];
        expect(Math.hypot(a.x - b.x, a.y - b.y)).toBeGreaterThanOrEqual(a.r + b.r - 0.02);
      }
  });

  it('is deterministic and puts the largest bubble in the centre', () => {
    const first = layoutCommunities(fifty, [], 1000, 700);
    const second = layoutCommunities([...fifty].reverse(), [], 1000, 700);
    expect(second).toEqual(first);
    const largest = [...fifty].sort((a, b) => b.size - a.size)[0];
    expect(first[0]).toMatchObject({ id: largest.id, x: 500, y: 350 });
    expect(first[0].r).toBeGreaterThan(first[first.length - 1].r);
  });
});

describe('edgeLines', () => {
  it('keeps the strongest edges and scales width logarithmically', () => {
    const layout = layoutCommunities(fifty.slice(0, 3), [], 1000, 700);
    const edges: CommunityEdge[] = [
      { source: 0, target: 1, weight: 1, count: 1 }, { source: 1, target: 2, weight: 100, count: 9 },
      { source: 0, target: 99, weight: 50, count: 1 },
    ];
    const lines = edgeLines(layout, edges, 1);
    expect(lines).toHaveLength(1);
    expect(lines[0]).toMatchObject({ source: 1, target: 2, width: 6 });
    const both = edgeLines(layout, edges);
    expect(both.map(l => l.weight)).toEqual([100, 1]);
    expect(both[1].width).toBeGreaterThan(1);
    expect(both[1].width).toBeLessThan(2);
  });
});

describe('filterCommunities', () => {
  const list = [
    community(1, 5, 'frontend/editor/canvas', { paths: ['frontend/editor'] }),
    community(2, 5, 'backend', { paths: ['backend/live_run'], top: [{ id: 'x', label: 'AgentBindings', source_file: 'backend/live_run/bindings.py', degree: 4 }] }),
  ];
  it('searches name, paths and top labels', () => {
    expect(filterCommunities(list, '')).toBe(list);
    expect(filterCommunities(list, 'canvas').map(c => c.id)).toEqual([1]);
    expect(filterCommunities(list, 'live_run').map(c => c.id)).toEqual([2]);
    expect(filterCommunities(list, 'agentbind').map(c => c.id)).toEqual([2]);
    expect(filterCommunities(list, 'backend bindings.py').map(c => c.id)).toEqual([2]);
    expect(filterCommunities(list, 'nic')).toEqual([]);
  });
});

describe('colors and neighbours', () => {
  it('cycles through category tokens', () => {
    expect(communityColor(0)).toBe('--cat-fe-components');
    expect(communityColor(9)).toBe(communityColor(0));
    expect(communityTone(-1)).toBe(8);
  });
  it('lists neighbouring communities by weight', () => {
    const list = [community(1, 1, 'a'), community(2, 1, 'b'), community(3, 1, 'c')];
    const edges = [{ source: 1, target: 2, weight: 2, count: 1 }, { source: 3, target: 1, weight: 5, count: 2 }];
    expect(neighbors(1, edges, list)).toEqual([
      { id: 3, name: 'c', weight: 5, count: 2 }, { id: 2, name: 'b', weight: 2, count: 1 }]);
  });
});

describe('view', () => {
  it('fits, zooms around a point and pans', () => {
    const base = fitView([{ id: 1, x: 100, y: 100, r: 50 }], 0);
    expect(base).toEqual({ x: 50, y: 50, w: 100, h: 100 });
    const zoomed = zoomAt(base, 0.5, 100, 100, base);
    expect(zoomed).toEqual({ x: 75, y: 75, w: 50, h: 50 });
    expect(zoomAt(base, 0.0001, 100, 100, base).w).toBe(5);
    expect(panBy(zoomed, 10, -5)).toEqual({ x: 65, y: 80, w: 50, h: 50 });
  });
  it('shortens labels and validates the response', () => {
    expect(shortLabel('frontend/editor', 9)).toBe('frontend…');
    expect(shortLabel('abc', 9)).toBe('abc');
    expect(isOverview({ project: 'p', communities: [], edges: [], counts: {} }, 'p')).toBe(true);
    expect(isOverview({ project: 'q', communities: [], edges: [], counts: {} }, 'p')).toBe(false);
  });
});
