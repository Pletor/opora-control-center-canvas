import {describe, expect, it} from 'vitest';
import {actionable, actionRequest, displayGraph, selection, type Review} from './flow-review';

const review = {operation: 'version_activate', identifier: 'v1', digest: 'exact', workflow: {kind: 'heart'}, selected: {id: 'v1', status: 'candidate'}, active: null, nodeRun: null} as Review;
describe('Exact native workflow review', () => {
  it('positions only missing coordinates without changing native graph or IDs', () => {
    const graph = {nodes: [{id: 'a', type: 'debug.echo'}, {id: 'b', type: 'debug.echo'}], edges: []};
    const shown = displayGraph(graph);
    expect(shown.nodes[0].position).not.toEqual(shown.nodes[1].position);
    expect(graph.nodes[0]).not.toHaveProperty('position');
    expect(shown.nodes.map(n => n.id)).toEqual(['a', 'b']);
  });
  it('binds selection to scope and never substitutes an unknown operation', () => {
    expect(selection('?project=p&workspace=w&flowReview=v1&flowOperation=version_activate', 'p', 'w')).toEqual({operation: 'version_activate', identifier: 'v1'});
    expect(selection('?project=p&workspace=w&flowReview=v1&flowOperation=unknown', 'p', 'w')).toBeNull();
    expect(selection('?project=p&workspace=w&flowReview=v1&flowOperation=version_activate', 'p', 'other')).toBeNull();
  });
  it('submits only the selected immutable version with the observed digest', () => {
    expect(actionRequest(review, '')).toEqual({url: '/api/flow/versions/v1/activate?expectedReviewDigest=exact', body: {}});
    expect(actionable({...review, selected: {...review.selected!, status: 'active'}})).toBe(false);
    expect(actionable({...review, workflow: {...review.workflow, kind: 'page_intent'}})).toBe(false);
  });
});
