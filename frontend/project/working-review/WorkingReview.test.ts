import {describe, expect, it} from 'vitest';
import {selected} from './WorkingReview';
import {ReviewMutations} from './review-requests';

describe('working operation review selection', () => {
  it('does not let a delayed old apply clear a new scope mutation, but permits own refresh completion', () => {
    const requests = new ReviewMutations();
    const old = requests.begin()!;
    expect(requests.begin()).toBeNull();
    requests.invalidate(); // Scope/selected review changed while the old network write was pending.
    const current = requests.begin()!;
    expect(requests.finish(old)).toBe(false);
    expect(requests.begin()).toBeNull(); // The new write must still hold the busy lock.
    expect(requests.finish(current)).toBe(true); // Its own read refresh does not revoke this token.
    expect(requests.begin()).not.toBeNull();
  });
  it('keeps exact immutable selection on reload and refuses another scope or unknown operation', () => {
    const url = '?project=p&workspace=w&workingOperation=remove_item&workingReview=saved';
    expect(selected(url, 'p', 'w')).toEqual({operation: 'remove_item', identifier: 'saved'});
    expect(selected(url, 'p', 'other')).toBeNull();
    expect(selected(url.replace('remove_item', 'other'), 'p', 'w')).toBeNull();
    expect(selected(url.replace('&workingReview=saved', ''), 'p', 'w')).toBeNull();
  });
});
