"""Outbox facts of the agent-state snapshot: `eventsCursor` and `cards[].lastEventAt` (docs/oporahub-agent-state.md).

Read on the same connection and under the same project lock as the rest of the document, so the
cursor is exactly the last event already reflected in the snapshot: a consumer resumes the events
stream from it (Last-Event-ID) and neither misses nor duplicates a change. Plain SELECTs only.
"""
from database.repositories import opora_events as store


def read(db, project, workspace):
    """`(eventsCursor, {nodeId: at})` from one consistent read of `opora_events`."""
    return store.head(db), store.last_event_at(db, project, workspace)


def attach(cards, last):
    """Each card gets `lastEventAt` (ISO of its newest event, or None)."""
    return [{**card, "lastEventAt": last.get(card["nodeId"])} for card in cards]
