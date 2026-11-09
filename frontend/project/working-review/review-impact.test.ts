import {describe, expect, it} from 'vitest';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import ReviewImpact from './ReviewImpact';
import {impact} from './review-impact';

describe('working review impact projection', () => {
  it('summarizes changed targets in a large graph and retains every exact source under closed details', () => {
    const nodes = Array.from({length: 185}, (_, n) => ({id: `n${n}`, name: `Card ${n}`, kind: 'node', purpose: `Full text ${n}`}));
    const before = {graph: {nodes, edges: []}, state: {revision: 3, state: {nodes: {n0: {phase: 'test'}}, rules: [], decisions: []}}, workspaceRows: [['p', 'w', 'n0', 1, 'full history']]};
    const after = {graph: {nodes: nodes.slice(1), edges: []}, state: {nodes: {}, rules: [], decisions: []}, workspaceRows: []};
    expect(impact(before, after)).toMatchObject({oldNodeCount: 185, nextNodeCount: 184, stateNodes: 1, workspaceRemoved: 1, workspaceAdded: 0});
    expect(impact(before, after).nodes.map(item => item.id)).toEqual(['n0']);
    const html = renderToStaticMarkup(createElement(ReviewImpact, {before, after, input: {target: 'n0'}, operation: 'remove_item'}));
    expect(html).toContain('Odstranění: Card 0');
    expect(html).not.toContain('Odstranění: Card 184');
    expect(html).toContain('Full text 184');
    expect(html).toContain('full history');
    expect(html).not.toMatch(/<details[^>]*\bopen\b/);
    expect(html).toContain('Úplné uložené podklady');
  });
  it('reports restoration without confusing preserved existing content with restored entries', () => {
    const before = {graph: {nodes: [{id: 'keep', name: 'Keep'}]}, state: {state: {nodes: {keep: {phase: 'test'}}}}, workspaceRows: [['p','w','keep',1]]};
    const after = {graph: {nodes: [{id: 'keep', name: 'Keep'}, {id: 'back', name: 'Restored'}]}, state: {nodes: {keep: {phase: 'test'}, back: {phase: 'test'}}}, workspaceRows: [['p','w','keep',1], ['p','w','back',2]]};
    expect(impact(before, after)).toMatchObject({stateNodes: 1, workspaceRemoved: 0, workspaceAdded: 1});
    expect(impact(before, after).nodes[0]).toMatchObject({id: 'back', action: 'Přidání'});
  });
});
